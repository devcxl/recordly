"""设置对话框 — 多 tab 分类管理"""

from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QSpinBox, QSlider, QComboBox,
    QCheckBox, QPushButton, QFileDialog, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QDialogButtonBox, QMessageBox,
)
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeySequence
from app.config import AppConfig
from core.project import Project
from core.shortcuts import ShortcutRegistry


_STYLE = """
QDialog { background: #1e1e1e; color: white; }
QTabWidget::pane { background: #2d2d2d; border: 1px solid #3d3d3d; }
QTabBar::tab { background: #2d2d2d; color: #aaa; padding: 8px 20px; border: none; }
QTabBar::tab:selected { background: #3d3d3d; color: white; }
QLabel { color: #ccc; font-size: 13px; }
QSpinBox, QComboBox, QLineEdit {
    background: #3d3d3d; color: white; border: 1px solid #555;
    border-radius: 4px; padding: 4px 8px;
}
QCheckBox { color: #ccc; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QPushButton {
    background: #0078D4; color: white; border: none;
    border-radius: 4px; padding: 6px 24px; font-size: 13px;
}
QPushButton:hover { background: #1a8ae8; }
QSlider::groove:horizontal {
    height: 6px; background: #3d3d3d; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #0078D4; width: 16px; height: 16px;
    margin: -5px 0; border-radius: 8px;
}
QSlider::sub-page:horizontal { background: #0078D4; border-radius: 3px; }
"""


class _ShortcutCaptureDialog(QDialog):
    """捕获并校验单个快捷键的私有对话框。"""

    _MODIFIER_KEYS = {
        Qt.Key_Control,
        Qt.Key_Alt,
        Qt.Key_Shift,
        Qt.Key_Meta,
        Qt.Key_AltGr,
    }

    def __init__(self, draft_registry, action_id, parent=None):
        super().__init__(parent)
        self._draft_registry = draft_registry
        self._action_id = action_id
        self._portable_text = None
        self.setWindowTitle("按下新快捷键")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("请按下新的快捷键"))
        self._sequence_label = QLabel("等待输入…")
        self._sequence_label.setAlignment(Qt.AlignCenter)
        self._sequence_label.setFocusPolicy(Qt.StrongFocus)
        self._sequence_label.installEventFilter(self)
        layout.addWidget(self._sequence_label)
        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #ff6b6b;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._confirm_button = buttons.button(QDialogButtonBox.Ok)
        self._confirm_button.setEnabled(False)
        for button in buttons.buttons():
            button.setFocusPolicy(Qt.NoFocus)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def showEvent(self, event):
        super().showEvent(event)
        self._sequence_label.setFocus(Qt.OtherFocusReason)

    def eventFilter(self, watched, event):
        if watched is self._sequence_label and event.type() == QEvent.KeyPress:
            self.keyPressEvent(event)
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            event.accept()
            return
        if event.key() in self._MODIFIER_KEYS:
            self._show_error("请按下包含非修饰键的快捷键")
            event.accept()
            return

        portable_text = QKeySequence(
            int(event.modifiers()) | event.key(),
        ).toString(QKeySequence.PortableText)
        if not portable_text:
            self._show_error("快捷键无效，请重新输入")
            event.accept()
            return

        self._portable_text = portable_text
        self._sequence_label.setText(
            SettingsDialog._native_shortcut_text(portable_text))
        self._error_label.hide()
        self._confirm_button.setEnabled(True)
        event.accept()

    def _on_accept(self):
        if self._portable_text is None:
            self._show_error("请按下包含非修饰键的快捷键")
            return

        validation = self._draft_registry.validate(
            self._action_id,
            self._portable_text,
        )
        if validation.ok:
            self.accept()
            return

        if validation.code == "SHORTCUT_CONFLICT":
            action = next(
                action
                for action in self._draft_registry.actions()
                if action.action_id == validation.conflicting_action_id
            )
            self._show_error(f"与「{action.display_name}」冲突，请重新设置")
            return
        self._show_error("快捷键无效，请重新输入")

    def _show_error(self, message):
        self._error_label.setText(message)
        self._error_label.show()


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._shortcut_draft = ShortcutRegistry(config.shortcuts)
        self._shortcut_actions = self._shortcut_draft.actions()
        self.setWindowTitle("设置")
        self.setMinimumSize(720, 560)
        self.resize(720, 560)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "通用")
        self._tabs.addTab(self._build_shortcut_tab(), "快捷键")
        self._tabs.addTab(self._build_cursor_tab(), "光标")
        self._tabs.addTab(self._build_zoom_tab(), "缩放")
        self._tabs.addTab(self._build_preview_tab(), "预览")
        self._tabs.addTab(self._build_about_tab(), "关于")

        layout.addWidget(self._tabs, 1)

        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(16, 12, 16, 12)
        btn_bar.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("background: #3d3d3d;")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        btn_bar.addWidget(cancel_btn)
        btn_bar.addWidget(save_btn)
        layout.addLayout(btn_bar)

    def _row(self, label, widget):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addStretch()
        row.addWidget(widget)
        return row

    # ── 快捷键 ─────────────────────────────────────────────

    def _build_shortcut_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        self._shortcut_table = QTableWidget(len(self._shortcut_actions), 5)
        self._shortcut_table.setHorizontalHeaderLabels(
            ["分类", "操作", "当前快捷键", "编辑", "恢复默认"])
        self._shortcut_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._shortcut_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._shortcut_table.verticalHeader().setVisible(False)
        self._shortcut_table.setAlternatingRowColors(True)
        header = self._shortcut_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        for row, action in enumerate(self._shortcut_actions):
            self._shortcut_table.setItem(
                row, 0, QTableWidgetItem(action.category))
            self._shortcut_table.setItem(
                row, 1, QTableWidgetItem(action.display_name))
            self._shortcut_table.setItem(
                row,
                2,
                QTableWidgetItem(self._native_shortcut_text(
                    self._shortcut_draft.binding(action.action_id))),
            )
            edit_button = QPushButton("编辑")
            edit_button.clicked.connect(
                lambda _checked=False, action_id=action.action_id:
                self._edit_shortcut(action_id))
            self._shortcut_table.setCellWidget(row, 3, edit_button)
            reset_button = QPushButton("恢复默认")
            reset_button.clicked.connect(
                lambda _checked=False, action_id=action.action_id:
                self._reset_shortcut(action_id))
            self._shortcut_table.setCellWidget(row, 4, reset_button)

        self._shortcut_table.cellDoubleClicked.connect(
            self._on_shortcut_cell_double_clicked)
        layout.addWidget(self._shortcut_table, 1)

        self._shortcut_error_label = QLabel()
        self._shortcut_error_label.setStyleSheet("color: #ff6b6b;")
        self._shortcut_error_label.hide()
        layout.addWidget(self._shortcut_error_label)

        restore_all_button = QPushButton("恢复全部默认")
        restore_all_button.clicked.connect(self._reset_all_shortcuts)
        layout.addWidget(restore_all_button, alignment=Qt.AlignRight)
        return w

    @staticmethod
    def _native_shortcut_text(portable_text):
        return QKeySequence(
            portable_text,
            QKeySequence.PortableText,
        ).toString(QKeySequence.NativeText)

    def _on_shortcut_cell_double_clicked(self, row, column):
        if column == 2:
            self._edit_shortcut(self._shortcut_actions[row].action_id)

    def _edit_shortcut(self, action_id):
        capture_dialog = _ShortcutCaptureDialog(
            self._shortcut_draft,
            action_id,
            self,
        )
        if capture_dialog.exec_() != QDialog.Accepted:
            return

        bindings = self._shortcut_draft.bindings()
        bindings[action_id] = capture_dialog._portable_text
        validation = self._shortcut_draft.replace_bindings(bindings)
        if not validation.ok:
            self._show_shortcut_validation_error(validation)
            return

        self._refresh_shortcut_table()
        self._shortcut_error_label.hide()

    def _refresh_shortcut_table(self):
        for row, action in enumerate(self._shortcut_actions):
            self._shortcut_table.item(row, 2).setText(
                self._native_shortcut_text(
                    self._shortcut_draft.binding(action.action_id)))

    def _show_shortcut_validation_error(self, validation):
        if validation.code == "SHORTCUT_CONFLICT":
            action = next(
                action
                for action in self._shortcut_actions
                if action.action_id == validation.conflicting_action_id
            )
            message = f"与「{action.display_name}」冲突，请重新设置"
        elif validation.code == "SHORTCUT_EMPTY_SEQUENCE":
            message = "请按下包含非修饰键的快捷键"
        else:
            message = "快捷键无效，请重新输入"
        self._shortcut_error_label.setText(message)
        self._shortcut_error_label.show()

    def _reset_shortcut(self, action_id):
        validation = self._shortcut_draft.reset_binding(action_id)
        if not validation.ok:
            self._show_shortcut_validation_error(validation)
            return
        self._refresh_shortcut_table()
        self._shortcut_error_label.hide()

    def _reset_all_shortcuts(self):
        confirmation = QMessageBox.question(
            self,
            "恢复全部默认快捷键",
            "确定要恢复全部默认快捷键吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmation != QMessageBox.Yes:
            return
        self._shortcut_draft.reset_all()
        self._refresh_shortcut_table()
        self._shortcut_error_label.hide()

    # ── 通用 ───────────────────────────────────────────────

    def _build_general_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(10, 120)
        self._fps_spin.setValue(self._config.default_fps)
        layout.addLayout(self._row("默认帧率 (FPS):", self._fps_spin))

        self._bitrate_edit = QLineEdit(self._config.default_bitrate)
        self._bitrate_edit.setFixedWidth(100)
        layout.addLayout(self._row("默认码率:", self._bitrate_edit))

        # ── 项目目录 ──
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("项目目录:"))
        self._projects_dir_edit = QLineEdit(self._config.projects_dir)
        self._projects_dir_edit.setReadOnly(True)
        dir_row.addWidget(self._projects_dir_edit, 1)
        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._on_browse_projects_dir)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        layout.addStretch()
        return w

    # ── 光标 ───────────────────────────────────────────────

    def _build_cursor_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("光标大小:"))
        self._cursor_slider = QSlider(Qt.Horizontal)
        self._cursor_slider.setRange(16, 96)
        self._cursor_slider.setValue(self._config.cursor_size)
        self._cursor_size_label = QLabel(str(self._config.cursor_size))
        self._cursor_size_label.setFixedWidth(30)
        self._cursor_slider.valueChanged.connect(
            lambda v: self._cursor_size_label.setText(str(v)))
        size_row.addWidget(self._cursor_slider, 1)
        size_row.addWidget(self._cursor_size_label)
        layout.addLayout(size_row)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["dark", "light"])
        self._theme_combo.setCurrentText(self._config.cursor_theme)
        self._theme_combo.setFixedWidth(120)
        layout.addLayout(self._row("光标主题:", self._theme_combo))

        self._cursor_style_combo = QComboBox()
        for label, value in (
            ("圆点", "dot"),
            ("圆环", "ring"),
            ("聚光", "spotlight"),
            ("经典箭头", "arrow"),
        ):
            self._cursor_style_combo.addItem(label, value)
        style_index = self._cursor_style_combo.findData(
            self._config.cursor_style)
        self._cursor_style_combo.setCurrentIndex(
            style_index if style_index >= 0 else 0)
        self._cursor_style_combo.setFixedWidth(120)
        layout.addLayout(self._row("光标样式:", self._cursor_style_combo))

        self._trail_check = QCheckBox("启用鼠标拖尾")
        self._trail_check.setChecked(self._config.trail_enabled)
        layout.addWidget(self._trail_check)

        layout.addStretch()
        return w

    # ── 缩放 ───────────────────────────────────────────────

    def _build_zoom_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        ratio_row = QHBoxLayout()
        ratio_row.addWidget(QLabel("缩放框大小 (%):"))
        self._zoom_ratio_slider = QSlider(Qt.Horizontal)
        self._zoom_ratio_slider.setRange(10, 90)
        self._zoom_ratio_slider.setValue(int(self._config.zoom_rect_ratio * 100))
        self._zoom_ratio_label = QLabel(f"{int(self._config.zoom_rect_ratio * 100)}%")
        self._zoom_ratio_label.setFixedWidth(40)
        self._zoom_ratio_slider.valueChanged.connect(
            lambda v: self._zoom_ratio_label.setText(f"{v}%"))
        ratio_row.addWidget(self._zoom_ratio_slider, 1)
        ratio_row.addWidget(self._zoom_ratio_label)
        layout.addLayout(ratio_row)

        layout.addStretch()
        return w

    # ── 预览 ───────────────────────────────────────────────

    def _build_preview_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("预览质量:"))
        self._quality_slider = QSlider(Qt.Horizontal)
        self._quality_slider.setRange(10, 100)
        self._quality_slider.setValue(int(self._config.preview_quality * 100))
        self._quality_label = QLabel(f"{self._config.preview_quality:.1f}")
        self._quality_label.setFixedWidth(30)
        self._quality_slider.valueChanged.connect(
            lambda v: self._quality_label.setText(f"{v / 100:.1f}"))
        quality_row.addWidget(self._quality_slider, 1)
        quality_row.addWidget(self._quality_label)
        layout.addLayout(quality_row)

        layout.addStretch()
        return w

    # ── 关于 ───────────────────────────────────────────────

    def _build_about_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        layout.addWidget(QLabel(f"Recordly v{Project.VERSION}"))
        layout.addWidget(QLabel("开源演示视频录制与编辑工具"))
        layout.addSpacing(12)
        layout.addWidget(QLabel("作者：devcxl"))
        layout.addWidget(QLabel("GitHub：https://github.com/devcxl/recordly"))
        layout.addSpacing(8)
        layout.addWidget(QLabel("基于 PyQt5 + FFmpeg"))
        layout.addWidget(QLabel(""))
        layout.addStretch()
        return w

    # ── 事件 ───────────────────────────────────────────────

    def _on_browse_projects_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择项目目录", self._config.projects_dir)
        if path:
            self._projects_dir_edit.setText(path)

    # ── 保存 ───────────────────────────────────────────────

    def _on_save(self):
        registry = ShortcutRegistry()
        validation = registry.replace_bindings(self._shortcut_draft.bindings())
        if not validation.ok:
            self._show_shortcut_validation_error(validation)
            return

        self._config.default_fps = self._fps_spin.value()
        self._config.default_bitrate = self._bitrate_edit.text()
        self._config.projects_dir = self._projects_dir_edit.text()
        self._config.cursor_size = self._cursor_slider.value()
        self._config.cursor_theme = self._theme_combo.currentText()
        self._config.cursor_style = self._cursor_style_combo.currentData() or "dot"
        self._config.trail_enabled = self._trail_check.isChecked()
        self._config.zoom_rect_ratio = self._zoom_ratio_slider.value() / 100.0
        self._config.preview_quality = self._quality_slider.value() / 100.0
        self._config.shortcuts = registry.bindings()
        self._config.save()
        self.accept()
