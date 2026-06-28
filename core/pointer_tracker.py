"""光标追踪引擎 — 基于 pynput"""

from pynput import mouse
from dataclasses import dataclass, field
import time
import bisect
from typing import Callable


@dataclass(order=True)
class CursorEvent:
    timestamp: float
    x: int = field(compare=False)
    y: int = field(compare=False)
    event_type: str = field(compare=False, default="move")      # "move" / "click" / "scroll"
    button: str | None = field(compare=False, default=None)
    pressed: bool | None = field(compare=False, default=None)


class PointerTracker:
    """全局鼠标事件追踪，记录位置与点击"""

    def __init__(self):
        self._events: list[CursorEvent] = []
        self._current_pos = (0, 0)
        self._listener = None
        self._on_click_callback: Callable | None = None

    def start(self):
        self._events.clear()
        self._listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._listener.start()

    def _on_move(self, x, y):
        self._current_pos = (x, y)
        self._events.append(CursorEvent(
            timestamp=time.time(), x=x, y=y, event_type="move"))

    def _on_click(self, x, y, button, pressed):
        self._events.append(CursorEvent(
            timestamp=time.time(), x=x, y=y, event_type="click",
            button=str(button), pressed=pressed))
        if self._on_click_callback:
            self._on_click_callback(x, y, str(button), pressed)

    def _on_scroll(self, x, y, dx, dy):
        self._events.append(CursorEvent(
            timestamp=time.time(), x=x, y=y, event_type="scroll"))

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    @property
    def events(self) -> list[CursorEvent]:
        return list(self._events)

    @property
    def current_position(self) -> tuple[int, int]:
        return self._current_pos

    def get_at(self, ts: float) -> CursorEvent:
        """按时间戳线性插值获取光标状态"""
        if not self._events:
            return CursorEvent(ts, 0, 0, "idle")
        times = [e.timestamp for e in self._events]
        idx = bisect.bisect_left(times, ts)

        if idx == 0:
            e = self._events[0]
            return CursorEvent(ts, e.x, e.y, e.event_type)
        if idx >= len(self._events):
            e = self._events[-1]
            return CursorEvent(ts, e.x, e.y, e.event_type)

        e0 = self._events[idx - 1]
        e1 = self._events[idx]
        if e1.timestamp == e0.timestamp:
            return CursorEvent(ts, e1.x, e1.y, e1.event_type)
        t = (ts - e0.timestamp) / (e1.timestamp - e0.timestamp)
        x = int(e0.x + (e1.x - e0.x) * t)
        y = int(e0.y + (e1.y - e0.y) * t)
        return CursorEvent(ts, x, y, e0.event_type)

    def get_clicks(self) -> list[CursorEvent]:
        """获取所有按下事件"""
        return [e for e in self._events
                if e.event_type == "click" and e.pressed]

    def set_click_callback(self, cb: Callable):
        self._on_click_callback = cb
