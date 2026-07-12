"""ProjectCard 缩略图卡片组件"""

import os

from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QLineEdit, QMenu, QHBoxLayout, QWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QFont, QMouseEvent, QPainter, QColor, QBrush

from core.project_manager import ProjectSummary


class ProjectCard(QFrame):
    clicked = pyqtSignal(str)
    rename_requested = pyqtSignal(str, str)
    delete_requested = pyqtSignal(str)

    CARD_WIDTH = 240
    CARD_HEIGHT = 180
    THUMB_HEIGHT = 135

    def __init__(self, summary: ProjectSummary, parent=None):
        super().__init__(parent)
        self._summary = summary
        self._editing = False

        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()
        self._apply_style()

    # ── UI 构建 ────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 缩略图
        self._thumb = QLabel(self)
        self._thumb.setFixedSize(self.CARD_WIDTH, self.THUMB_HEIGHT)
        self._thumb.setScaledContents(True)
        self._thumb.setAlignment(Qt.AlignCenter)
        self._load_thumbnail()
        layout.addWidget(self._thumb)

        # 底部信息区
        info = QWidget(self)
        info.setFixedHeight(self.CARD_HEIGHT - self.THUMB_HEIGHT)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(8, 4, 8, 4)
        info_layout.setSpacing(0)

        # 项目名称（可双击编辑）
        self._name_label = QLabel(self._summary.name, info)
        self._name_label.setWordWrap(True)
        self._name_label.setFont(QFont("sans-serif", 10, QFont.Bold))
        info_layout.addWidget(self._name_label)

        # 编辑框（默认隐藏）
        self._name_edit = QLineEdit(self._summary.name, info)
        self._name_edit.setVisible(False)
        self._name_edit.returnPressed.connect(self._finish_rename)
        info_layout.addWidget(self._name_edit)

        # 时长
        duration_text = f"{int(self._summary.duration)//60:02d}:{int(self._summary.duration)%60:02d}"
        self._duration_label = QLabel(duration_text, info)
        self._duration_label.setFont(QFont("monospace", 9))
        self._duration_label.setStyleSheet("color: #888;")
        info_layout.addWidget(self._duration_label)

        info_layout.addStretch()
        layout.addWidget(info)

    def _apply_style(self):
        self.setStyleSheet("""
            ProjectCard {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
            }
            ProjectCard:hover {
                border: 1px solid #4A90D9;
                background-color: #252525;
            }
            QLabel {
                background: transparent;
                color: #eee;
            }
            QLineEdit {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #4A90D9;
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 10px;
            }
        """)

    # ── 缩略图 ─────────────────────────────────────────────

    def _load_thumbnail(self):
        thumb_path = self._summary.thumbnail_path
        if thumb_path and os.path.isfile(thumb_path):
            pixmap = QPixmap(thumb_path)
            if not pixmap.isNull():
                self._thumb.setPixmap(pixmap)
                return

        # 加载失败 → 占位图
        self._draw_fallback_thumbnail()

    def _draw_fallback_thumbnail(self):
        pixmap = QPixmap(self.CARD_WIDTH, self.THUMB_HEIGHT)
        pixmap.fill(QColor("#3a3a3a"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#888"))
        painter.setFont(QFont("sans-serif", 12))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, self._summary.name)
        painter.end()
        self._thumb.setPixmap(pixmap)

    # ── 事件 ───────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._summary.path)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        # 双击名称区域 → 进入编辑模式
        child_pos = self._name_label.mapFrom(self, event.pos())
        if self._name_label.rect().contains(child_pos):
            self._start_editing()
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #4A90D9;
            }
        """)
        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(
            lambda: self.delete_requested.emit(self._summary.path))
        menu.exec_(event.globalPos())

    # ── 名称编辑 ──────────────────────────────────────────

    def _start_editing(self):
        if self._editing:
            return
        self._editing = True
        self._name_label.setVisible(False)
        self._name_edit.setText(self._summary.name)
        self._name_edit.setVisible(True)
        self._name_edit.setFocus()
        self._name_edit.selectAll()

    def _finish_rename(self):
        new_name = self._name_edit.text().strip()
        if not new_name:
            new_name = self._summary.name

        self._name_edit.setVisible(False)
        self._name_label.setText(new_name)
        self._name_label.setVisible(True)
        self._editing = False

        if new_name != self._summary.name:
            self.rename_requested.emit(self._summary.path, new_name)

    def focusOutEvent(self, event):
        if self._editing:
            self._finish_rename()
        super().focusOutEvent(event)
