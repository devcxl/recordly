"""MP4 导出实现 — ExportWorker 的方法扩展。"""

import logging
import os
import subprocess

import ffmpeg

from core.aspect_ratio import calculate_export_dimensions
from core.audio_mix import compose_audio
from core.export_ffmpeg import _start_stderr_reader, is_gpu_available
from core.export_models import ExportResult

logger = logging.getLogger(__name__)


class Mp4ExportMixin:
    """MP4（libx264 / NVENC）导出方法。"""

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
            logger.debug("ffmpeg " + " ".join(map(str, cmd)))
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

