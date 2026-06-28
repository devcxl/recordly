"""pytest 全局配置与 fixture"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Qt 是否可用（用于条件跳过 GUI 测试） ─────────────────
_HAS_QT = False
try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance()
    if _app is None:
        _app = QApplication(sys.argv)
    _HAS_QT = True
except Exception:
    pass

requires_qt = pytest.mark.skipif(
    not _HAS_QT,
    reason="PyQt5 不可用或缺少系统 GL 库",
)


@pytest.fixture(scope="session")
def qapp():
    """单例 QApplication（仅 enable QT 时生效）"""
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# ── 合成测试用的帧 ──────────────────────────────────────

@pytest.fixture
def synthetic_frame():
    """返回一张 320×240 纯色 RGB 帧（numpy uint8）"""
    import numpy as np
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[:, :, 0] = 30
    frame[:, :, 1] = 60
    frame[:, :, 2] = 90
    return frame


@pytest.fixture
def synthetic_pil():
    """返回一张 320×240 纯色 PIL Image"""
    from PIL import Image
    frame = Image.new("RGB", (320, 240), (30, 60, 90))
    return frame
