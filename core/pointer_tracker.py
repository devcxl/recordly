"""光标追踪引擎 — 基于 pynput"""

from pynput import mouse
from dataclasses import dataclass, field
import time
import bisect
from threading import Lock
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
        # listener 线程（在途回调）与主线程（停止/归一化/读取）之间的互斥锁
        self._lock = Lock()

    def start(self):
        with self._lock:
            self._events.clear()
        self._listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._listener.start()

    def _on_move(self, x, y):
        self._current_pos = (x, y)
        with self._lock:
            self._events.append(CursorEvent(
                timestamp=time.time(), x=x, y=y, event_type="move"))

    def _on_click(self, x, y, button, pressed):
        with self._lock:
            self._events.append(CursorEvent(
                timestamp=time.time(), x=x, y=y, event_type="click",
                button=str(button), pressed=pressed))
        if self._on_click_callback:
            self._on_click_callback(x, y, str(button), pressed)

    def _on_scroll(self, x, y, dx, dy):
        with self._lock:
            self._events.append(CursorEvent(
                timestamp=time.time(), x=x, y=y, event_type="scroll"))

    def stop(self):
        """停止监听并等待 listener 线程退出（防止在途回调继续写事件）。"""
        if self._listener:
            self._listener.stop()
            try:
                self._listener.wait(5)
            except TypeError:
                self._listener.wait()
            self._listener = None

    @property
    def events(self) -> list[CursorEvent]:
        """事件快照（listener 线程并发写入时也安全）。"""
        with self._lock:
            return list(self._events)

    @property
    def current_position(self) -> tuple[int, int]:
        return self._current_pos

    def normalize_timestamps(self, perf_start: float, wall_start: float):
        """把事件时间戳从 time.time() 基准换算到 time.perf_counter() 基准。

        锁内遍历改写，listener 在途回调（若有）会被阻塞直到换算完成，
        消除 "list changed size during iteration" 风险。
        """
        with self._lock:
            for e in self._events:
                e.timestamp = perf_start + (e.timestamp - wall_start)

    # ── 查询（内部基于事件快照，监听线程并发写入安全） ──

    def _snapshot(self) -> list[CursorEvent]:
        with self._lock:
            return list(self._events)

    def get_at(self, ts: float) -> CursorEvent:
        """按时间戳线性插值获取光标状态"""
        events = self._snapshot()
        if not events:
            return CursorEvent(ts, 0, 0, "idle")
        times = [e.timestamp for e in events]
        idx = bisect.bisect_left(times, ts)

        if idx == 0:
            e = events[0]
            return CursorEvent(ts, e.x, e.y, e.event_type)
        if idx >= len(events):
            e = events[-1]
            return CursorEvent(ts, e.x, e.y, e.event_type)

        e0 = events[idx - 1]
        e1 = events[idx]
        if e1.timestamp == e0.timestamp:
            return CursorEvent(ts, e1.x, e1.y, e1.event_type)
        t = (ts - e0.timestamp) / (e1.timestamp - e0.timestamp)
        x = int(e0.x + (e1.x - e0.x) * t)
        y = int(e0.y + (e1.y - e0.y) * t)
        return CursorEvent(ts, x, y, e0.event_type)

    def get_clicks(self) -> list[CursorEvent]:
        """获取所有按下事件"""
        events = self._snapshot()
        return [e for e in events
                if e.event_type == "click" and e.pressed]

    def set_click_callback(self, cb: Callable):
        self._on_click_callback = cb
