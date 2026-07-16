"""FFmpeg 导出引擎"""

import logging
import os
import subprocess
import sys
import tempfile
import threading
import wave
import numpy as np
from dataclasses import dataclass
from PIL import Image
import ffmpeg

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from core.compositor import Compositor
from core.aspect_ratio import calculate_export_dimensions

logger = logging.getLogger(__name__)

_gpu_available_cache: bool | None = None


def is_gpu_available() -> bool:
    """检测 CUDA NVENC 是否可用（结果缓存）"""
    global _gpu_available_cache
    if _gpu_available_cache is not None:
        return _gpu_available_cache
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-init_hw_device", "cuda=cuda:0",
             "-f", "lavfi", "-i", "testsrc=duration=0.1:size=320x240:rate=10",
             "-vf", "hwupload_cuda,scale_cuda=320:240", "-c:v", "h264_nvenc",
             "-b:v", "1M", "-f", "null", "-"],
            capture_output=True, timeout=10,
        )
        _gpu_available_cache = result.returncode == 0
    except Exception:
        _gpu_available_cache = False
    return _gpu_available_cache


def _start_stderr_reader(process):
    """后台线程实时读取 ffmpeg stderr，防止管道缓冲区满阻塞，同时写入临时文件"""
    chunks = []

    def _read():
        try:
            for line in process.stderr:
                text = line.decode("utf-8", errors="replace")
                chunks.append(text)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(text.rstrip())
        except Exception:
            pass
    t = threading.Thread(target=_read, daemon=True)
    t.start()
    return t, chunks


@dataclass
class ExportSettings:
    output_path: str
    format: str = "mp4"            # "mp4" / "gif"
    fps: int = 30
    bitrate: str = "10M"
    width: int = 0                 # 0 = 自动计算；>0 = 自定义精确宽度
    height: int = 0                # 0 = 自动计算；>0 = 自定义精确高度
    max_height: int | None = None  # 分辨率上限（仅缩小不放大），None = 不限制
    samplerate: int = 44100
    aspect_ratio: str = "native"
    quality: float = 1.0
    loop: bool = True              # GIF 是否循环
    preset: str = "veryfast"       # x264 preset: ultrafast/superfast/veryfast/faster/fast/medium/slow/slower/veryslow
    use_gpu: bool = False          # 使用 GPU (NVENC CUDA) 硬件编码
    clip_speeds: list[tuple[float, float, float]] | None = None  # (start_ms, end_ms, speed)
    extra_audio: list | None = None  # list[AudioRegion]
    crop_region: 'CropRegion | None' = None


@dataclass
class ExportResult:
    success: bool
    path: str
    duration: float = 0.0
    size_bytes: int = 0
    error: str | None = None


class ExportWorker(QObject):
    """在工作线程中执行导出，不阻塞 UI"""

    progress = pyqtSignal(int)
    finished = pyqtSignal(ExportResult)

    def __init__(self, compositor: Compositor,
                 audio_data: np.ndarray | None,
                 settings: ExportSettings):
        super().__init__()
        self._compositor = compositor
        self._audio_data = audio_data
        self._settings = settings
        self._cancelled = False
        self._process = None

    def cancel(self):
        self._cancelled = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def run(self):
        try:
            if self._settings.format == "gif":
                self._export_gif()
            else:
                self._export_mp4()
        except Exception as exc:
            self.finished.emit(ExportResult(False, self._settings.output_path,
                                            error=f"导出异常: {exc}"))

    @staticmethod
    def _process_one(img, index, target_w, target_h, pix_fmt):
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.LANCZOS)
        if img.mode != pix_fmt:
            img = img.convert(pix_fmt)
        return index, img.tobytes()

    def _stream_frames_parallel(self, total, w, h, pix_fmt,
                                stderr_thread, stderr_chunks):
        from concurrent.futures import ThreadPoolExecutor

        max_workers = min(os.cpu_count() or 4, 8)
        buffer_size = max_workers * 2
        c = self._compositor

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            frame_iter = enumerate(c.render_all())

            for _ in range(buffer_size):
                try:
                    idx, frame = next(frame_iter)
                except StopIteration:
                    break
                futures.append(executor.submit(
                    self._process_one, frame, idx, w, h, pix_fmt))

            while futures:
                idx, data = futures[0].result()
                futures.pop(0)

                if self._cancelled:
                    for f in futures:
                        f.cancel()
                    self._process.terminate()
                    self.finished.emit(ExportResult(
                        False, self._settings.output_path, error="已取消"))
                    return False

                try:
                    self._process.stdin.write(data)
                except BrokenPipeError:
                    self._process.stdin.close()
                    self._process.wait()
                    stderr_thread.join(timeout=2)
                    stderr_text = "".join(stderr_chunks).strip()
                    if not stderr_text:
                        stderr_text = "(ffmpeg 无 stderr 输出)"
                    self._process = None
                    self.finished.emit(ExportResult(
                        False, self._settings.output_path,
                        error=f"FFmpeg 管道断开:\n{stderr_text}"))
                    return False

                self.progress.emit(int((idx + 1) / total * 100))

                try:
                    next_idx, next_frame = next(frame_iter)
                except StopIteration:
                    continue
                futures.append(executor.submit(
                    self._process_one, next_frame, next_idx, w, h, pix_fmt))

        return True

    # ── MP4 ────────────────────────────────────────────

    def _export_mp4(self):
        s = self._settings
        if s.use_gpu and is_gpu_available():
            self._export_mp4_nvenc()
            return
        self._export_mp4_cpu()

    # ── MP4 (CPU: libx264) ──────────────────────────────

    def _export_mp4_cpu(self):
        s = self._settings
        c = self._compositor
        src_w, src_h = c.width, c.height

        # 计算输出尺寸
        if s.width and s.height:
            # 自定义精确尺寸：不超过源分辨率
            w = min(s.width, src_w) if src_w > 0 else s.width
            h = min(s.height, src_h) if src_h > 0 else s.height
        else:
            dims = calculate_export_dimensions(
                src_w, src_h, s.aspect_ratio, quality=s.quality,
                max_height=s.max_height)
            w, h = dims.width, dims.height

        # 裁剪影响导出尺寸
        if s.crop_region and (s.crop_region.width < 1.0 or s.crop_region.height < 1.0):
            w = int(w * s.crop_region.width)
            h = int(h * s.crop_region.height)

        total = c.total_output_frames
        if total == 0:
            self.finished.emit(ExportResult(False, s.output_path,
                                            error="没有帧可以导出"))
            return

        video = ffmpeg.input("pipe:", format="rawvideo",
                              pix_fmt="rgb24", s=f"{w}x{h}", r=c.fps)

        # ── 速度滤镜 ────────────────────────────────────────
        # ── 音频处理 ────────────────────────────────────────
        _temp_paths = []

        # 1) 保存原始录音到临时 WAV
        orig_wav = None
        if self._audio_data is not None and len(self._audio_data) > 0:
            orig_wav = self._save_temp_wav(self._audio_data, s.samplerate)
            _temp_paths.append(orig_wav)

        # 2) 混合额外音频轨道
        mixed_wav = None
        extra = s.extra_audio or []
        if extra:
            mixed_wav = self._build_audio_filtergraph(
                extra, orig_wav, s.samplerate,
                video_duration=total / c.fps,
            )
            if mixed_wav:
                _temp_paths.append(mixed_wav)
        elif orig_wav and c._clips:
            mixed_wav = self._build_audio_filtergraph(
                [], orig_wav, s.samplerate,
                video_duration=total / c.fps,
            )
            if mixed_wav:
                _temp_paths.append(mixed_wav)

        # 3) 确定最终音频输入并构建 output
        final_wav = mixed_wav or orig_wav
        if final_wav:
            audio_input = ffmpeg.input(final_wav)

            # 速度变化时同步调整音频
            output = ffmpeg.output(
                video, audio_input, s.output_path,
                vcodec="libx264", pix_fmt="yuv420p",
                video_bitrate=s.bitrate, preset=s.preset,
                acodec="aac", audio_bitrate="192k",
            )
        else:
            output = ffmpeg.output(
                video, s.output_path,
                vcodec="libx264", pix_fmt="yuv420p",
                video_bitrate=s.bitrate, preset=s.preset,
            )

        output = output.overwrite_output()
        self._process = output.run_async(pipe_stdin=True, pipe_stderr=True)
        stderr_thread, stderr_chunks = _start_stderr_reader(self._process)

        if logger.isEnabledFor(logging.DEBUG):
            cmd = output.compile()
            logger.debug("ffmpeg {' '.join(cmd)}")
            logger.debug("帧数={total} 尺寸={w}x{h} fps={s.fps}")

        if not self._stream_frames_parallel(
                total, w, h, "RGB", stderr_thread, stderr_chunks):
            return

        process = self._process
        process.stdin.close()
        returncode = process.wait()
        stderr_thread.join(timeout=2)
        stderr_text = "".join(stderr_chunks).strip()
        self._process = None

        for p in _temp_paths:
            try:
                os.remove(p)
            except OSError:
                pass

        if returncode != 0 or not os.path.exists(s.output_path):
            self.finished.emit(ExportResult(
                False, s.output_path,
                error=f"FFmpeg 导出失败 (exit={returncode}):\n{stderr_text}",
            ))
            return

        result = ExportResult(
            success=True, path=s.output_path,
            size_bytes=os.path.getsize(s.output_path),
            duration=total / c.fps,
        )
        self.finished.emit(result)

    # ── MP4 (GPU: NVENC CUDA) ───────────────────────────

    def _export_mp4_nvenc(self):
        s = self._settings
        c = self._compositor
        src_w, src_h = c.width, c.height

        if s.width and s.height:
            w = min(s.width, src_w) if src_w > 0 else s.width
            h = min(s.height, src_h) if src_h > 0 else s.height
        else:
            dims = calculate_export_dimensions(
                src_w, src_h, s.aspect_ratio, quality=s.quality,
                max_height=s.max_height)
            w, h = dims.width, dims.height

        if s.crop_region and (s.crop_region.width < 1.0 or s.crop_region.height < 1.0):
            w = int(w * s.crop_region.width)
            h = int(h * s.crop_region.height)

        total = c.total_output_frames
        if total == 0:
            self.finished.emit(ExportResult(False, s.output_path,
                                            error="没有帧可以导出"))
            return

        # 音频处理（与 CPU 路径共用临时 WAV 逻辑）
        _temp_paths = []
        orig_wav = None
        if self._audio_data is not None and len(self._audio_data) > 0:
            orig_wav = self._save_temp_wav(self._audio_data, s.samplerate)
            _temp_paths.append(orig_wav)

        mixed_wav = None
        extra = s.extra_audio or []
        if extra:
            mixed_wav = self._build_audio_filtergraph(
                extra, orig_wav, s.samplerate,
                video_duration=total / c.fps,
            )
            if mixed_wav:
                _temp_paths.append(mixed_wav)
        elif orig_wav and c._clips:
            mixed_wav = self._build_audio_filtergraph(
                [], orig_wav, s.samplerate,
                video_duration=total / c.fps,
            )
            if mixed_wav:
                _temp_paths.append(mixed_wav)

        final_wav = mixed_wav or orig_wav

        # 视频输入：rgba（NVENC 原生支持，无需 yuv 转换）
        video = ffmpeg.input("pipe:", format="rawvideo",
                              pix_fmt="rgba", s=f"{w}x{h}", r=c.fps)
        video = video.filter("hwupload_cuda")

        if final_wav:
            audio_input = ffmpeg.input(final_wav)
            output = ffmpeg.output(
                video, audio_input, s.output_path,
                vcodec="h264_nvenc", video_bitrate=s.bitrate,
                acodec="aac", audio_bitrate="192k",
            )
        else:
            output = ffmpeg.output(
                video, s.output_path,
                vcodec="h264_nvenc", video_bitrate=s.bitrate,
            )

        output = output.overwrite_output()
        cmd = output.compile()
        cmd.insert(1, "-init_hw_device")
        cmd.insert(2, "cuda=cuda:0")
        self._process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        stderr_thread, stderr_chunks = _start_stderr_reader(self._process)

        if not self._stream_frames_parallel(
                total, w, h, "RGBA", stderr_thread, stderr_chunks):
            return

        process = self._process
        process.stdin.close()
        returncode = process.wait()
        stderr_thread.join(timeout=2)
        stderr_text = "".join(stderr_chunks).strip()
        self._process = None

        for p in _temp_paths:
            try:
                os.remove(p)
            except OSError:
                pass

        if returncode != 0 or not os.path.exists(s.output_path):
            self.finished.emit(ExportResult(
                False, s.output_path,
                error=f"NVENC 导出失败 (exit={returncode}):\n{stderr_text}",
            ))
            return

        result = ExportResult(
            success=True, path=s.output_path,
            size_bytes=os.path.getsize(s.output_path),
            duration=total / c.fps,
        )
        self.finished.emit(result)

    # ── GIF ────────────────────────────────────────────

    def _build_gif_output(self, width: int, height: int):
        """构建 palettegen 与 paletteuse 显式连接的 GIF 滤镜图。
        在 split 前对 rawvideo 应用 fps 降采样，输入保持 compositor.fps，
        输出使用 settings.fps 确保总时长不变。"""
        s = self._settings
        source = ffmpeg.input(
            "pipe:", format="rawvideo", pix_fmt="rgba",
            s=f"{width}x{height}", r=self._compositor.fps,
        )
        downsampled = source.filter("fps", fps=s.fps, round="near")
        split = downsampled.filter_multi_output("split")
        palette = split[0].filter("palettegen", stats_mode="diff")
        gif_video = ffmpeg.filter(
            [split[1], palette], "paletteuse",
            dither="bayer", bayer_scale=5, diff_mode="rectangle",
        )
        return ffmpeg.output(
            gif_video, s.output_path,
            loop=0 if s.loop else -1,
        ).overwrite_output()

    def _export_gif(self):
        s = self._settings
        c = self._compositor
        src_w, src_h = c.width, c.height

        if s.width and s.height:
            w = min(s.width, src_w) if src_w > 0 else s.width
            h = min(s.height, src_h) if src_h > 0 else s.height
        else:
            dims = calculate_export_dimensions(
                src_w, src_h, s.aspect_ratio, quality=s.quality,
                max_height=s.max_height)
            w, h = dims.width, dims.height

        if s.crop_region and (s.crop_region.width < 1.0 or s.crop_region.height < 1.0):
            w = int(w * s.crop_region.width)
            h = int(h * s.crop_region.height)

        total = c.total_output_frames
        if total == 0:
            self.finished.emit(ExportResult(False, s.output_path,
                                            error="没有帧可以导出"))
            return

        process = self._build_gif_output(w, h).run_async(
            pipe_stdin=True, pipe_stderr=True)
        self._process = process
        stderr_thread, stderr_chunks = _start_stderr_reader(process)
        gif_cancelled = False
        try:
            for i, frame in enumerate(c.render_all()):
                if self._cancelled:
                    gif_cancelled = True
                    process.terminate()
                    self.finished.emit(ExportResult(False, s.output_path,
                                                    error="已取消"))
                    return
                if frame.size != (w, h):
                    frame = frame.resize((w, h), Image.LANCZOS)
                if frame.mode != "RGBA":
                    frame = frame.convert("RGBA")
                try:
                    process.stdin.write(frame.tobytes())
                except BrokenPipeError:
                    break
                self.progress.emit(int((i + 1) / total * 100))
            if not gif_cancelled:
                process.stdin.close()
                returncode = process.wait()
                stderr_thread.join(timeout=5)
                stderr_text = "".join(stderr_chunks)
                output_exists = os.path.exists(s.output_path) and os.path.getsize(s.output_path) > 0
                if returncode != 0 or not output_exists:
                    self.finished.emit(ExportResult(
                        False, s.output_path,
                        error=f"FFmpeg GIF 导出失败: {stderr_text.strip() or returncode}",
                    ))
                    return
                self.finished.emit(ExportResult(
                    success=True, path=s.output_path,
                    size_bytes=os.path.getsize(s.output_path),
                    duration=total / c.fps,
                ))
        finally:
            self._process = None
            if not gif_cancelled:
                stderr_thread.join(timeout=3)
            if gif_cancelled and os.path.exists(s.output_path):
                try:
                    os.remove(s.output_path)
                except OSError:
                    pass

    # ── 多音频混合 ─────────────────────────────────────────

    def _build_audio_filtergraph(self, audio_regions: list,
                                 orig_wav: str | None,
                                 samplerate: int,
                                 video_duration: float) -> str | None:
        """为每个额外音频区域构建 FFmpeg 滤镜链混合，返回临时混合 WAV 路径"""
        regions = [r for r in audio_regions if os.path.exists(r.audio_path)]
        if not regions and not orig_wav:
            return None
        regions.sort(key=lambda r: r.start_ms)

        cmd = ['ffmpeg', '-y']
        input_idx = 0

        if orig_wav:
            cmd.extend(['-i', orig_wav])
            input_idx += 1

        region_inputs = []
        for r in regions:
            cmd.extend(['-i', r.audio_path])
            region_inputs.append((input_idx, r))
            input_idx += 1

        parts = []
        mix_labels = []

        if orig_wav:
            video_clips = self._compositor._clips
            if video_clips:
                for clip_no, clip in enumerate(video_clips):
                    label = f'[v{clip_no}]'
                    source_end = clip.source_end if clip.source_end is not None else clip.source_start + (clip.end - clip.start)
                    chain = (
                        f'[0:a]atrim=start={clip.source_start}:end={source_end},'
                        'asetpts=PTS-STARTPTS'
                    )
                    if abs(clip.speed - 1.0) > 0.0001:
                        chain += f',{self._atempo_filter_text(clip.speed)}'
                    delay = round(clip.start * 1000)
                    chain += f',adelay={delay}|{delay}{label}'
                    parts.append(chain)
                    mix_labels.append(label)
            else:
                parts.append(
                    f'[0:a]atrim=duration={video_duration},'
                    'asetpts=PTS-STARTPTS[original]')
                mix_labels.append('[original]')

        for idx, r in region_inputs:
            delay = int(r.start_ms)
            label = f'[m{idx}]'
            source_start = r.source_start_ms / 1000.0
            source_end = (r.source_end_ms / 1000.0) if r.source_end_ms is not None else (r.end_ms / 1000.0)
            vol = f',volume={r.volume}' if r.volume != 1.0 else ''
            parts.append(
                f'[{idx}:a]atrim=start={source_start}:end={source_end},'
                f'asetpts=PTS-STARTPTS{vol},adelay={delay}|{delay}{label}')
            mix_labels.append(label)

        num_mix = len(mix_labels)
        mix_in = ''.join(mix_labels)
        parts.append(
            f'{mix_in}amix=inputs={num_mix}:duration=longest[mixed]')
        parts.append(
            f'[mixed]atrim=duration={video_duration},'
            'asetpts=PTS-STARTPTS[aout]')

        cmd.extend(['-filter_complex', ';'.join(parts)])
        cmd.extend(['-map', '[aout]'])
        cmd.extend(['-ac', '2', '-ar', str(samplerate),
                     '-acodec', 'pcm_s16le'])

        fd, out_path = tempfile.mkstemp(suffix='_mixed.wav')
        os.close(fd)
        cmd.append(out_path)

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='replace')
            logger.debug("音频混合失败: {stderr.strip()}")
            try:
                os.remove(out_path)
            except OSError:
                pass
            return None

        return out_path

    @staticmethod
    def _atempo_filter_text(speed: float) -> str:
        factors = []
        remaining = speed
        while remaining > 2.0:
            factors.append(2.0)
            remaining /= 2.0
        while remaining < 0.5:
            factors.append(0.5)
            remaining /= 0.5
        factors.append(remaining)
        return ','.join(f'atempo={factor:g}' for factor in factors)

    # ── 工具 ────────────────────────────────────────────

    @staticmethod
    def _apply_atempo(audio_input, speed: float):
        """对音频输入应用 atempo 滤镜，支持 0.5-2.0 范围，超出则链式处理"""
        if speed <= 0:
            return audio_input
        # atempo 仅支持 0.5-2.0
        if 0.5 <= speed <= 2.0:
            return audio_input.filter("atempo", str(speed))
        # > 2.0: 链式 atempo（2.0 * 2.0 * ...）
        remaining = speed
        chained = audio_input
        while remaining > 2.0:
            chained = chained.filter("atempo", "2.0")
            remaining /= 2.0
        if remaining >= 0.5:
            chained = chained.filter("atempo", f"{remaining:.6f}")
        return chained

    @staticmethod
    def _save_temp_wav(audio: np.ndarray, samplerate: int) -> str:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
            wf.writeframes(int16.tobytes())
        return path
