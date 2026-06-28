"""Recordly 程序入口"""

import sys
from PyQt5.QtWidgets import QApplication

from app.config import AppConfig
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Recordly")
    app.setOrganizationName("Recordly")
    app.setApplicationVersion("1.0.0")

    config = AppConfig.load()
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
