"""resources 模块及应用图标/托盘图标相关测试。"""

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from app.config import AppConfig
from app.resources import resource_path, load_text, exists, load_icon, get_app_icon
from app.main_window import MainWindow


def test_resource_path_and_exists():
    assert exists("icons", "recordly.svg")
    assert not exists("icons", "non_existent_file.xyz")


def test_load_text():
    assert load_text("non_existent_file.xyz") == ""
    # style.qss should be loaded if exists
    if exists("style.qss"):
        assert len(load_text("style.qss")) > 0


def test_load_icon(qapp):
    icon = load_icon("icons", "recordly.svg")
    assert not icon.isNull()
    pix = icon.pixmap(32, 32)
    assert not pix.isNull()
    assert pix.width() == 32 and pix.height() == 32

    bad_icon = load_icon("icons", "not_exist.png")
    assert bad_icon.isNull()


def test_get_app_icon(qapp):
    icon = get_app_icon()
    assert not icon.isNull()
    pix = icon.pixmap(64, 64)
    assert not pix.isNull()
    assert pix.width() == 64 and pix.height() == 64


def test_main_window_tray_and_window_icon(qapp, tmp_path):
    config = AppConfig(projects_dir=str(tmp_path))
    window = MainWindow(config)
    try:
        assert not window.windowIcon().isNull()
        assert not window._tray.icon().isNull()
    finally:
        window._tray.hide()
        window.close()
