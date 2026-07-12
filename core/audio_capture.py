"""音频录制引擎 — 麦克风 (sounddevice) + 系统音频 (FFmpeg)"""

import sys
import time
import subprocess
import threading
import numpy as np
import sounddevice as sd
from dataclasses import dataclass
from app.constants import DEFAULT_SAMPLE_RATE, DEFAULT_AUDIO_CHANNELS


@dataclass
class AudioResult:
    data: np.ndarray
    samplerate: int
    channels: int


def mix_audio_results(*results: AudioResult | None) -> AudioResult | None:
    """将同采样率的音频统一为立体声后混合，短轨道以静音补齐。"""
    valid = [r for r in results if r is not None and len(r.data) > 0]
    if not valid:
        return next((r for r in results if r is not None), None)

    samplerate = valid[0].samplerate
    if any(r.samplerate != samplerate for r in valid):
        raise ValueError("音频采样率不一致，无法直接混合")

    target_channels = max(2, *(r.channels for r in valid))
    target_frames = max(len(r.data) for r in valid)
    mixed = np.zeros((target_frames, target_channels), dtype=np.float32)

    for result in valid:
        data = np.asarray(result.data, dtype=np.float32)
        if data.ndim == 1:
            data = data.reshape(-1, result.channels)
        if data.shape[1] == 1 and target_channels > 1:
            data = np.repeat(data, target_channels, axis=1)
        mixed[:len(data), :data.shape[1]] += data

    np.clip(mixed, -1.0, 1.0, out=mixed)
    return AudioResult(mixed, samplerate, target_channels)


class MicrophoneCapture:
    """麦克风录制"""

    def __init__(self, samplerate: int = DEFAULT_SAMPLE_RATE,
                 channels: int = DEFAULT_AUDIO_CHANNELS):
        self.samplerate = samplerate
        self.channels = channels
        self._buffer: list[np.ndarray] = []
        self._stream = None
        self._active_channels = channels

    def start(self):
        self._buffer.clear()

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[mic] {status}", file=sys.stderr)
            self._buffer.append(indata.copy())

        def open_stream(channels: int):
            stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=channels,
                callback=callback,
            )
            try:
                stream.start()
            except Exception:
                try:
                    stream.close()
                except Exception:
                    pass
                raise
            return stream

        try:
            self._stream = open_stream(self.channels)
            self._active_channels = self.channels
        except Exception as first_error:
            if self.channels <= 1:
                raise RuntimeError(f"麦克风启动失败: {first_error}") from first_error
            try:
                self._stream = open_stream(1)
                self._active_channels = 1
            except Exception as mono_error:
                raise RuntimeError(f"麦克风启动失败: {mono_error}") from mono_error

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
                           channels=self._active_channels)


class SystemAudioCapture:
    """系统音频录制，平台分叉但对外接口统一"""

    def __init__(self, samplerate: int = DEFAULT_SAMPLE_RATE):
        self.samplerate = samplerate
        self._process = None
        self._buffer = []
        self._thread = None
        self._stderr = b""
        self.error: BaseException | None = None
        self.channels = 2

    def start(self):
        self._buffer.clear()
        self._stderr = b""
        self.error = None
        try:
            cmd = self._build_cmd()
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (OSError, RuntimeError) as exc:
            self.error = exc
            self._process = None
            return False
        self._thread = threading.Thread(
            target=self._read_loop, args=(self._process,), daemon=True)
        self._thread.start()
        return True

    def _build_cmd(self) -> list[str]:
        if sys.platform == "win32":
            return [
                "ffmpeg", "-nostdin", "-loglevel", "error",
                "-f", "dshow", "-i", "audio=virtual-audio-capturer",
                "-ac", "2", "-ar", str(self.samplerate),
                "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1",
            ]
        elif sys.platform == "linux":
            return [
                "ffmpeg", "-nostdin", "-loglevel", "error",
                "-f", "pulse", "-i", "@DEFAULT_MONITOR@",
                "-ac", "2", "-ar", str(self.samplerate),
                "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1",
            ]
        else:
            raise RuntimeError(f"系统音频录制暂不支持 {sys.platform}")

    def _read_loop(self, process):
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            self._buffer.append(chunk)

    def stop(self) -> AudioResult | None:
        process = self._process
        if process:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if self._thread:
            self._thread.join(timeout=3)
        if process and process.stderr:
            self._stderr = process.stderr.read()
        self._process = None
        self._thread = None
        if not self._buffer:
            if self._stderr and self.error is None:
                message = self._stderr.decode("utf-8", errors="replace").strip()
                if message:
                    self.error = RuntimeError(message)
            return None
        raw = b"".join(self._buffer)
        sample_width = np.dtype(np.int16).itemsize * self.channels
        usable = len(raw) - (len(raw) % sample_width)
        data = np.frombuffer(raw[:usable], dtype=np.int16).astype(np.float32) / 32768.0
        data = data.reshape(-1, self.channels)
        return AudioResult(data=data, samplerate=self.samplerate,
                           channels=self.channels)
