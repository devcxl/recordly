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
        # 输入保持 compositor.fps, 输出使用 settings.fps
        assert "-r 30" in command, "输入应保持 compositor.fps"
        assert "-r 15" in command, "输出应使用 settings.fps"
