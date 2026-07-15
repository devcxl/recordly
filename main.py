"""Recordly 程序入口"""

import os
import sys
from PyQt5.QtWidgets import QApplication

from app.config import AppConfig
from app.main_window import MainWindow


def _load_stylesheet() -> str:
    qss_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
    try:
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return ""


def main():
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