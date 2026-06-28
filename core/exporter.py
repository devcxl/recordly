"""FFmpeg 导出引擎"""

import os
import tempfile
import wave
import numpy as np
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal
from PIL import Image
import ffmpeg

from core.compositor import Compositor


@dataclass
class ExportSettings:
    output_path: str
    format: str = "mp4"            # "mp4" / "gif"
    fps: int = 30
    bitrate: str = "10M"
    width: int = 0                 # 0 = 原始分辨率
    height: int = 0
    samplerate: int = 44100


@dataclass
class ExportResult:
    success: bool
    path: str
    duration: float = 0.0
    size_bytes: int = 0
    error: str | None = None


class Exporter(QObject):
    """FFmpeg 导出引擎，支持 MP4 和 GIF"""

    progress = pyqtSignal(int)          # 0–100
    finished = pyqtSignal(ExportResult)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False
        self._process = None

    def cancel(self):
        self._cancelled = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def export_mp4(self, compositor: Compositor,
                   audio_data: np.ndarray | None,
                   settings: ExportSettings):
        """导出 MP4 视频"""
        self._cancelled = False
        w = settings.width or compositor.width
        h = settings.height or compositor.height
        total = len(compositor._frames)
        if total == 0:
            self.finished.emit(ExportResult(False, settings.output_path,
                                            error="没有帧可以导出"))
            return

        # 构建 ffmpeg 命令
        video = ffmpeg.input("pipe:", format="rawvideo",
                             pix_fmt="rgba", s=f"{w}x{h}",
                             r=settings.fps)

        # 音频处理
        if audio_data is not None and len(audio_data) > 0:
            audio_path = self._save_temp_wav(audio_data, settings.samplerate)
            audio_input = ffmpeg.input(audio_path)
            output = ffmpeg.output(
                video, audio_input, settings.output_path,
                vcodec="libx264", pix_fmt="yuv420p",
                video_bitrate=settings.bitrate,
                acodec="aac", audio_bitrate="192k",
            )
        else:
            output = ffmpeg.output(
                video, settings.output_path,
                vcodec="libx264", pix_fmt="yuv420p",
                video_bitrate=settings.bitrate,
            )

        output = output.overwrite_output()
        self._process = output.run_async(pipe_stdin=True, pipe_stderr=True)

        for i, frame in enumerate(compositor.render_all()):
            if self._cancelled:
                self._process.terminate()
                self.finished.emit(ExportResult(False, settings.output_path,
                                                error="已取消"))
                return
            # 调整分辨率
            if settings.width and settings.height:
                frame = frame.resize((w, h), Image.LANCZOS)
            # 确保是 RGBA
            if frame.mode != "RGBA":
                frame = frame.convert("RGBA")
            self._process.stdin.write(frame.tobytes())
            self.progress.emit(int((i + 1) / total * 100))

        self._process.stdin.close()
        self._process.wait()
        self._process = None

        # 清理临时音频文件
        if audio_data is not None and len(audio_data) > 0:
            try:
                os.remove(audio_path)
            except OSError:
                pass

        result = ExportResult(
            success=True,
            path=settings.output_path,
            size_bytes=os.path.getsize(settings.output_path),
            duration=total / settings.fps,
        )
        self.finished.emit(result)

    def export_gif(self, compositor: Compositor, settings: ExportSettings):
        """导出 GIF（双 pass: palettegen + paletteuse）"""
        self._cancelled = False
        w = settings.width or compositor.width
        h = settings.height or compositor.height
        total = len(compositor._frames)
        if total == 0:
            self.finished.emit(ExportResult(False, settings.output_path,
                                            error="没有帧可以导出"))
            return

        palette_file = tempfile.mktemp(suffix=".png")

        # Pass 1: palettegen
        pass1 = (
            ffmpeg.input("pipe:", format="rawvideo",
                         pix_fmt="rgba", s=f"{w}x{h}",
                         r=settings.fps)
            .output(palette_file, vf="palettegen", r=settings.fps)
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )
        for i, frame in enumerate(compositor.render_all()):
            if self._cancelled:
                pass1.terminate()
                os.remove(palette_file)
                self.finished.emit(ExportResult(False, settings.output_path,
                                                error="已取消"))
                return
            pass1.stdin.write(frame.tobytes())
        pass1.stdin.close()
        pass1.wait()

        # Pass 2: paletteuse
        pass2 = (
            ffmpeg.input("pipe:", format="rawvideo",
                         pix_fmt="rgba", s=f"{w}x{h}",
                         r=settings.fps)
            .output(settings.output_path,
                    vf=f"paletteuse=dither=bayer:bayer_scale=5",
                    r=settings.fps)
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )
        for i, frame in enumerate(compositor.render_all()):
            if self._cancelled:
                pass2.terminate()
                os.remove(palette_file)
                self.finished.emit(ExportResult(False, settings.output_path,
                                                error="已取消"))
                return
            pass2.stdin.write(frame.tobytes())
            self.progress.emit(int((i + 1) / total * 100))
        pass2.stdin.close()
        pass2.wait()

        try:
            os.remove(palette_file)
        except OSError:
            pass

        result = ExportResult(
            success=True,
            path=settings.output_path,
            size_bytes=os.path.getsize(settings.output_path),
            duration=total / settings.fps,
        )
        self.finished.emit(result)

    @staticmethod
    def _save_temp_wav(audio: np.ndarray, samplerate: int) -> str:
        path = tempfile.mktemp(suffix=".wav")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            # float32 → int16
            int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
            wf.writeframes(int16.tobytes())
        return path
