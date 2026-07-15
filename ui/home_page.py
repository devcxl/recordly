"""Recordly 首页组件 — 操作按钮 + 项目画廊"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from core.project_manager import ProjectManager
from ui.project_gallery import ProjectGallery


class HomePage(QWidget):
    """首页：标题区域 + ProjectGallery"""

    record_requested = pyqtSignal()
    open_project_requested = pyqtSignal()
    project_opened = pyqtSignal(str)

    def __init__(self, project_manager: ProjectManager, parent=None):
        super().__init__(parent)
        self._manager = project_manager
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setStyleSheet("background-color: #121212;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部区域
        header = self._build_header()
        layout.addWidget(header)

        # 项目画廊
        self._gallery = ProjectGallery(self._manager, self)
        layout.addWidget(self._gallery, 1)

    def _build_header(self) -> QWidget:
        widget = QWidget(self)
        widget.setFixedHeight(180)
        widget.setStyleSheet("background-color: #121212;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(32, 40, 32, 24)
        layout.setSpacing(8)

        # 标题
        title = QLabel("Recordly", widget)
        title.setFont(QFont("sans-serif", 36, QFont.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel("录制、编辑、导出 — 快速创建屏幕录制", widget)
        subtitle.setFont(QFont("sans-serif", 14))
        subtitle.setStyleSheet("color: #999; background: transparent;")
        layout.addWidget(subtitle)

        layout.addSpacing(12)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._record_btn = QPushButton("\U0001f3ac 开始录制", widget)
        self._record_btn.setCursor(Qt.PointingHandCursor)
        self._record_btn.setFixedHeight(40)
        self._record_btn.setStyleSheet(
            """
            QPushButton {
                font-size: 15px;
                padding: 8px 24px;
                font-weight: bold;
            }
            """
        )

        self._open_btn = QPushButton("\U0001f4c2 打开项目", widget)
        self._open_btn.setCursor(Qt.PointingHandCursor)
        self._open_btn.setFixedHeight(40)
        self._open_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3a3a3a;
                color: #ccc;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 15px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                color: white;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            """
        )

        btn_row.addWidget(self._record_btn)
        btn_row.addWidget(self._open_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return widget

    def _connect_signals(self):
        self._record_btn.clicked.connect(self.record_requested.emit)
        self._open_btn.clicked.connect(self.open_project_requested.emit)
        self._gallery.project_opened.connect(self.project_opened.emit)

    def refresh_projects(self):
        """刷新项目画廊"""
        self._gallery.refresh()
