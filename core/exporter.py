"""FFmpeg 导出引擎"""

import os
import subprocess
import tempfile
import wave
import numpy as np
from dataclasses import dataclass
from PIL import Image
import ffmpeg

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from core.compositor import Compositor
from core.aspect_ratio import calculate_export_dimensions


@dataclass
class ExportSettings:
    output_path: str
    format: str = "mp4"            # "mp4" / "gif"
    fps: int = 30
    bitrate: str = "10M"
    width: int = 0                 # 0 = 原始分辨率
    height: int = 0
    samplerate: int = 44100
    aspect_ratio: str = "native"
    quality: float = 1.0
    loop: bool = True              # GIF 是否循环
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
        if self._settings.format == "gif":
            self._export_gif()
        else:
            self._export_mp4()

    # ── MP4 ────────────────────────────────────────────

    def _export_mp4(self):
        s = self._settings
        c = self._compositor
        # 计算输出尺寸（宽高比/质量优先，explicit width/height 覆盖）
        if s.width and s.height:
            w, h = s.width, s.height
        else:
            dims = calculate_export_dimensions(
                c.width, c.height, s.aspect_ratio, quality=s.quality)
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
                             pix_fmt="rgba", s=f"{w}x{h}", r=s.fps)

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
                video_bitrate=s.bitrate,
                acodec="aac", audio_bitrate="192k",
            )
        else:
            output = ffmpeg.output(
                video, s.output_path,
                vcodec="libx264", pix_fmt="yuv420p",
                video_bitrate=s.bitrate,
            )

        output = output.overwrite_output()
        self._process = output.run_async(pipe_stdin=True, pipe_stderr=True)

        for i, frame in enumerate(c.render_all()):
            if self._cancelled:
                self._process.terminate()
                self.finished.emit(ExportResult(False, s.output_path,
                                                error="已取消"))
                return
            if frame.size != (w, h):
                frame = frame.resize((w, h), Image.LANCZOS)
            if frame.mode != "RGBA":
                frame = frame.convert("RGBA")
            try:
                self._process.stdin.write(frame.tobytes())
            except BrokenPipeError:
                stderr = self._process.stderr.read().decode("utf-8", errors="replace")
                self._process.wait()
                self._process = None
                self.finished.emit(ExportResult(False, s.output_path,
                                                error=f"FFmpeg 管道断开: {stderr.strip()}"))
                return
            self.progress.emit(int((i + 1) / total * 100))

        process = self._process
        process.stdin.close()
        returncode = process.wait()
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        self._process = None

        for p in _temp_paths:
            try:
                os.remove(p)
            except OSError:
                pass

        if returncode != 0 or not os.path.exists(s.output_path):
            self.finished.emit(ExportResult(
                False, s.output_path,
                error=f"FFmpeg 导出失败: {stderr.strip() or returncode}",
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
        """构建 palettegen 与 paletteuse 显式连接的 GIF 滤镜图。"""
        s = self._settings
        source = ffmpeg.input(
            "pipe:", format="rawvideo", pix_fmt="rgba",
            s=f"{width}x{height}", r=self._compositor.fps,
        )
        split = source.filter_multi_output("split")
        palette = split[0].filter("palettegen", stats_mode="diff")
        gif_video = ffmpeg.filter(
            [split[1], palette], "paletteuse",
            dither="bayer", bayer_scale=5, diff_mode="rectangle",
        )
        return ffmpeg.output(
            gif_video, s.output_path, r=s.fps,
            loop=0 if s.loop else -1,
        ).overwrite_output()

    def _export_gif(self):
        s = self._settings
        c = self._compositor
        if s.width and s.height:
            w, h = s.width, s.height
        else:
            dims = calculate_export_dimensions(
                c.width, c.height, s.aspect_ratio, quality=s.quality)
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
        for i, frame in enumerate(c.render_all()):
            if self._cancelled:
                process.terminate()
                self._process = None
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
                stderr = process.stderr.read().decode(
                    "utf-8", errors="replace")
                process.wait()
                self._process = None
                self.finished.emit(ExportResult(
                    False, s.output_path,
                    error=f"FFmpeg GIF 管道断开: {stderr.strip()}",
                ))
                return
            self.progress.emit(int((i + 1) / total * 100))

        process.stdin.close()
        returncode = process.wait()
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        self._process = None
        if returncode != 0 or not os.path.exists(s.output_path):
            self.finished.emit(ExportResult(
                False, s.output_path,
                error=f"FFmpeg GIF 导出失败: {stderr.strip() or returncode}",
            ))
            return

        self.finished.emit(ExportResult(
            success=True, path=s.output_path,
            size_bytes=os.path.getsize(s.output_path),
            duration=total / c.fps,
        ))

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
                    source_end = clip.source_end
                    if source_end is None:
                        source_end = clip.source_start + (
                            clip.end - clip.start) * clip.speed
                    label = f'[v{clip_no}]'
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
            source_end_ms = r.source_end_ms
            if source_end_ms is None:
                source_end_ms = r.source_start_ms + (r.end_ms - r.start_ms)
            source_end = source_end_ms / 1000.0
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

        out_path = tempfile.mktemp(suffix='_mixed.wav')
        cmd.append(out_path)

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='replace')
            print(f"[exporter] 音频混合失败: {stderr.strip()}")
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
        path = tempfile.mktemp(suffix=".wav")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
            wf.writeframes(int16.tobytes())
        return path
