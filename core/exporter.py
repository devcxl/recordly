"""FFmpeg 导出引擎"""

import logging
import os
import subprocess
import tempfile
import threading
import wave
import numpy as np
from dataclasses import dataclass
from PIL import Image
import ffmpeg

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from core.compositor import Compositor
from core.aspect_ratio import calculate_export_dimensions, calculate_fill_crop_region
from core.audio_mix import compose_audio

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
             "-c:v", "h264_nvenc", "-b:v", "1M",
             "-f", "null", "-"],
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
    audio_regions: list | None = None  # list[AudioRegion]，全部音频区域（含内置轨）
    crop_region: 'CropRegion | None' = None
    fill_crop_ratio: str | None = None  # crop-to-fill 目标比例（如 "16:9"），与 crop_region 互斥，物化时优先


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
                 settings: ExportSettings):
        super().__init__()
        self._compositor = compositor
        self._settings = settings
        self._cancelled = False
        self._process = None
        # 导出产生的临时 WAV 路径，统一在 run() finally 清理（含取消/断管/异常路径）
        self._temp_wavs: list[str] = []

    def cancel(self):
        self._cancelled = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def run(self):
        # fill_crop_ratio → 物化为 crop_region（复用现有裁剪渲染与尺寸计算路径），
        # 导出结束后恢复 compositor 原状态（settings 用完即弃无需恢复）
        restored_crop = None
        s = self._settings
        if s.fill_crop_ratio:
            region = calculate_fill_crop_region(
                self._compositor.width, self._compositor.height,
                s.fill_crop_ratio)
            if region is not None:
                restored_crop = self._compositor.crop_region
                s.crop_region = region
                self._compositor.set_crop(region)
        try:
            if s.format == "gif":
                self._export_gif()
            else:
                self._export_mp4()
        except Exception as exc:
            self.finished.emit(ExportResult(False, s.output_path,
                                            error=f"导出异常: {exc}"))
        finally:
            if restored_crop is not None:
                self._compositor.set_crop(restored_crop)
            # 无论成功/取消/断管/异常，都删除本次导出产生的临时 WAV
            self._cleanup_temp_wavs()

    def _cleanup_temp_wavs(self):
        """删除本次导出产生的所有临时 WAV（不抛错）。"""
        for path in self._temp_wavs:
            try:
                os.remove(path)
            except OSError:
                pass
        self._temp_wavs.clear()

    @staticmethod
    def _compose_and_encode(compositor, raw_frame, index, ts,
                            target_w, target_h, pix_fmt, direct_output):
        if raw_frame is None:
            size = ((target_w, target_h) if direct_output
                    else (compositor.width, compositor.height))
            color = (0, 0, 0, 255) if pix_fmt == "RGBA" else 0
            return index, Image.new(pix_fmt, size, color), None
        img, ctx = compositor.prepare_frame(
            raw_frame,
            ts,
            output_size=(target_w, target_h) if direct_output else None,
            output_mode=pix_fmt if direct_output else None,
            frame_index=index,
        )
        return index, img, ctx

    def _stream_frames_parallel(self, total, w, h, pix_fmt,
                                stderr_thread, stderr_chunks,
                                render_fps, direct_output):
        from concurrent.futures import (
            FIRST_COMPLETED, ThreadPoolExecutor, wait,
        )

        max_workers = min(os.cpu_count() or 4, 8)
        reorder_max_bytes = 256 * 1024 * 1024
        c = self._compositor
        bytes_per_frame = (
            w * h * (4 if pix_fmt == "RGBA" else 3)
            if direct_output else c.width * c.height * 4
        )
        pending_limit = min(
            max_workers * 2,
            max(1, reorder_max_bytes // max(bytes_per_frame, 1)),
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            pending = set()
            ready = {}
            next_to_write = 0
            frame_iter = c.iter_frame_meta(render_fps=render_fps)
            exhausted = False

            def submit_one():
                nonlocal exhausted
                try:
                    idx, raw_frame, ts = next(frame_iter)
                except StopIteration:
                    exhausted = True
                    return False
                pending.add(executor.submit(
                    self._compose_and_encode, c, raw_frame, idx, ts,
                    w, h, pix_fmt, direct_output))
                return True

            while len(pending) < pending_limit and submit_one():
                pass

            while pending or ready:
                if pending:
                    completed, pending = wait(
                        pending, return_when=FIRST_COMPLETED)
                    for future in completed:
                        result = future.result()
                        ready[result[0]] = result[1:]

                if self._cancelled:
                    for future in pending:
                        future.cancel()
                    self._process.terminate()
                    self.finished.emit(ExportResult(
                        False, self._settings.output_path, error="已取消"))
                    return False

                while next_to_write in ready:
                    prepared = ready.pop(next_to_write)
                    if len(prepared) == 1 and isinstance(
                            prepared[0], (bytes, bytearray)):
                        data = prepared[0]
                    else:
                        img, ctx = prepared
                        if ctx is not None:
                            img = c.apply_effects(
                                img, ctx,
                                output_mode=pix_fmt if direct_output else None,
                            )
                        if img.size != (w, h):
                            img = img.resize((w, h), Image.LANCZOS)
                        if img.mode != pix_fmt:
                            img = img.convert(pix_fmt)
                        data = img.tobytes()
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
                    next_to_write += 1
                    self.progress.emit(int(next_to_write / total * 100))

                if (exhausted and not pending and ready
                        and next_to_write not in ready):
                    self._process.terminate()
                    raise RuntimeError(
                        f"导出帧序列缺少第 {next_to_write} 帧")

                ready_bytes = len(ready) * bytes_per_frame
                while (not exhausted
                       and len(pending) < pending_limit
                       and ready_bytes < reorder_max_bytes):
                    if not submit_one():
                        break

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

        total = c.total_output_frames_for(s.fps)
        if total == 0:
            self.finished.emit(ExportResult(False, s.output_path,
                                            error="没有帧可以导出"))
            return

        video = ffmpeg.input("pipe:", format="rawvideo",
                              pix_fmt="rgb24", s=f"{w}x{h}", r=s.fps)

        # ── 速度滤镜 ────────────────────────────────────────
        # ── 音频处理 ────────────────────────────────────────
        # 临时 WAV 统一注册到 self._temp_wavs，由 run() finally 清理

        # 1) 按音频区域列表内存合成时间轴音频（替代旧 orig_wav + amix 链路）
        video_duration = total / s.fps
        regions = [r for r in (s.audio_regions or [])
                   if os.path.exists(r.audio_path)]
        mixed = compose_audio(regions, s.samplerate, video_duration)

        # 2) 确定最终音频输入并构建 output
        final_wav = None
        if mixed is not None:
            final_wav = self._save_temp_wav(mixed, s.samplerate)
            self._temp_wavs.append(final_wav)
        if final_wav:
            audio_input = ffmpeg.input(final_wav)

            # 音频已由 compose_audio 按 region 定位/变速语义合成，独立于视频轨
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
            logger.debug(f"帧数={total} 尺寸={w}x{h} fps={s.fps}")

        direct_output = (
            src_w * h == src_h * w
            and not (s.crop_region and (
                s.crop_region.width < 1.0 or s.crop_region.height < 1.0))
        )
        if not self._stream_frames_parallel(
                total, w, h, "RGB", stderr_thread, stderr_chunks,
                render_fps=s.fps, direct_output=direct_output):
            return

        process = self._process
        process.stdin.close()
        returncode = process.wait()
        stderr_thread.join(timeout=2)
        stderr_text = "".join(stderr_chunks).strip()
        self._process = None

        if returncode != 0 or not os.path.exists(s.output_path):
            self.finished.emit(ExportResult(
                False, s.output_path,
                error=f"FFmpeg 导出失败 (exit={returncode}):\n{stderr_text}",
            ))
            return

        result = ExportResult(
            success=True, path=s.output_path,
            size_bytes=os.path.getsize(s.output_path),
            duration=total / s.fps,
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

        total = c.total_output_frames_for(s.fps)
        if total == 0:
            self.finished.emit(ExportResult(False, s.output_path,
                                            error="没有帧可以导出"))
            return

        # 音频处理（与 CPU 路径共用 compose_audio 合成语义）
        video_duration = total / s.fps
        regions = [r for r in (s.audio_regions or [])
                   if os.path.exists(r.audio_path)]
        mixed = compose_audio(regions, s.samplerate, video_duration)

        final_wav = None
        if mixed is not None:
            final_wav = self._save_temp_wav(mixed, s.samplerate)
            self._temp_wavs.append(final_wav)

        # RGB 管道避免合成后再做整帧 RGBA 转换。
        video = ffmpeg.input("pipe:", format="rawvideo",
                              pix_fmt="rgb24", s=f"{w}x{h}", r=s.fps)

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

        direct_output = (
            src_w * h == src_h * w
            and not (s.crop_region and (
                s.crop_region.width < 1.0 or s.crop_region.height < 1.0))
        )
        if not self._stream_frames_parallel(
                total, w, h, "RGB", stderr_thread, stderr_chunks,
                render_fps=s.fps, direct_output=direct_output):
            return

        process = self._process
        process.stdin.close()
        returncode = process.wait()
        stderr_thread.join(timeout=2)
        stderr_text = "".join(stderr_chunks).strip()
        self._process = None

        if returncode != 0 or not os.path.exists(s.output_path):
            self.finished.emit(ExportResult(
                False, s.output_path,
                error=f"NVENC 导出失败 (exit={returncode}):\n{stderr_text}",
            ))
            return

        result = ExportResult(
            success=True, path=s.output_path,
            size_bytes=os.path.getsize(s.output_path),
            duration=total / s.fps,
        )
        self.finished.emit(result)

    # ── GIF ────────────────────────────────────────────

    def _build_gif_output(self, width: int, height: int):
        """构建 palettegen 与 paletteuse 显式连接的 GIF 滤镜图。"""
        s = self._settings
        source = ffmpeg.input(
            "pipe:", format="rawvideo", pix_fmt="rgb24",
            s=f"{width}x{height}", r=s.fps,
        )
        split = source.filter_multi_output("split")
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

        total = c.total_output_frames_for(s.fps)
        if total == 0:
            self.finished.emit(ExportResult(False, s.output_path,
                                            error="没有帧可以导出"))
            return

        process = self._build_gif_output(w, h).run_async(
            pipe_stdin=True, pipe_stderr=True)
        self._process = process
        stderr_thread, stderr_chunks = _start_stderr_reader(process)
        try:
            direct_output = (
                src_w * h == src_h * w
                and not (s.crop_region and (
                    s.crop_region.width < 1.0
                    or s.crop_region.height < 1.0))
            )
            if not self._stream_frames_parallel(
                    total, w, h, "RGB", stderr_thread, stderr_chunks,
                    render_fps=s.fps, direct_output=direct_output):
                return
            process.stdin.close()
            returncode = process.wait()
            stderr_thread.join(timeout=5)
            stderr_text = "".join(stderr_chunks)
            output_exists = (
                os.path.exists(s.output_path)
                and os.path.getsize(s.output_path) > 0)
            if returncode != 0 or not output_exists:
                self.finished.emit(ExportResult(
                    False, s.output_path,
                    error=("FFmpeg GIF 导出失败: "
                           f"{stderr_text.strip() or returncode}"),
                ))
                return
            self.finished.emit(ExportResult(
                success=True, path=s.output_path,
                size_bytes=os.path.getsize(s.output_path),
                duration=total / s.fps,
            ))
        finally:
            self._process = None
            stderr_thread.join(timeout=3)
            if self._cancelled and os.path.exists(s.output_path):
                try:
                    os.remove(s.output_path)
                except OSError:
                    pass

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
        """保存临时 WAV。声道数按数组形状推断：2D (N,C) → C 声道，1D → 单声道。"""
        channels = audio.shape[1] if audio.ndim == 2 else 1
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
            wf.writeframes(int16.tobytes())
        return path
