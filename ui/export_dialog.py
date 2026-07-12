"""导出设置对话框 — 格式/宽高比/质量/帧率"""

import os

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QLabel, QPushButton, QFileDialog, QSpinBox, QCheckBox,
)

from core.aspect_ratio import ASPECT_RATIO_PRESETS


class ExportDialog(QDialog):
    """增强导出对话框，支持格式、宽高比预设、质量、GIF 帧率和循环设置"""

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

        # 格式切换时显示/隐藏 GIF 选项
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        self._on_format_changed("MP4")

    def _on_format_changed(self, fmt: str):
        is_gif = fmt == "GIF"
        self.gif_fps.setVisible(is_gif)
        self.gif_loop.setVisible(is_gif)
        self.quality_combo.setVisible(not is_gif)

    def _browse(self):
        fmt = self.format_combo.currentText()
        ext = "GIF (*.gif)" if fmt == "GIF" else "MP4 (*.mp4)"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存为", self._default_dir, ext)
        if path:
            self._output_path = path
            self.browse_btn.setText(os.path.basename(path))

    @property
    def output_path(self) -> str:
        return self._output_path

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
