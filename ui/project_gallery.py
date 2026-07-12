"""ProjectGallery 卡片网格容器"""

from PyQt5.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QMessageBox, QLayout, QSizePolicy, QLabel,
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize

from core.project_manager import ProjectManager, ProjectSummary
from ui.project_card import ProjectCard


class FlowLayout(QLayout):
    """自适应换行布局（参考 Qt 官方 FlowLayout 示例）"""

    def __init__(self, parent=None, margin=0, spacing=10):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def __del__(self):
        while self._items:
            item = self._items.pop()
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), False)

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(),
                      margins.top() + margins.bottom())
        return size

    def sizeHint(self):
        return self.minimumSize()

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, True)

    def _do_layout(self, rect, apply):
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(),
            -margins.right(), -margins.bottom(),
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            widget = item.widget()
            if widget is None:
                continue
            hint = widget.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y()


class ProjectGallery(QScrollArea):
    """卡片网格容器，内部使用 FlowLayout 自适应排列 ProjectCard"""

    project_opened = pyqtSignal(str)
    project_deleted = pyqtSignal(str)
    project_renamed = pyqtSignal(str, str)

    def __init__(self, project_manager: ProjectManager, parent=None):
        super().__init__(parent)
        self._manager = project_manager

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #121212;
            }
        """)

        # 内部容器：垂直布局，上方 FlowLayout 区域，下方空状态居中
        self._container = QWidget(self)
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)

        # FlowLayout 承载卡片
        self._flow_widget = QWidget()
        self._flow_layout = FlowLayout(self._flow_widget, margin=16, spacing=12)
        self._flow_widget.setLayout(self._flow_layout)
        self._container_layout.addWidget(self._flow_widget)

        # 空状态标签（stretch 使其在无卡片时居中）
        self._empty_label = QLabel("还没有项目，开始录制吧！")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #666; font-size: 16px;")
        self._container_layout.addWidget(self._empty_label, 1)

        self.setWidget(self._container)

    # ── 公共方法 ──────────────────────────────────────────

    def set_projects(self, summaries: list[ProjectSummary]):
        """清空并重新填充 ProjectCard"""
        self._clear_cards()

        if not summaries:
            self._empty_label.setVisible(True)
            return

        self._empty_label.setVisible(False)
        for summary in summaries:
            card = ProjectCard(summary, self._flow_widget)
            card.clicked.connect(self.project_opened.emit)
            card.delete_requested.connect(self._on_delete_requested)
            card.rename_requested.connect(self._on_rename_requested)
            self._flow_layout.addWidget(card)

    def refresh(self):
        """重新调用 ProjectManager.list_projects() 并刷新显示"""
        summaries = self._manager.list_projects()
        self.set_projects(summaries)

    # ── 内部方法 ──────────────────────────────────────────

    def _clear_cards(self):
        """清空布局中的所有卡片"""
        while self._flow_layout.count():
            item = self._flow_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

    def _on_delete_requested(self, project_path: str):
        """删除确认 → 发射 project_deleted"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这个项目吗？此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.project_deleted.emit(project_path)

    def _on_rename_requested(self, project_path: str, new_name: str):
        """只发射信号，由 MainWindow 统一处理"""
        self.project_renamed.emit(project_path, new_name)
