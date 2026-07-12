"""Recordly 程序入口"""

import sys
from PyQt5.QtWidgets import QApplication

from app.config import AppConfig
from app.main_window import MainWindow

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}
QToolBar {
    background: #252526;
    border-bottom: 1px solid #323232;
    spacing: 4px;
    padding: 4px 8px;
}
QToolBar QToolButton {
    color: #cccccc;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 13px;
}
QToolBar QToolButton:hover {
    background: #3a3a3a;
    border-color: #555;
}
QToolBar QToolButton:checked {
    background: #094771;
    color: white;
    border-color: #0078D4;
}
QPushButton {
    color: white;
    background: #0078D4;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background: #1a8ad4;
}
QPushButton:pressed {
    background: #0068b4;
}
QPushButton:disabled {
    background: #3a3a3a;
    color: #666;
}
QToolButton {
    color: #ccc;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 16px;
    min-width: 32px;
    min-height: 28px;
}
QToolButton:hover {
    background: #3a3a3a;
    border-color: #555;
}
QToolButton:checked {
    background: #094771;
    color: white;
    border-color: #0078D4;
}
QToolButton:disabled {
    color: #555;
}
QScrollArea {
    border: none;
    background: #1e1e1e;
}
QScrollBar:vertical {
    background: #1e1e1e;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #424242;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #1e1e1e;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #424242;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QComboBox {
    background: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #424242;
    border-radius: 4px;
    padding: 4px 8px;
}
QComboBox:hover {
    border-color: #0078D4;
}
QComboBox QAbstractItemView {
    background: #2d2d2d;
    color: #d4d4d4;
    selection-background-color: #094771;
    border: 1px solid #424242;
}
QLineEdit, QSpinBox {
    background: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #424242;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus, QSpinBox:focus {
    border-color: #0078D4;
}
QCheckBox {
    color: #d4d4d4;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
QProgressBar {
    border: 1px solid #323232;
    border-radius: 4px;
    background: #2d2d2d;
    text-align: center;
    color: white;
}
QProgressBar::chunk {
    background: #0078D4;
    border-radius: 3px;
}
QMenu {
    background: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #424242;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #094771;
}
QMenu::separator {
    height: 1px;
    background: #424242;
    margin: 4px 8px;
}
QMessageBox {
    background: #1e1e1e;
    color: #d4d4d4;
}
QMessageBox QLabel {
    color: #d4d4d4;
}
QMessageBox QPushButton {
    min-width: 80px;
}
QSplitter::handle {
    background: #323232;
}
QStatusBar {
    background: #007acc;
    color: white;
    border-top: none;
    font-size: 12px;
}
QStatusBar QLabel {
    color: white;
    padding: 2px 8px;
}
QHeaderView::section {
    background: #252526;
    color: #d4d4d4;
    border: 1px solid #323232;
    padding: 4px;
}
QTabWidget::pane {
    border: 1px solid #323232;
    background: #1e1e1e;
}
QTabBar::tab {
    background: #2d2d2d;
    color: #999;
    border: 1px solid #323232;
    padding: 6px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: #1e1e1e;
    color: white;
    border-bottom: 2px solid #0078D4;
}
QTabBar::tab:hover:!selected {
    background: #3a3a3a;
}
QDialog {
    background: #1e1e1e;
    color: #d4d4d4;
}
QLabel {
    color: #d4d4d4;
}
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Recordly")
    app.setOrganizationName("Recordly")
    app.setApplicationVersion("1.0.0")
    app.setStyleSheet(DARK_STYLESHEET)

    config = AppConfig.load()
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()