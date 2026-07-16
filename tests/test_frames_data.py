"""
测试 load_frames_data: 从 frames.data + frames.idx 加载帧
测试 _collect_project_state: EventData 和 tuple 两种格式
"""

import json
import os
import tempfile
import numpy as np
import pytest

pytest.importorskip("cv2", reason="需要 OpenCV for JPEG 帧编解码测试")

from core.compositor import Compositor


class TestLoadFramesData:
    """验证从 JPEG 帧存储文件加载"""

    def test_load_frames_data_from_index(self):
        """用真实 JPEG 帧写入 frames.data 再通过 frames.idx 加载"""
        import cv2
        comp = Compositor(320, 240, 30)

        # 创建合成帧
        frame1 = np.zeros((240, 320, 3), dtype=np.uint8)
        frame1[:, :, 0] = 30
        frame2 = np.zeros((240, 320, 3), dtype=np.uint8)
        frame2[:, :, 1] = 60

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "frames.data")
            idx_path = os.path.join(tmpdir, "frames.idx")

            # 写入 JPEG 帧和偏移索引
            offsets = []
            with open(store_path, "wb") as fh:
                for frame in [frame1, frame2]:
                    bgr = np.ascontiguousarray(frame[:, :, ::-1])
                    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    payload = buf.tobytes()
                    offset = fh.tell()
                    fh.write(payload)
                    offsets.append([offset, len(payload)])

            with open(idx_path, "w") as f:
                json.dump(offsets, f)

            # 加载
            num = comp.load_frames_data(store_path, 2, 30)
            assert num == 2
            assert len(comp._frames) == 2
            assert comp.width == 320
            assert comp.height == 240
            # 验证首帧数据可读取
            data0 = comp._frames[0].data
            assert data0 is not None
            assert data0.shape == (240, 320, 3)

            # 释放 compositor 引用的文件句柄，确保 Windows 可清理临时目录
            del data0, num
            del comp
            import gc
            gc.collect()

    def test_load_empty_offsets_raises(self):
        """无 frames.idx 且 frame_count > 0 时报错"""
        comp = Compositor(320, 240, 30)
        with pytest.raises((RuntimeError, IndexError, FileNotFoundError)):
            comp.load_frames_data("/nonexistent/frames.data", 10, 30)

    def test_reload_preserves_recorded_duration_when_capture_fps_is_lower(
            self, tmp_path):
        """重开后应按录制时长恢复时间轴，而非按目标 FPS 加速。"""
        store_path = tmp_path / "frames.data"
        idx_path = tmp_path / "frames.idx"
        store_path.write_bytes(b"")
        idx_path.write_text(json.dumps([[0, 0]] * 250))

        comp = Compositor(320, 240, 60)
        comp.load_frames_data(
            str(store_path), frame_count=250, fps=60, duration=10.0)

        assert comp.source_duration == pytest.approx(10.0)
        assert comp.frame_times[-1] == pytest.approx(9.96)

    def test_concurrent_requests_decode_same_frame_once(self, tmp_path,
                                                        monkeypatch):
        import cv2
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor

        frame = np.full((32, 32, 3), 90, dtype=np.uint8)
        ok, encoded = cv2.imencode(".jpg", frame)
        assert ok
        payload = encoded.tobytes()
        store_path = tmp_path / "frames.data"
        idx_path = tmp_path / "frames.idx"
        store_path.write_bytes(payload)
        idx_path.write_text(json.dumps([[0, len(payload)]]))

        original_decode = cv2.imdecode
        decode_count = 0
        count_lock = threading.Lock()

        def tracked_decode(*args, **kwargs):
            nonlocal decode_count
            with count_lock:
                decode_count += 1
            time.sleep(0.02)
            return original_decode(*args, **kwargs)

        monkeypatch.setattr(cv2, "imdecode", tracked_decode)
        comp = Compositor(32, 32, 30)
        comp.load_frames_data(
            str(store_path), 1, 30, cache_max_bytes=4096)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: comp.frames[0].data, range(8)))

        assert decode_count == 1
        assert all(result.shape == (32, 32, 3) for result in results)

    def test_replacing_frames_closes_frames_data_handle(self, tmp_path):
        store_path = tmp_path / "frames.data"
        idx_path = tmp_path / "frames.idx"
        store_path.write_bytes(b"")
        idx_path.write_text("[[0, 0]]")

        comp = Compositor(32, 32, 30)
        comp.load_frames_data(str(store_path), 1, 30)
        handle = comp._frames_data_handle

        comp.frames = []

        assert handle.closed
        assert comp._frames_data_handle is None


class TestLiveFrameStore:
    def test_concurrent_reads_decode_once_and_use_byte_budget(self, tmp_path,
                                                              monkeypatch):
        import cv2
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor
        from core.screen_capture import _CompressedFrameStore

        store = _CompressedFrameStore(
            store_path=str(tmp_path / "live.frames"),
            cache_max_bytes=4096,
        )
        store.append(np.full((32, 32, 3), 70, dtype=np.uint8))
        original_decode = cv2.imdecode
        decode_count = 0
        count_lock = threading.Lock()

        def tracked_decode(*args, **kwargs):
            nonlocal decode_count
            with count_lock:
                decode_count += 1
            time.sleep(0.02)
            return original_decode(*args, **kwargs)

        monkeypatch.setattr(cv2, "imdecode", tracked_decode)
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: store.read(0), range(8)))

        assert decode_count == 1
        assert store._cache_nbytes <= store._cache_max_bytes
        assert all(result.shape == (32, 32, 3) for result in results)
        store.cleanup()


class TestCollectProjectStateFormats:
    """_collect_project_state 兼容 EventData 对象和元组"""

    def test_collect_from_eventdata(self):
        """从 EventData 对象收集 cursor_events"""
        EventData = type("EventData", (), {})
        e1 = EventData()
        e1.x, e1.y, e1.timestamp = 100, 200, 1.5
        e2 = EventData()
        e2.x, e2.y, e2.timestamp = 110, 210, 2.0

        result = []
        for c in [e1, e2]:
            if hasattr(c, 'x'):
                result.append([c.x, c.y, c.timestamp])
            else:
                result.append([c[0], c[1], c[2]])

        assert result == [[100, 200, 1.5], [110, 210, 2.0]]

    def test_collect_from_tuples(self):
        """从元组收集 click_events"""
        clicks = [(50, 100, 1.5), (55, 105, 2.0)]
        result = []
        for c in clicks:
            if hasattr(c, 'x'):
                result.append([c.x, c.y, c.timestamp])
            else:
                result.append([c[0], c[1], c[2]])

        assert result == [[50, 100, 1.5], [55, 105, 2.0]]
