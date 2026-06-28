"""FFmpeg 导出引擎"""

import os
import tempfile
import wave
import numpy as np
from dataclasses import dataclass
from PIL import Image
import ffmpeg

from PyQt5.QtCore import QObject, QThread, pyqtSignal

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
        w = s.width or c.width
        h = s.height or c.height
        total = len(c._frames)
        if total == 0:
            self.finished.emit(ExportResult(False, s.output_path,
                                            error="没有帧可以导出"))
            return

        video = ffmpeg.input("pipe:", format="rawvideo",
                             pix_fmt="rgba", s=f"{w}x{h}", r=s.fps)

        audio_data = self._audio_data
        if audio_data is not None and len(audio_data) > 0:
            audio_path = self._save_temp_wav(audio_data, s.samplerate)
            audio_input = ffmpeg.input(audio_path)
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
            if s.width and s.height:
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

        self._process.stdin.close()
        self._process.wait()
        self._process = None

        if audio_data is not None and len(audio_data) > 0:
            try:
                os.remove(audio_path)
            except OSError:
                pass

        result = ExportResult(
            success=True, path=s.output_path,
            size_bytes=os.path.getsize(s.output_path),
            duration=total / s.fps,
        )
        self.finished.emit(result)

    # ── GIF ────────────────────────────────────────────

    def _export_gif(self):
        s = self._settings
        c = self._compositor
        w = s.width or c.width
        h = s.height or c.height
        total = len(c._frames)
        if total == 0:
            self.finished.emit(ExportResult(False, s.output_path,
                                            error="没有帧可以导出"))
            return

        palette_file = tempfile.mktemp(suffix=".png")

        pass1 = (
            ffmpeg.input("pipe:", format="rawvideo",
                         pix_fmt="rgba", s=f"{w}x{h}", r=s.fps)
            .output(palette_file, vf="palettegen", r=s.fps)
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )
        for i, frame in enumerate(c.render_all()):
            if self._cancelled:
                pass1.terminate()
                os.remove(palette_file)
                self.finished.emit(ExportResult(False, s.output_path,
                                                error="已取消"))
                return
            try:
                pass1.stdin.write(frame.tobytes())
            except BrokenPipeError:
                pass1.wait()
                self.finished.emit(ExportResult(False, s.output_path,
                                                error="FFmpeg palettegen 管道断开"))
                return
        pass1.stdin.close()
        pass1.wait()

        pass2 = (
            ffmpeg.input("pipe:", format="rawvideo",
                         pix_fmt="rgba", s=f"{w}x{h}", r=s.fps)
            .output(s.output_path,
                    vf="paletteuse=dither=bayer:bayer_scale=5",
                    r=s.fps)
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )
        for i, frame in enumerate(c.render_all()):
            if self._cancelled:
                pass2.terminate()
                os.remove(palette_file)
                self.finished.emit(ExportResult(False, s.output_path,
                                                error="已取消"))
                return
            try:
                pass2.stdin.write(frame.tobytes())
            except BrokenPipeError:
                pass2.wait()
                self.finished.emit(ExportResult(False, s.output_path,
                                                error="FFmpeg paletteuse 管道断开"))
                return
            self.progress.emit(int((i + 1) / total * 100))
        pass2.stdin.close()
        pass2.wait()

        try:
            os.remove(palette_file)
        except OSError:
            pass

        result = ExportResult(
            success=True, path=s.output_path,
            size_bytes=os.path.getsize(s.output_path),
            duration=total / s.fps,
        )
        self.finished.emit(result)

    # ── 工具 ────────────────────────────────────────────

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
