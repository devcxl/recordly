"""Tests for core/screen_capture.py — 匹配实际 API"""

import numpy as np
import pytest


class TestCapturedFrame:
    def test_importable(self):
        from core.screen_capture import CapturedFrame
        assert CapturedFrame is not None

    def test_create_frame(self):
        from core.screen_capture import CapturedFrame
        data = np.zeros((480, 640, 3), dtype=np.uint8)
        frame = CapturedFrame(data=data, timestamp=123.45, index=0)
        assert frame.data.shape == (480, 640, 3)
        assert frame.timestamp == 123.45
        assert frame.index == 0

    def test_frame_index(self):
        from core.screen_capture import CapturedFrame
        frame = CapturedFrame(data=np.zeros((100, 100, 3), dtype=np.uint8),
                              timestamp=1.0, index=5)
        assert frame.index == 5


class TestScreenCapture:
    def test_importable(self):
        from core.screen_capture import ScreenCapture
        assert ScreenCapture is not None

    def test_default_params(self):
        from core.screen_capture import ScreenCapture
        sc = ScreenCapture()
        assert sc.monitor_id == 1
        assert sc.daemon is True
        assert sc.latest_frame is None  # 未启动时返回 None
        assert callable(sc.clear)

    def test_custom_monitor(self):
        from core.screen_capture import ScreenCapture
        sc = ScreenCapture(monitor_id=2)
        assert sc.monitor_id == 2

    def test_fps_param(self):
        from core.screen_capture import ScreenCapture
        sc = ScreenCapture(target_fps=60)
        assert sc.interval == pytest.approx(1.0 / 60)

    def test_latest_frame_empty(self):
        from core.screen_capture import ScreenCapture
        sc = ScreenCapture()
        assert sc.latest_frame is None  # 未启动时返回 None

    def test_clear(self):
        from core.screen_capture import ScreenCapture
        sc = ScreenCapture()
        sc.clear()  # should not raise
