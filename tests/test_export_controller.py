"""ExportController 单元测试"""

import pytest
from unittest.mock import MagicMock
from app.export_controller import ExportController


class TestExportController:
    def test_initial_state(self):
        ctrl = ExportController()
        assert ctrl.is_exporting is False

    def test_cancel_before_export_noop(self):
        ctrl = ExportController()
        ctrl.cancel()

    def test_cleanup_noop_when_idle(self):
        ctrl = ExportController()
        ctrl.cleanup()

    def test_state_after_finished(self):
        ctrl = ExportController()
        sig = MagicMock()
        ctrl.export_finished.connect(sig)

        # Simulate worker finished
        result = MagicMock(success=True)
        ctrl._on_worker_finished(result)

        sig.assert_called_once_with(result)
        assert ctrl.is_exporting is False

    def test_start_export_constructs_worker_with_compositor_and_settings(
            self, monkeypatch):
        """start_export(compositor, settings)：audio 来源从 audio_data 改为 settings.audio_regions"""
        from core.compositor import Compositor
        from core.exporter import ExportSettings

        captured = {}
        worker = MagicMock()

        def fake_worker(compositor, settings):
            captured["compositor"] = compositor
            captured["settings"] = settings
            return worker

        monkeypatch.setattr("app.export_controller.ExportWorker", fake_worker)

        ctrl = ExportController()
        compositor = Compositor(320, 240, 30)
        settings = ExportSettings(
            output_path="out.mp4", audio_regions=["region-a"])
        ctrl.start_export(compositor, settings)

        assert captured["compositor"] is compositor
        assert captured["settings"] is settings
        ctrl.cleanup()
