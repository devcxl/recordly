"""导出设置对话框 — 格式/分辨率/宽高比/质量/帧率"""

import os

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QLabel, QPushButton, QFileDialog, QSpinBox, QCheckBox,
    QWidget,
)

from core.aspect_ratio import ASPECT_RATIO_PRESETS, RESOLUTION_PRESETS


_CUSTOM_RESOLUTION = "自定义..."


class ExportDialog(QDialog):
    """增强导出对话框，支持格式、分辨率、宽高比预设、质量、GIF 帧率和循环设置"""

    def __init__(self, parent=None, default_dir="", default_fps=30):
        super().__init__(parent)
        self.setWindowTitle("导出视频")
        self.setMinimumWidth(480)

        self._output_path = ""
        self._default_dir = default_dir

        layout = QVBoxLayout(self)

        # 格式选择
        layout.addWidget(QLabel("导出格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "GIF"])
        layout.addWidget(self.format_combo)

        # 分辨率
        layout.addWidget(QLabel("分辨率:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(list(RESOLUTION_PRESETS.keys()) + [_CUSTOM_RESOLUTION])
        self.resolution_combo.setCurrentText("原始（不限制）")
        layout.addWidget(self.resolution_combo)

        # 自定义分辨率输入（默认隐藏）
        self._custom_widget = QWidget()
        custom_layout = QHBoxLayout(self._custom_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(QLabel("宽:"))
        self._custom_width = QSpinBox()
        self._custom_width.setRange(2, 7680)
        self._custom_width.setSingleStep(2)
        self._custom_width.setValue(1920)
        self._custom_width.setSuffix(" px")
        custom_layout.addWidget(self._custom_width)
        custom_layout.addWidget(QLabel("高:"))
        self._custom_height = QSpinBox()
        self._custom_height.setRange(2, 4320)
        self._custom_height.setSingleStep(2)
        self._custom_height.setValue(1080)
        self._custom_height.setSuffix(" px")
        custom_layout.addWidget(self._custom_height)
        custom_layout.addStretch()
        self._custom_widget.setVisible(False)
        layout.addWidget(self._custom_widget)

        # 宽高比
        layout.addWidget(QLabel("宽高比:"))
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(ASPECT_RATIO_PRESETS)
        self.ratio_combo.setCurrentText("native")
        layout.addWidget(self.ratio_combo)

        # 质量 (MP4)
        layout.addWidget(QLabel("质量:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(
            ["原始 (100%)", "高 (90%)", "好 (75%)", "中 (60%)"])
        layout.addWidget(self.quality_combo)

        # GIF 帧率
        layout.addWidget(QLabel("GIF 帧率:"))
        self.gif_fps = QSpinBox()
        self.gif_fps.setRange(5, 30)
        self.gif_fps.setValue(min(default_fps, 15))
        layout.addWidget(self.gif_fps)

        # GIF 循环
        self.gif_loop = QCheckBox("GIF 循环播放")
        self.gif_loop.setChecked(True)
        layout.addWidget(self.gif_loop)

        # 按钮
        btn_layout = QHBoxLayout()
        self.browse_btn = QPushButton("选择保存路径...")
        self.browse_btn.clicked.connect(self._browse)
        self.export_btn = QPushButton("导出")
        self.export_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.browse_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

        # 信号连接
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        self.resolution_combo.currentTextChanged.connect(self._on_resolution_changed)
        self._on_format_changed("MP4")

    def _on_format_changed(self, fmt: str):
        is_gif = fmt == "GIF"
        self.gif_fps.setVisible(is_gif)
        self.gif_loop.setVisible(is_gif)
        self.quality_combo.setVisible(not is_gif)

    def _on_resolution_changed(self, text: str):
        self._custom_widget.setVisible(text == _CUSTOM_RESOLUTION)

    def _browse(self):
        fmt = self.format_combo.currentText()
        ext = ".gif" if fmt == "GIF" else ".mp4"
        filter_str = "GIF (*.gif)" if fmt == "GIF" else "MP4 (*.mp4)"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存为", self._default_dir, filter_str)
        if path:
            # 确保路径包含与格式匹配的扩展名（Linux 上 Qt 不会自动追加）
            if not path.lower().endswith(ext):
                path += ext
            self._output_path = path
            self.browse_btn.setText(os.path.basename(path))

    @property
    def output_path(self) -> str:
        return self._output_path

    @property
    def resolution_preset(self) -> str:
        return self.resolution_combo.currentText()

    @property
    def resolution_max_height(self) -> int | None:
        """返回分辨率预设对应的最大高度，自定义或原始时返回 None"""
        return RESOLUTION_PRESETS.get(self.resolution_combo.currentText())

    @property
    def is_custom_resolution(self) -> bool:
        return self.resolution_combo.currentText() == _CUSTOM_RESOLUTION

    @property
    def custom_width(self) -> int:
        return self._custom_width.value()

    @property
    def custom_height(self) -> int:
        return self._custom_height.value()

    @property
    def aspect_ratio(self) -> str:
        return self.ratio_combo.currentText()

    @property
    def quality(self) -> float:
        mapping = {
            "原始 (100%)": 1.0,
            "高 (90%)": 0.9,
            "好 (75%)": 0.75,
            "中 (60%)": 0.6,
        }
        return mapping.get(self.quality_combo.currentText(), 0.9)

    @property
    def gif_fps_value(self) -> int:
        return self.gif_fps.value()

    @property
    def gif_loop_value(self) -> bool:
        return self.gif_loop.isChecked()

    @property
    def export_format(self) -> str:
        return "gif" if self.format_combo.currentText() == "GIF" else "mp4"
