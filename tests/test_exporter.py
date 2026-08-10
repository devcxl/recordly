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

    def test_fill_crop_ratio_default_none(self):
        from core.exporter import ExportSettings
        s = ExportSettings(output_path="out.mp4")
        assert s.fill_crop_ratio is None

    def test_export_settings_audio_regions_field(self):
        """ExportSettings.extra_audio 更名为 audio_regions（语义=全部音频区域）"""
        from core.exporter import ExportSettings
        s = ExportSettings(output_path="out.mp4", audio_regions=["region"])
        assert s.audio_regions == ["region"]
        assert "extra_audio" not in ExportSettings.__dataclass_fields__


class TestFillCropMaterialization:
    """fill_crop_ratio → crop_region 物化（复用现有裁剪渲染/尺寸路径）"""

    def _compositor(self):
        from core.compositor import Compositor
        c = Compositor(320, 240, 30)
        return c

    def test_materializes_fill_region_on_run(self, monkeypatch):
        """320×240 源 + 1:1：crop_region 物化为中心裁剪并写入 compositor"""
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        compositor = self._compositor()
        settings = ExportSettings(
            output_path="out.mp4", fill_crop_ratio="1:1")
        worker = ExportWorker(compositor, settings)
        monkeypatch.setattr(worker, "_export_mp4", lambda: None)

        worker.run()

        # 320×240 (4:3) → 1:1：裁左右，宽 240 → 归一化 0.75，居中
        assert settings.crop_region is not None
        assert settings.crop_region.width == 0.75
        assert settings.crop_region.x == 0.125
        assert settings.crop_region.height == 1.0
        assert settings.crop_region.y == 0.0
        assert compositor.crop_region is settings.crop_region

    def test_restores_compositor_crop_after_run(self, monkeypatch):
        """导出结束后 compositor 恢复导出前的裁剪状态"""
        from core.project import CropRegion
        from core.exporter import ExportWorker, ExportSettings

        original = CropRegion(x=0.1, y=0.2, width=0.5, height=0.6)
        compositor = self._compositor()
        compositor.set_crop(original)
        settings = ExportSettings(
            output_path="out.mp4", fill_crop_ratio="1:1")
        worker = ExportWorker(compositor, settings)
        monkeypatch.setattr(worker, "_export_mp4", lambda: None)

        worker.run()

        assert compositor.crop_region is original

    def test_exact_ratio_skips_materialization(self, monkeypatch):
        """源比例与目标比例相同 → 无需裁剪，crop_region 保持 None"""
        from core.exporter import ExportWorker, ExportSettings

        compositor = self._compositor()  # 320×240 = 4:3
        settings = ExportSettings(
            output_path="out.mp4", fill_crop_ratio="4:3")
        worker = ExportWorker(compositor, settings)
        monkeypatch.setattr(worker, "_export_mp4", lambda: None)

        worker.run()

        assert settings.crop_region is None
        assert compositor.crop_region is None

    def test_invalid_ratio_skips_materialization(self, monkeypatch):
        from core.exporter import ExportWorker, ExportSettings

        compositor = self._compositor()
        settings = ExportSettings(
            output_path="out.mp4", fill_crop_ratio="invalid")
        worker = ExportWorker(compositor, settings)
        monkeypatch.setattr(worker, "_export_mp4", lambda: None)

        worker.run()

        assert settings.crop_region is None

    def test_fill_precedes_free_crop(self, monkeypatch):
        """fill 优先于自由裁剪（对话框层互斥的兜底）"""
        from core.project import CropRegion
        from core.exporter import ExportWorker, ExportSettings

        compositor = self._compositor()
        settings = ExportSettings(
            output_path="out.mp4", fill_crop_ratio="1:1",
            crop_region=CropRegion(x=0.0, y=0.0, width=0.5, height=0.5))
        worker = ExportWorker(compositor, settings)
        monkeypatch.setattr(worker, "_export_mp4", lambda: None)

        worker.run()

        assert settings.crop_region.width == 0.75
        assert settings.crop_region.x == 0.125

    def test_gif_export_uses_fill_region(self, monkeypatch):
        """GIF 导出同样走物化路径"""
        from core.exporter import ExportWorker, ExportSettings

        compositor = self._compositor()
        settings = ExportSettings(
            output_path="out.gif", format="gif", fps=15,
            fill_crop_ratio="1:1")
        worker = ExportWorker(compositor, settings)
        monkeypatch.setattr(worker, "_export_gif", lambda: None)

        worker.run()

        assert settings.crop_region is not None
        assert settings.crop_region.width == 0.75


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

    def test_worker_constructor_drops_audio_data(self):
        """ExportWorker.__init__ 不再接收 audio_data（音频由 settings.audio_regions 合成）"""
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        worker = ExportWorker(
            Compositor(320, 240, 30), ExportSettings(output_path="out.mp4"))
        assert worker._settings.audio_regions is None
        with pytest.raises(TypeError):
            ExportWorker(
                Compositor(320, 240, 30), None,
                ExportSettings(output_path="out.mp4"))

    def test_filtergraph_helpers_removed(self):
        """_build_audio_filtergraph / _atempo_filter_text 已删除且无调用者"""
        import core.exporter as exporter_module
        assert not hasattr(exporter_module, "_build_audio_filtergraph")
        assert not hasattr(exporter_module, "_atempo_filter_text")

    def test_mp4_cpu_uses_composed_audio(self, monkeypatch):
        """_export_mp4_cpu：audio_regions（过滤不存在项）→ compose_audio → _save_temp_wav
        作为 FFmpeg 唯一音频输入；不再出现 orig_wav / filtergraph。"""
        import numpy as np
        from types import SimpleNamespace
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings
        from core.project import AudioRegion, Clip

        compositor = Compositor(320, 240, 30)
        compositor.load_clips([Clip(type="video", start=0.0, end=1.0)])
        worker = ExportWorker(
            compositor,
            ExportSettings(output_path="out.mp4", fps=30),
        )
        worker._settings.audio_regions = [
            AudioRegion(id="mic", start_ms=0, end_ms=1000,
                        source_start_ms=0, source_end_ms=1000,
                        audio_path="/tmp/mic.wav", volume=1.0),
            AudioRegion(id="missing", start_ms=0, end_ms=1000,
                        source_start_ms=0, source_end_ms=1000,
                        audio_path="/tmp/not-exists.wav", volume=1.0),
        ]

        compose_calls = []
        mixed = np.zeros((100, 2), dtype=np.float32)
        monkeypatch.setattr(
            "core.exporter.compose_audio",
            lambda regions, samplerate, duration=None: (
                compose_calls.append((regions, samplerate, duration)) or mixed))
        saved = []
        monkeypatch.setattr(
            ExportWorker, "_save_temp_wav",
            staticmethod(lambda audio, samplerate: (
                saved.append((audio, samplerate)) or "/tmp/mixed.wav")))

        ffmpeg_inputs = []
        monkeypatch.setattr(
            "core.exporter.ffmpeg.input",
            lambda *args, **_kwargs: (ffmpeg_inputs.append(args) or object()))
        captured = {}

        def fake_output(*args, **_kwargs):
            captured["output_args"] = args
            return SimpleNamespace(
                overwrite_output=lambda: SimpleNamespace(
                    run_async=lambda **_kw: SimpleNamespace(
                        stdin=SimpleNamespace(
                            write=lambda _d: None, close=lambda: None),
                        stderr=[], terminate=lambda: None, wait=lambda: 0)))

        monkeypatch.setattr("core.exporter.ffmpeg.output", fake_output)
        monkeypatch.setattr(
            worker, "_stream_frames_parallel", lambda *a, **_k: True)
        monkeypatch.setattr(
            "core.exporter.os.path.exists",
            lambda path: path in ("/tmp/mic.wav", "out.mp4"))
        monkeypatch.setattr(
            "core.exporter.os.path.getsize", lambda _p: 12345)

        worker._export_mp4_cpu()

        # audio_regions 过滤不存在项后传入 compose_audio，携带 samplerate 与 video_duration
        assert len(compose_calls) == 1
        regions, samplerate, duration = compose_calls[0]
        assert [r.id for r in regions] == ["mic"]
        assert samplerate == 44100
        assert duration == pytest.approx(1.0)  # total(30) / fps(30)

        # _save_temp_wav 输出 compose_audio 的合成结果，作为唯一音频输入
        assert saved == [(mixed, 44100)]
        assert ("/tmp/mixed.wav",) in ffmpeg_inputs
        # 视频输入仍是 pipe:
        assert any(a[0] == "pipe:" for a in ffmpeg_inputs)

    def test_mp4_cpu_without_valid_regions_skips_audio(self, monkeypatch):
        """无有效 regions（audio_path 不存在）→ compose_audio 无有效 region → 无音频输入"""
        from types import SimpleNamespace
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings
        from core.project import AudioRegion, Clip

        compositor = Compositor(320, 240, 30)
        compositor.load_clips([Clip(type="video", start=0.0, end=1.0)])
        worker = ExportWorker(
            compositor,
            ExportSettings(output_path="out.mp4", fps=30),
        )
        worker._settings.audio_regions = [
            AudioRegion(id="missing", start_ms=0, end_ms=1000,
                        source_start_ms=0, source_end_ms=1000,
                        audio_path="/tmp/not-exists.wav", volume=1.0),
        ]

        monkeypatch.setattr(
            "core.exporter.compose_audio", lambda *a, **_k: None)
        saved = []
        monkeypatch.setattr(
            ExportWorker, "_save_temp_wav",
            staticmethod(lambda audio, samplerate: (
                saved.append((audio, samplerate)) or "/tmp/mixed.wav")))

        ffmpeg_inputs = []
        monkeypatch.setattr(
            "core.exporter.ffmpeg.input",
            lambda *args, **_kwargs: (ffmpeg_inputs.append(args) or object()))
        captured = {}

        def fake_output(*args, **_kwargs):
            captured["output_args"] = args
            return SimpleNamespace(
                overwrite_output=lambda: SimpleNamespace(
                    run_async=lambda **_kw: SimpleNamespace(
                        stdin=SimpleNamespace(
                            write=lambda _d: None, close=lambda: None),
                        stderr=[], terminate=lambda: None, wait=lambda: 0)))

        monkeypatch.setattr("core.exporter.ffmpeg.output", fake_output)
        monkeypatch.setattr(
            worker, "_stream_frames_parallel", lambda *a, **_k: True)
        monkeypatch.setattr(
            "core.exporter.os.path.exists", lambda path: path == "out.mp4")
        monkeypatch.setattr(
            "core.exporter.os.path.getsize", lambda _p: 12345)

        worker._export_mp4_cpu()

        assert saved == []
        assert len(ffmpeg_inputs) == 1  # 只有视频 pipe:
        assert captured["output_args"][1:] == ("out.mp4",)

    def test_mp4_nvenc_uses_composed_audio(self, monkeypatch):
        """_export_mp4_nvenc：与 CPU 路径共用 compose_audio 合成语义，无 orig_wav"""
        import numpy as np
        from types import SimpleNamespace
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings
        from core.project import AudioRegion, Clip

        compositor = Compositor(320, 240, 30)
        compositor.load_clips([Clip(type="video", start=0.0, end=1.0)])
        worker = ExportWorker(
            compositor,
            ExportSettings(output_path="out.mp4", fps=30, use_gpu=True),
        )
        worker._settings.audio_regions = [
            AudioRegion(id="mic", start_ms=0, end_ms=1000,
                        source_start_ms=0, source_end_ms=1000,
                        audio_path="/tmp/mic.wav", volume=1.0),
        ]

        compose_calls = []
        mixed = np.zeros((100, 2), dtype=np.float32)
        monkeypatch.setattr(
            "core.exporter.compose_audio",
            lambda regions, samplerate, duration=None: (
                compose_calls.append((regions, samplerate, duration)) or mixed))
        saved = []
        monkeypatch.setattr(
            ExportWorker, "_save_temp_wav",
            staticmethod(lambda audio, samplerate: (
                saved.append((audio, samplerate)) or "/tmp/mixed.wav")))

        ffmpeg_inputs = []
        monkeypatch.setattr(
            "core.exporter.ffmpeg.input",
            lambda *args, **_kwargs: (ffmpeg_inputs.append(args) or object()))
        monkeypatch.setattr(
            "core.exporter.ffmpeg.output",
            lambda *args, **_kwargs: SimpleNamespace(
                overwrite_output=lambda: SimpleNamespace(
                    compile=lambda: ["ffmpeg", "-y", "out.mp4"])))
        monkeypatch.setattr(
            "core.exporter.subprocess.Popen",
            lambda *a, **_kw: SimpleNamespace(
                stdin=SimpleNamespace(
                    write=lambda _d: None, close=lambda: None),
                stderr=[], terminate=lambda: None, wait=lambda: 0))
        monkeypatch.setattr(
            worker, "_stream_frames_parallel", lambda *a, **_k: True)
        monkeypatch.setattr(
            "core.exporter.os.path.exists",
            lambda path: path in ("/tmp/mic.wav", "out.mp4"))
        monkeypatch.setattr(
            "core.exporter.os.path.getsize", lambda _p: 12345)

        worker._export_mp4_nvenc()

        assert len(compose_calls) == 1
        regions, samplerate, duration = compose_calls[0]
        assert [r.id for r in regions] == ["mic"]
        assert samplerate == 44100
        assert duration == pytest.approx(1.0)  # total(30) / fps(30)
        assert saved == [(mixed, 44100)]
        assert ("/tmp/mixed.wav",) in ffmpeg_inputs
        assert any(a[0] == "pipe:" for a in ffmpeg_inputs)

    @pytest.mark.parametrize("region_kwargs", [
        dict(id="trim", start_ms=5000, end_ms=7000,
             source_start_ms=1000, source_end_ms=3000, volume=0.5),
        dict(id="open", start_ms=0, end_ms=4000,
             source_start_ms=0, source_end_ms=None, volume=1.0),
        dict(id="half", start_ms=0, end_ms=4000,
             source_start_ms=0, source_end_ms=4000, volume=0.5),
        dict(id="muted", start_ms=0, end_ms=4000,
             source_start_ms=0, source_end_ms=4000, volume=0.0),
    ])
    def test_export_passes_region_timeline_semantics_to_compose_audio(
            self, monkeypatch, region_kwargs):
        """导出把 region 的裁剪/定位/音量字段原样交给 compose_audio 合成
        （旧 filtergraph 链路中 atrim/atempo/adelay/volume 的职责由 compose_audio 承接；
        video 轨 speed 不再影响音频，见方案 §4.3）。"""
        import numpy as np
        from types import SimpleNamespace
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings
        from core.project import AudioRegion, Clip

        compositor = Compositor(320, 240, 30)
        compositor.load_clips([Clip(
            type="video", start=0.0, end=2.0,
            source_start=0.0, source_end=4.0, speed=2.0,
        )])
        region = AudioRegion(audio_path="/tmp/music.wav", **region_kwargs)
        worker = ExportWorker(
            compositor, ExportSettings(output_path="out.mp4", fps=30))
        worker._settings.audio_regions = [region]

        compose_calls = []
        mixed = np.zeros((100, 2), dtype=np.float32)
        monkeypatch.setattr(
            "core.exporter.compose_audio",
            lambda regions, samplerate, duration=None: (
                compose_calls.append((regions, samplerate, duration)) or mixed))
        monkeypatch.setattr(
            ExportWorker, "_save_temp_wav",
            staticmethod(lambda audio, samplerate: "/tmp/mixed.wav"))
        ffmpeg_inputs = []
        monkeypatch.setattr(
            "core.exporter.ffmpeg.input",
            lambda *args, **_kwargs: (ffmpeg_inputs.append(args) or object()))
        monkeypatch.setattr(
            "core.exporter.ffmpeg.output",
            lambda *args, **_kwargs: SimpleNamespace(
                overwrite_output=lambda: SimpleNamespace(
                    run_async=lambda **_kw: SimpleNamespace(
                        stdin=SimpleNamespace(
                            write=lambda _d: None, close=lambda: None),
                        stderr=[], terminate=lambda: None, wait=lambda: 0))))
        monkeypatch.setattr(
            worker, "_stream_frames_parallel", lambda *a, **_k: True)
        monkeypatch.setattr(
            "core.exporter.os.path.exists",
            lambda path: path in ("/tmp/music.wav", "out.mp4"))
        monkeypatch.setattr(
            "core.exporter.os.path.getsize", lambda _p: 12345)

        worker._export_mp4_cpu()

        assert len(compose_calls) == 1
        passed, _samplerate, _duration = compose_calls[0]
        assert len(passed) == 1
        passed_region = passed[0]
        # 字段原样传递（start_ms/source_start_ms/source_end_ms/volume/audio_path）
        for field, expected in region_kwargs.items():
            assert getattr(passed_region, field) == expected
        assert passed_region.audio_path == "/tmp/music.wav"
        # 合成结果写盘并作为唯一音频输入
        assert ("/tmp/mixed.wav",) in ffmpeg_inputs

    def test_save_temp_wav_infers_channels_from_array_shape(self):
        import wave
        import numpy as np
        from core.exporter import ExportWorker

        mono = np.zeros((100,), dtype=np.float32)
        stereo = np.zeros((100, 2), dtype=np.float32)
        quad = np.zeros((100, 4), dtype=np.float32)

        for data, expected in ((mono, 1), (stereo, 2), (quad, 4)):
            path = ExportWorker._save_temp_wav(data, 44100)
            with wave.open(path, "r") as wf:
                assert wf.getnchannels() == expected
            import os
            os.remove(path)

    def test_gif_graph_uses_target_fps_without_downsampling_filter(self):
        import ffmpeg
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        compositor = Compositor(320, 240, 30)
        worker = ExportWorker(
            compositor,
            ExportSettings(output_path="out.gif", format="gif", fps=15),
        )

        graph = worker._build_gif_output(320, 240)
        command = " ".join(ffmpeg.compile(graph))

        assert "palettegen" in command
        assert "paletteuse" in command
        assert "-pix_fmt rgb24" in command
        assert "-r 15" in command, "输入应直接使用 GIF 目标 FPS"
        assert "fps=fps=" not in command

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
            FakeCompositor(),
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
            FakeCompositor(),
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
            FakeCompositor(),
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
            parallel, ExportSettings(output_path="out.mp4", fps=10))
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
            FakeCompositor(),
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
