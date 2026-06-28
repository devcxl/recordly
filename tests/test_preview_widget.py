"""Tests for ui/preview_widget.py — 需要 PyQt5 可用环境"""

import pytest


def _has_pyqt5():
    """检查 PyQt5 是否可导入"""
    try:
        from PyQt5.QtWidgets import QWidget  # noqa: F401
        return True
    except ImportError:
        return False


class TestPreviewWidgetImport:
    def test_importable(self):
        """验证模块可导入"""
        if not _has_pyqt5():
            pytest.skip("PyQt5 不可用")
        from ui.preview_widget import PreviewWidget
        assert PreviewWidget is not None

    @pytest.mark.skipif(not _has_pyqt5(), reason="PyQt5 不可用")
    def test_creation(self, qapp):
        from ui.preview_widget import PreviewWidget
        w = PreviewWidget()
        assert w is not None

    @pytest.mark.skipif(not _has_pyqt5(), reason="PyQt5 不可用")
    def test_label_initialized(self, qapp):
        from ui.preview_widget import PreviewWidget
        w = PreviewWidget()
        assert hasattr(w, '_label') or hasattr(w, 'label')
