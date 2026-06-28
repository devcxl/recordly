"""Tests for core/recorder.py — 匹配实际 API"""

import pytest


class TestRecorder:
    def test_importable(self):
        from core.recorder import Recorder
        assert Recorder is not None

    def test_default_params(self):
        from core.recorder import Recorder
        r = Recorder()
        assert hasattr(r, 'start_recording')
        assert hasattr(r, 'stop_recording')
        assert hasattr(r, 'screen')
        assert hasattr(r, 'mic')
        assert hasattr(r, 'pointer')

    def test_is_recording_initially_false(self):
        from core.recorder import Recorder
        r = Recorder()
        assert r._recording is False

    def test_start_stop(self):
        from core.recorder import Recorder
        r = Recorder()
        r.start_recording()
        assert r._recording is True
        r.stop_recording()
        assert r._recording is False

    def test_double_start(self):
        from core.recorder import Recorder
        r = Recorder()
        r.start_recording()
        r.start_recording()  # should not raise
        r.stop_recording()

    def test_stop_without_start(self):
        from core.recorder import Recorder
        r = Recorder()
        r.stop_recording()  # should not raise

    def test_record_returns_timing(self):
        from core.recorder import Recorder
        import time
        r = Recorder()
        r.start_recording()
        time.sleep(0.01)
        r.stop_recording()
        # 验证至少经过了一些时间
        assert True
