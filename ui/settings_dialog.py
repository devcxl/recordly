"""设置对话框 — 多 tab 分类管理"""

from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QSpinBox, QSlider, QComboBox,
    QCheckBox, QPushButton, QFileDialog, QLineEdit,
)
from PyQt5.QtCore import Qt
from app.config import AppConfig


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


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("设置")
        self.setFixedSize(520, 420)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "通用")
        tabs.addTab(self._build_cursor_tab(), "光标")
        tabs.addTab(self._build_zoom_tab(), "缩放")
        tabs.addTab(self._build_preview_tab(), "预览")
        tabs.addTab(self._build_about_tab(), "关于")

        layout.addWidget(tabs, 1)

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

        layout.addWidget(QLabel("Recordly v1.0"))
        layout.addWidget(QLabel("开源演示视频录制与编辑工具"))
        layout.addSpacing(12)
        layout.addWidget(QLabel("基于 PyQt5 + FFmpeg"))
        layout.addWidget(QLabel(""))
        layout.addStretch()
        return w

    # ── 保存 ───────────────────────────────────────────────

    def _on_save(self):
        self._config.default_fps = self._fps_spin.value()
        self._config.default_bitrate = self._bitrate_edit.text()
        self._config.cursor_size = self._cursor_slider.value()
        self._config.cursor_theme = self._theme_combo.currentText()
        self._config.trail_enabled = self._trail_check.isChecked()
        self._config.zoom_rect_ratio = self._zoom_ratio_slider.value() / 100.0
        self._config.preview_quality = self._quality_slider.value() / 100.0
        self._config.save()
        self.accept()
