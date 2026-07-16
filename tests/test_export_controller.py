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
