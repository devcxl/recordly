"""音频录制引擎 — 麦克风 (sounddevice) + 系统音频 (FFmpeg)"""

import sys
import time
import subprocess
import threading
import wave
import io
import numpy as np
import sounddevice as sd
from dataclasses import dataclass
from app.constants import DEFAULT_SAMPLE_RATE, DEFAULT_AUDIO_CHANNELS


@dataclass
class AudioResult:
    data: np.ndarray
    samplerate: int
    channels: int


class MicrophoneCapture:
    """麦克风录制"""

    def __init__(self, samplerate: int = DEFAULT_SAMPLE_RATE,
                 channels: int = DEFAULT_AUDIO_CHANNELS):
        self.samplerate = samplerate
        self.channels = channels
        self._buffer: list[np.ndarray] = []
        self._stream = None

    def start(self):
        self._buffer.clear()

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[mic] {status}", file=sys.stderr)
            self._buffer.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> AudioResult:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._buffer:
            data = np.concatenate(self._buffer, axis=0)
        else:
            data = np.array([], dtype=np.float32)
        return AudioResult(data=data, samplerate=self.samplerate,
                           channels=self.channels)


class SystemAudioCapture:
    """系统音频录制，平台分叉但对外接口统一"""

    def __init__(self, samplerate: int = DEFAULT_SAMPLE_RATE):
        self.samplerate = samplerate
        self._process = None
        self._buffer = []
        self._thread = None

    def start(self):
        self._buffer.clear()
        cmd = self._build_cmd()
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._thread = threading.Thread(
            target=self._read_loop, daemon=True)
        self._thread.start()

    def _build_cmd(self) -> list[str]:
        if sys.platform == "win32":
            return [
                "ffmpeg", "-f", "dshow", "-i", "audio=virtual-audio-capturer",
                "-ac", "2", "-ar", str(self.samplerate),
                "-f", "wav", "pipe:1",
            ]
        elif sys.platform == "linux":
            return [
                "ffmpeg", "-f", "pulse", "-i", "default.monitor",
                "-ac", "2", "-ar", str(self.samplerate),
                "-f", "wav", "pipe:1",
            ]
        else:
            raise RuntimeError(f"系统音频录制暂不支持 {sys.platform}")

    def _read_loop(self):
        while True:
            chunk = self._process.stdout.read(4096)
            if not chunk:
                break
            self._buffer.append(chunk)

    def stop(self) -> AudioResult | None:
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        if self._thread:
            self._thread.join(timeout=3)
        if not self._buffer:
            return None
        raw = b"".join(self._buffer)
        try:
            with wave.open(io.BytesIO(raw), "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                if wf.getnchannels() > 1:
                    data = data.reshape(-1, wf.getnchannels())
                return AudioResult(data=data, samplerate=wf.getframerate(),
                                   channels=wf.getnchannels())
        except Exception as e:
            print(f"[sysaudio] WAV 解析失败: {e}", file=sys.stderr)
            return None
