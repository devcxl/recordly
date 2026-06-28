"""Tests for core/pointer_tracker.py"""

import time
import pytest

from core.pointer_tracker import CursorEvent, PointerTracker


class TestCursorEvent:
    def test_default_types(self):
        e = CursorEvent(timestamp=1.0, x=100, y=200)
        assert isinstance(e.timestamp, float)
        assert isinstance(e.x, int)
        assert isinstance(e.y, int)

    def test_order_by_timestamp(self):
        a = CursorEvent(1.0, 10, 20)
        b = CursorEvent(2.0, 30, 40)
        assert a < b

    def test_click_event(self):
        e = CursorEvent(timestamp=1.0, x=100, y=200,
                        event_type="click", button="left", pressed=True)
        assert e.event_type == "click"
        assert e.button == "left"
        assert e.pressed is True

    def test_scroll_event(self):
        e = CursorEvent(timestamp=1.0, x=0, y=0, event_type="scroll")
        assert e.event_type == "scroll"


class TestPointerTrackerData:
    """纯数据层测试 — 直接调用内部记录方法"""

    @pytest.fixture
    def tracker(self):
        return PointerTracker()

    def test_initial_state(self, tracker):
        assert tracker.events == []
        assert tracker.current_position == (0, 0)
        assert tracker.get_clicks() == []

    def test_on_move_records_event(self, tracker):
        tracker._on_move(100, 200)
        assert len(tracker.events) == 1
        assert tracker.events[0].x == 100
        assert tracker.events[0].y == 200
        assert tracker.events[0].event_type == "move"
        assert tracker.current_position == (100, 200)

    def test_on_click_records_event(self, tracker):
        tracker._on_click(150, 250, "left", True)
        assert len(tracker.events) == 1
        assert tracker.events[0].x == 150
        assert tracker.events[0].event_type == "click"
        assert tracker.events[0].pressed is True

    def test_on_scroll_records_event(self, tracker):
        tracker._on_scroll(0, 0, 0, -1)
        assert len(tracker.events) == 1
        assert tracker.events[0].event_type == "scroll"

    def test_multiple_events(self, tracker):
        tracker._on_move(10, 20)
        tracker._on_move(30, 40)
        tracker._on_move(50, 60)
        assert len(tracker.events) == 3

    def test_click_callback(self, tracker):
        cb_called = []
        tracker.set_click_callback(lambda x, y, b, p: cb_called.append((x, y, b, p)))
        tracker._on_click(200, 300, "right", True)
        assert len(cb_called) == 1
        assert cb_called[0] == (200, 300, "right", True)

    # ── 插值测试 ──────────────────────────────────────────

    def test_get_at_empty(self, tracker):
        result = tracker.get_at(time.time())
        assert isinstance(result, CursorEvent)
        assert result.event_type == "idle"

    def test_get_at_before_first(self, tracker):
        now = time.time()
        tracker._on_move(50, 50)
        result = tracker.get_at(now - 1)
        assert result.x == 50
        assert result.y == 50

    def test_get_at_after_last(self, tracker):
        now = time.time()
        tracker._on_move(50, 50)
        result = tracker.get_at(now + 10)
        assert result.x == 50
        assert result.y == 50

    def test_get_at_interpolated(self, tracker):
        """验证线性插值"""
        tracker._events = [
            CursorEvent(timestamp=1.0, x=0, y=0),
            CursorEvent(timestamp=3.0, x=100, y=100),
        ]
        result = tracker.get_at(2.0)
        assert result.x == 50
        assert result.y == 50

    def test_get_at_exact(self, tracker):
        tracker._events = [
            CursorEvent(timestamp=1.0, x=42, y=84),
        ]
        result = tracker.get_at(1.0)
        assert result.x == 42
        assert result.y == 84

    # ── 点击查询 ──────────────────────────────────────────

    def test_get_clicks_filters_press(self, tracker):
        tracker._events = [
            CursorEvent(1.0, 0, 0, "click", pressed=False),
            CursorEvent(2.0, 0, 0, "click", pressed=True),
            CursorEvent(3.0, 0, 0, "click", pressed=True),
            CursorEvent(4.0, 0, 0, "move"),
        ]
        clicks = tracker.get_clicks()
        assert len(clicks) == 2

    # ── 生命周期 ──────────────────────────────────────────

    def test_stop_without_start(self, tracker):
        """未 start 就 stop 不应报错"""
        tracker.stop()
