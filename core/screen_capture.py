"""屏幕录制引擎 — 基于 mss"""

import mss
import numpy as np
from threading import Thread, Event
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class CapturedFrame:
    data: np.ndarray
    timestamp: float
    index: int


class ScreenCapture(Thread):
    """基于 mss 的跨平台屏幕录制"""

    def __init__(self, monitor_id: int = 1, target_fps: int = 30):
        super().__init__(daemon=True)
        self.monitor_id = monitor_id
        self.interval = 1.0 / target_fps
        self._stop = Event()
        self._buffer: deque[CapturedFrame] = deque(maxlen=600)
        self._frame_index = 0

    def run(self):
        with mss.mss() as sct:
            monitor = sct.monitors[self.monitor_id]
            while not self._stop.is_set():
                t0 = time.perf_counter()
                raw = sct.grab(monitor)
                # mss 返回 BGRA, 转 RGB
                arr = np.array(raw, dtype=np.uint8)
                rgb = arr[:, :, :3][:, :, ::-1]  # BGR → RGB (直接反转通道)
                self._buffer.append(CapturedFrame(
                    data=rgb,
                    timestamp=t0,
                    index=self._frame_index,
                ))
                self._frame_index += 1
                elapsed = time.perf_counter() - t0
                sleep_time = self.interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def stop(self):
        self._stop.set()
        self.join(timeout=5)

    @property
    def latest_frame(self) -> CapturedFrame | None:
        if self._buffer:
            return self._buffer[-1]
        return None

    @property
    def all_frames(self) -> list[CapturedFrame]:
        return list(self._buffer)

    def clear(self):
        self._buffer.clear()
        self._frame_index = 0
