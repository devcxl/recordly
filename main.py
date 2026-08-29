"""Recordly 程序入口"""

import logging
import os
import sys
from PyQt5.QtWidgets import QApplication

from app.config import AppConfig
from app.main_window import MainWindow
from app.resources import load_text


def main():
    log_level = logging.DEBUG if os.environ.get("RECORDLY_DEBUG") == "1" else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s [%(name)s] %(message)s", stream=sys.stderr)

    # 清扫崩溃残留的录屏临时帧文件（无项目目录录制时遗留）
    try:
        from core.screen_capture import cleanup_stale_temp_frames
        removed = cleanup_stale_temp_frames()
        if removed:
            logging.getLogger(__name__).warning(
                "清理了 %d 个崩溃残留的录屏临时文件", removed)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Recordly")
    app.setOrganizationName("Recordly")
    app.setApplicationVersion("1.3.0")
    stylesheet = load_text("style.qss")
    if stylesheet:
        app.setStyleSheet(stylesheet)

    config = AppConfig.load()
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()