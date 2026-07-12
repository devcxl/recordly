"""录制控制器 — 协调各录制引擎"""

import time

from core.screen_capture import ScreenCapture
from core.audio_capture import (
    MicrophoneCapture,
    SystemAudioCapture,
    mix_audio_results,
)
from core.pointer_tracker import PointerTracker
from app.constants import DEFAULT_FPS


class Recorder:
    """协调屏幕录制、音频、鼠标追踪的顶层控制器"""

    def __init__(self, target_fps: int = DEFAULT_FPS):
        self.target_fps = max(1, int(target_fps))
        self.screen = ScreenCapture(
            monitor_id=1, target_fps=self.target_fps)
        self.mic = MicrophoneCapture()
        self.system_audio = SystemAudioCapture()
        self.pointer = PointerTracker()
        self._recording = False
        self._screen_session_started = False
        self._perf_start = 0.0
        self._wall_start = 0.0

    def set_target_fps(self, target_fps: int):
        if self._recording:
            raise RuntimeError("录制过程中不能修改帧率")
        self.target_fps = max(1, int(target_fps))
        if not self._screen_session_started:
            self.screen = ScreenCapture(
                monitor_id=self.screen.monitor_id,
                target_fps=self.target_fps,
            )

    def start_recording(self):
        if self._recording:
            return
        if self._screen_session_started:
            self.screen = ScreenCapture(
                monitor_id=self.screen.monitor_id,
                target_fps=self.target_fps,
            )
        self._recording = True
        self._perf_start = time.perf_counter()
        self._wall_start = time.time()
        self.screen.clear()
        try:
            self.screen.start()
            self._screen_session_started = True
            self.mic.start()
            self.system_audio.start()
            self.pointer.start()
        except Exception:
            self._recording = False
            try:
                self.mic.stop()
            finally:
                self.system_audio.stop()
                self.screen.stop()
            raise
        print("[recorder] 录制开始")

    def stop_recording(self):
        if not self._recording:
            return None
        self._recording = False
        self.pointer.stop()
        mic_audio = self.mic.stop()
        system_audio = self.system_audio.stop()
        self.screen.stop()
        print(f"[recorder] 录制结束")

        if self.screen.error is not None:
            raise RuntimeError(f"屏幕采集失败: {self.screen.error}") from self.screen.error

        # 统一时间基准：光标事件从 time.time() 转换到 time.perf_counter()
        for e in self.pointer._events:
            e.timestamp = self._perf_start + (e.timestamp - self._wall_start)

        mixed_audio = mix_audio_results(mic_audio, system_audio)

        return {
            "frames": self.screen.all_frames,
            "audio": mixed_audio,
            "mic_audio": mic_audio,
            "system_audio": system_audio,
            "cursor_events": self.pointer.events,
            "clicks": self.pointer.get_clicks(),
            "fps": self.target_fps,
            "width": 0,
            "height": 0,
            "monitor_offset": self.screen.monitor_offset,
        }
