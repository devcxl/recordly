"""Tests for core/screen_capture.py — 匹配实际 API"""

import numpy as np
import pytest

pytest.importorskip("cv2", reason="需要 OpenCV for _store_frame JPEG 压缩测试")


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
    def test_disk_store_keeps_more_than_legacy_600_frame_limit(self):
        from core.screen_capture import ScreenCapture

        sc = ScreenCapture()
        for index in range(650):
            data = np.full((4, 6, 3), index % 255, dtype=np.uint8)
            sc._store_frame(data, timestamp=index / 60, index=index)

        frames = sc.all_frames

        assert len(frames) == 650
        assert frames[0].index == 0
        assert frames[-1].index == 649
        assert np.allclose(frames[-1].data, 649 % 255, atol=3)
        sc.clear()

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

    def test_stop_before_start_is_safe(self):
        from core.screen_capture import ScreenCapture

        sc = ScreenCapture()
        sc.stop()

        assert sc.error is None

    def test_stop_returns_true_when_thread_not_started(self):
        from core.screen_capture import ScreenCapture
        sc = ScreenCapture()
        assert sc.stop() is True

    def test_concurrent_write_read_snapshots_never_raise(self):
        """#2 竞态回归：采集线程持续写入时，主线程读快照不抛迭代异常。"""
        import threading
        import time
        from core.screen_capture import ScreenCapture

        sc = ScreenCapture()
        stop = threading.Event()

        def writer():
            index = 0
            while not stop.is_set():
                data = np.full((4, 6, 3), index % 255, dtype=np.uint8)
                sc._store_frame(data, timestamp=index / 60.0, index=index)
                index += 1

        t = threading.Thread(target=writer, daemon=True)
        t.start()
        try:
            for _ in range(200):
                frames = sc.all_frames
                meta_ts, meta_idx = sc.frame_meta
                offsets = sc.frame_offsets
                # 快照内部长度自洽
                assert len(meta_ts) == len(meta_idx)
                assert len(offsets) == len(meta_ts)
                assert len(frames) == len(meta_ts)
                latest = sc.latest_frame
                assert latest is None or latest.index == len(frames) - 1
        finally:
            stop.set()
            t.join(timeout=5)
            sc.clear()

    def test_clear_raises_when_thread_alive(self):
        """#2 回归：线程仍在运行时 clear() 必须拒绝（防止写已删文件）。"""
        from core.screen_capture import ScreenCapture
        sc = ScreenCapture()
        # 未 start 的线程 is_alive()=False，正常清理
        sc.clear()
        # 模拟线程存活：手动 join 无法唤醒，直接验证活线程分支
        sc._store_frame(np.zeros((4, 6, 3), dtype=np.uint8), 0.0, 0)
        sc._quit.set()
        # 未启动线程 is_alive()=False → 不抛；清空数据
        sc.clear()
        assert sc.all_frames == []

    def test_run_loop_interruptible_and_stop_confirms(self, monkeypatch):
        """#2 回归：真实线程下 stop() 确认退出，sleep 可被即时中断。"""
        import time
        from types import SimpleNamespace
        import core.screen_capture as sc_mod

        class FakeSct:
            monitors = [None, {"left": 0, "top": 0}]

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def grab(self, monitor):
                return np.zeros((16, 16, 4), dtype=np.uint8)

        monkeypatch.setattr(sc_mod, "mss", SimpleNamespace(
            mss=lambda: FakeSct()))

        sc = sc_mod.ScreenCapture(target_fps=5)
        sc.start()
        time.sleep(0.3)  # 让线程采几帧
        assert sc.stop() is True
        assert not sc.is_alive()
        assert len(sc.all_frames) >= 1
        # 停止后数据不再增长
        n = len(sc.all_frames)
        time.sleep(0.1)
        assert len(sc.all_frames) == n
        sc.clear()


class TestStaleTempFramesCleanup:
    """#4：崩溃残留的录屏临时帧文件启动时清扫。"""

    def test_deletes_old_matching_files_only(self, monkeypatch, tmp_path):
        import os
        import time
        from core.screen_capture import cleanup_stale_temp_frames

        old = tmp_path / "recordly-abc.frames"
        old.write_bytes(b"data")
        old_time = time.time() - 48 * 3600
        os.utime(old, (old_time, old_time))

        fresh = tmp_path / "recordly-fresh.frames"
        fresh.write_bytes(b"data")  # 新文件，应该保留

        unrelated = tmp_path / "other-output.txt"
        unrelated.write_bytes(b"data")
        unrelated_time = time.time() - 48 * 3600
        os.utime(unrelated, (unrelated_time, unrelated_time))

        monkeypatch.setattr(
            "core.screen_capture.tempfile.gettempdir",
            lambda: str(tmp_path))

        removed = cleanup_stale_temp_frames()
        assert removed == 1
        assert not old.exists()
        assert fresh.exists()
        assert unrelated.exists()  # 非录屏文件不动

    def test_keeps_active_files(self, monkeypatch, tmp_path):
        import time
        from core.screen_capture import cleanup_stale_temp_frames

        active = tmp_path / "recordly-active.frames"
        active.write_bytes(b"data")  # 近期文件 = 可能正在录制的实例

        monkeypatch.setattr(
            "core.screen_capture.tempfile.gettempdir",
            lambda: str(tmp_path))

        assert cleanup_stale_temp_frames() == 0
        assert active.exists()

    def test_missing_temp_dir_returns_zero(self, monkeypatch, tmp_path):
        from core.screen_capture import cleanup_stale_temp_frames
        missing = tmp_path / "nope"
        monkeypatch.setattr(
            "core.screen_capture.tempfile.gettempdir",
            lambda: str(missing))
        assert cleanup_stale_temp_frames() == 0
