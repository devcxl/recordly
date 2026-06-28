"""录制控制器 — 协调各录制引擎"""

import time
from threading import Event

from core.screen_capture import ScreenCapture
from core.audio_capture import MicrophoneCapture
from core.pointer_tracker import PointerTracker
from app.constants import DEFAULT_FPS


class Recorder:
    """协调屏幕录制、音频、鼠标追踪的顶层控制器"""

    def __init__(self):
        self.screen = ScreenCapture(monitor_id=1, target_fps=DEFAULT_FPS)
        self.mic = MicrophoneCapture()
        self.pointer = PointerTracker()
        self._recording = False

    def start_recording(self):
        if self._recording:
            return
        self._recording = True
        self.screen.clear()
        self.screen.start()
        self.mic.start()
        self.pointer.start()
        print("[recorder] 录制开始")

    def stop_recording(self):
        if not self._recording:
            return None
        self._recording = False
        self.pointer.stop()
        mic_audio = self.mic.stop()
        self.screen.stop()
        print(f"[recorder] 录制结束")

        return {
            "frames": self.screen.all_frames,
            "audio": mic_audio,
            "cursor_events": self.pointer.events,
            "clicks": self.pointer.get_clicks(),
            "fps": DEFAULT_FPS,
            "width": 0,  # 从 frames 中获取
            "height": 0,
        }
