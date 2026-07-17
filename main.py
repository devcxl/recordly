"""Recordly 程序入口"""

import logging
import os
import sys
from PyQt5.QtWidgets import QApplication

from app.config import AppConfig
from app.main_window import MainWindow


def _resource_path(relative: str) -> str:
    """PyInstaller 打包后资源在 sys._MEIPASS，开发时相对于 __file__"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, relative)


def _load_stylesheet() -> str:
    try:
        with open(_resource_path(os.path.join("resources", "style.qss")), encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return ""


def main():
    log_level = logging.DEBUG if os.environ.get("RECORDLY_DEBUG") == "1" else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s [%(name)s] %(message)s", stream=sys.stderr)

    app = QApplication(sys.argv)
    app.setApplicationName("Recordly")
    app.setOrganizationName("Recordly")
    app.setApplicationVersion("1.0.0")
    stylesheet = _load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    config = AppConfig.load()
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()