"""Tests for core/exporter.py — 匹配实际 API"""

import pytest


class TestExportResult:
    def test_fields(self):
        from core.exporter import ExportResult
        fields = ExportResult.__dataclass_fields__
        assert 'success' in fields
        assert 'path' in fields
        assert 'duration' in fields
        assert 'size_bytes' in fields
        assert 'error' in fields

    def test_success_result(self):
        from core.exporter import ExportResult
        r = ExportResult(success=True, path="out.mp4", duration=30.0, size_bytes=1_500_000)
        assert r.success is True
        assert r.path == "out.mp4"
        assert r.duration == pytest.approx(30.0)
        assert r.size_bytes == 1_500_000

    def test_failure_result(self):
        from core.exporter import ExportResult
        r = ExportResult(success=False, path="out.mp4", error="ffmpeg not found")
        assert r.success is False
        assert r.error == "ffmpeg not found"

    def test_default_duration(self):
        from core.exporter import ExportResult
        r = ExportResult(success=True, path="test.mp4")
        assert r.duration == 0.0

    def test_default_error(self):
        from core.exporter import ExportResult
        r = ExportResult(success=True, path="test.mp4")
        assert r.error is None


class TestExportSettings:
    def test_fields(self):
        from core.exporter import ExportSettings
        fields = ExportSettings.__dataclass_fields__
        assert 'output_path' in fields
        assert 'format' in fields
        assert 'fps' in fields
        assert 'bitrate' in fields

    def test_defaults(self):
        from core.exporter import ExportSettings
        s = ExportSettings(output_path="out.mp4")
        assert s.format == "mp4"
        assert s.fps == 30
        assert s.width == 0

    def test_custom(self):
        from core.exporter import ExportSettings
        s = ExportSettings(output_path="out.gif", format="gif", fps=15, width=640, height=480)
        assert s.format == "gif"
        assert s.fps == 15
        assert s.width == 640

    def test_aspect_ratio_default(self):
        from core.exporter import ExportSettings
        s = ExportSettings(output_path="out.mp4")
        assert s.aspect_ratio == "native"
        assert s.quality == 1.0
        assert s.loop is True

    def test_extra_fields(self):
        from core.exporter import ExportSettings
        s = ExportSettings(output_path="out.mp4", aspect_ratio="16:9", quality=0.75, loop=False)
        assert s.aspect_ratio == "16:9"
        assert s.quality == 0.75
        assert s.loop is False


class TestExportWorker:
    def test_importable(self):
        from core.exporter import ExportWorker
        assert ExportWorker is not None

    def test_has_signals(self):
        from core.exporter import ExportWorker
        assert hasattr(ExportWorker, 'progress')
        assert hasattr(ExportWorker, 'finished')

    def test_has_cancel(self):
        from core.exporter import ExportWorker
        assert hasattr(ExportWorker, 'cancel')

    def test_audio_mix_trims_sources_and_preserves_timeline(self, monkeypatch):
        from types import SimpleNamespace
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings
        from core.project import AudioRegion, Clip

        compositor = Compositor(320, 240, 30)
        compositor.load_clips([Clip(
            type="video", start=2.0, end=4.0,
            source_start=1.0, source_end=5.0, speed=2.0,
        )])
        worker = ExportWorker(
            compositor, None, ExportSettings(output_path="out.mp4"))
        region = AudioRegion(
            id="extra", start_ms=5000, end_ms=7000,
            source_start_ms=1000, source_end_ms=3000,
            audio_path="/tmp/music.wav", volume=0.5,
        )
        captured = {}

        monkeypatch.setattr("core.exporter.os.path.exists", lambda _path: True)
        monkeypatch.setattr("core.exporter.tempfile.mkstemp",
                            lambda **_kwargs: (0, "/tmp/mixed.wav"))

        def fake_run(cmd, **_kwargs):
            captured["cmd"] = cmd
            return SimpleNamespace(returncode=0, stderr=b"")

        monkeypatch.setattr("core.exporter.subprocess.run", fake_run)

        result = worker._build_audio_filtergraph(
            [region], "/tmp/original.wav", 44100, video_duration=8.0)

        filtergraph = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]
        assert result == "/tmp/mixed.wav"
        assert "atrim=start=1.0:end=5.0" in filtergraph
        assert "atempo=2" in filtergraph
        assert "adelay=2000|2000" in filtergraph
        assert "atrim=start=1.0:end=3.0" in filtergraph
        assert "volume=0.5" in filtergraph
        assert "adelay=5000|5000" in filtergraph
        assert "amix=inputs=2:duration=longest" in filtergraph
        assert "atrim=duration=8.0" in filtergraph

    def test_gif_graph_connects_palette_and_keeps_source_timing(self):
        import ffmpeg
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        compositor = Compositor(320, 240, 30)
        worker = ExportWorker(
            compositor, None,
            ExportSettings(output_path="out.gif", format="gif", fps=15),
        )

        graph = worker._build_gif_output(320, 240)
        command = " ".join(ffmpeg.compile(graph))

        assert "palettegen" in command
        assert "paletteuse" in command
        # 输入保持 compositor.fps, split 前有 fps 降采样
        assert "-r 30" in command, "输入应保持 compositor.fps"
        assert "fps=fps=15" in command, "fps filter 应降采样到 settings.fps"

    def test_parallel_stream_refills_behind_slow_first_frame(self, monkeypatch):
        import threading
        from types import SimpleNamespace
        from core.exporter import ExportWorker, ExportSettings

        release_first = threading.Event()
        later_frame_started = threading.Event()
        first_released_by_later_frame = []

        class FakeCompositor:
            width = 1
            height = 1

            def iter_frame_meta(self, render_fps=None):
                for index in range(20):
                    yield index, index, index / 30

        class FakeStdin:
            def __init__(self):
                self.values = []

            def write(self, data):
                self.values.append(data[0])

        stdin = FakeStdin()
        worker = ExportWorker(
            FakeCompositor(), None,
            ExportSettings(output_path="out.mp4", fps=30),
        )
        worker._process = SimpleNamespace(
            stdin=stdin, terminate=lambda: None, wait=lambda: 0)
        monkeypatch.setattr("core.exporter.os.cpu_count", lambda: 2)

        def prepare(_compositor, raw_frame, index, _ts,
                    _target_w, _target_h, _pix_fmt, _direct_output):
            if index == 0:
                first_released_by_later_frame.append(
                    release_first.wait(timeout=0.5))
            if index == 4:
                later_frame_started.set()
                release_first.set()
            return index, bytes([index])

        monkeypatch.setattr(worker, "_compose_and_encode", prepare)
        stderr_thread = SimpleNamespace(join=lambda timeout=None: None)

        success = worker._stream_frames_parallel(
            20, 1, 1, "RGB", stderr_thread, [],
            render_fps=30, direct_output=False)

        assert success is True
        assert later_frame_started.is_set()
        assert first_released_by_later_frame == [True]
        assert stdin.values == list(range(20))

    def test_parallel_stream_applies_effects_in_frame_order(self, monkeypatch):
        import time
        from types import SimpleNamespace
        from PIL import Image
        from core.exporter import ExportWorker, ExportSettings

        effect_order = []

        class FakeCompositor:
            width = 1
            height = 1

            def iter_frame_meta(self, render_fps=None):
                for index in range(8):
                    yield index, SimpleNamespace(index=index), index / 30

            def prepare_frame(self, raw_frame, _ts, **_kwargs):
                time.sleep((7 - raw_frame.index) * 0.001)
                image = Image.new("RGB", (1, 1), raw_frame.index)
                return image, SimpleNamespace(frame_index=raw_frame.index)

            def apply_effects(self, image, ctx, output_mode=None):
                effect_order.append(ctx.frame_index)
                return image

        class FakeStdin:
            def __init__(self):
                self.values = []

            def write(self, data):
                self.values.append(data[0])

        stdin = FakeStdin()
        worker = ExportWorker(
            FakeCompositor(), None,
            ExportSettings(output_path="out.mp4", fps=30),
        )
        worker._process = SimpleNamespace(
            stdin=stdin, terminate=lambda: None, wait=lambda: 0)
        monkeypatch.setattr("core.exporter.os.cpu_count", lambda: 4)

        success = worker._stream_frames_parallel(
            8, 1, 1, "RGB",
            SimpleNamespace(join=lambda timeout=None: None), [],
            render_fps=30, direct_output=True)

        assert success is True
        assert effect_order == list(range(8))
        assert stdin.values == list(range(8))

    def test_parallel_stream_terminates_ffmpeg_when_frame_is_missing(self):
        from types import SimpleNamespace
        from core.exporter import ExportWorker, ExportSettings

        class FakeCompositor:
            width = 1
            height = 1

            def iter_frame_meta(self, render_fps=None):
                yield 0, 0, 0.0
                yield 2, 2, 2 / 30

        terminated = []
        worker = ExportWorker(
            FakeCompositor(), None,
            ExportSettings(output_path="out.mp4", fps=30),
        )
        worker._process = SimpleNamespace(
            stdin=SimpleNamespace(write=lambda _data: None),
            terminate=lambda: terminated.append(True),
        )
        worker._compose_and_encode = (
            lambda _c, _frame, index, _ts, _w, _h, _fmt, _direct:
            (index, bytes([index]))
        )

        with pytest.raises(RuntimeError, match="缺少第 1 帧"):
            worker._stream_frames_parallel(
                3, 1, 1, "RGB",
                SimpleNamespace(join=lambda timeout=None: None), [],
                render_fps=30, direct_output=True)

        assert terminated == [True]

    def test_parallel_export_matches_serial_moving_cursor(self, monkeypatch):
        import time
        from types import SimpleNamespace
        import numpy as np
        from core.compositor import Compositor
        from core.cursor_effects import CursorEffect
        from core.exporter import ExportWorker, ExportSettings
        from core.screen_capture import CapturedFrame

        def make_compositor():
            compositor = Compositor(32, 16, 10)
            compositor.load_frames([CapturedFrame(
                data=np.zeros((16, 32, 3), dtype=np.uint8),
                timestamp=index / 10,
                index=index,
            ) for index in range(8)])
            compositor._cursor_events = [SimpleNamespace(
                x=3 + index * 3, y=8, timestamp=index / 10,
            ) for index in range(8)]
            effect = CursorEffect(cursor_size=6, cursor_style="ring")
            effect.enabled["ripple"] = False
            compositor.register_effect("cursor", effect)
            return compositor

        serial = make_compositor()
        expected = [serial.compose(
            frame, index / 10, output_size=(32, 16), output_mode="RGB",
        ).tobytes() for index, frame in enumerate(serial.frames)]

        parallel = make_compositor()
        original_prepare = parallel.prepare_frame

        def delayed_prepare(frame, *args, **kwargs):
            time.sleep((7 - frame.index) * 0.001)
            return original_prepare(frame, *args, **kwargs)

        monkeypatch.setattr(parallel, "prepare_frame", delayed_prepare)
        rendered = []
        worker = ExportWorker(
            parallel, None, ExportSettings(output_path="out.mp4", fps=10))
        worker._process = SimpleNamespace(
            stdin=SimpleNamespace(write=rendered.append),
            terminate=lambda: None,
        )

        success = worker._stream_frames_parallel(
            8, 32, 16, "RGB",
            SimpleNamespace(join=lambda timeout=None: None), [],
            render_fps=10, direct_output=True)

        assert success is True
        assert rendered == expected

    def test_parallel_pending_frames_respect_reorder_byte_budget(
            self, monkeypatch):
        import threading
        import time
        from types import SimpleNamespace
        from core.exporter import ExportWorker, ExportSettings

        release = threading.Event()
        started = []

        class FakeCompositor:
            width = 4096
            height = 4096

            def iter_frame_meta(self, render_fps=None):
                for index in range(8):
                    yield index, index, index / 30

        worker = ExportWorker(
            FakeCompositor(), None,
            ExportSettings(output_path="out.mp4", fps=30),
        )
        worker._process = SimpleNamespace(
            stdin=SimpleNamespace(write=lambda _data: None),
            terminate=lambda: None,
        )
        monkeypatch.setattr("core.exporter.os.cpu_count", lambda: 8)

        def blocked_prepare(_c, _frame, index, _ts,
                            _w, _h, _fmt, _direct):
            started.append(index)
            release.wait(timeout=1)
            return index, bytes([index])

        monkeypatch.setattr(worker, "_compose_and_encode", blocked_prepare)
        result = []
        thread = threading.Thread(target=lambda: result.append(
            worker._stream_frames_parallel(
                8, 1920, 1080, "RGB",
                SimpleNamespace(join=lambda timeout=None: None), [],
                render_fps=30, direct_output=False)))
        thread.start()

        deadline = time.monotonic() + 1
        while len(started) < 4 and time.monotonic() < deadline:
            time.sleep(0.005)
        time.sleep(0.02)
        assert len(started) == 4

        release.set()
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert result == [True]
