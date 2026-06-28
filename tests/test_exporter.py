"""Tests for core/exporter.py — 匹配实际 API"""

import pytest


class TestExportResult:
    def test_fields(self):
        from core.exporter import ExportResult
        fields = ExportResult.__dataclass_fields__  # pyright: ignore
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
        fields = ExportSettings.__dataclass_fields__  # pyright: ignore
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


class TestExporter:
    def test_importable(self):
        from core.exporter import Exporter
        assert Exporter is not None

    def test_can_instantiate(self):
        from core.exporter import Exporter
        e = Exporter()
        assert hasattr(e, 'progress')
        assert hasattr(e, 'finished')
        assert hasattr(e, 'cancel')

    def test_cancel_before_start(self):
        from core.exporter import Exporter
        e = Exporter()
        e.cancel()  # should not raise
