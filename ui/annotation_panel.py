"""标注设置面板 — 文本/图片/箭头/模糊"""

import base64
import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QSpinBox, QCheckBox, QPushButton,
    QComboBox, QSlider, QLabel, QButtonGroup,
    QGridLayout, QFileDialog, QColorDialog, QDoubleSpinBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

from core.project import AnnotationRegion, FigureData


class AnnotationSettingsPanel(QWidget):
    """标注设置面板 — 支持 4 种标注类型的参数配置"""

    annotation_created = pyqtSignal(object)  # AnnotationRegion

    def __init__(self, parent=None, duration=60.0, current_time=0.0):
        super().__init__(parent)
        self._duration = duration
        self._current_time = current_time
        self._image_data_url = ""
        self._selected_direction = "right"
        self._text_color = "#ffffff"
        self._figure_color = "#ff0000"
        self._blur_color = "#000000"
        self._setup_ui()

    # ── UI 构建 ──────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_text_tab(), "文本")
        self._tabs.addTab(self._build_image_tab(), "图片")
        self._tabs.addTab(self._build_figure_tab(), "箭头")
        self._tabs.addTab(self._build_blur_tab(), "模糊")
        layout.addWidget(self._tabs)

        # 统一时间范围控件
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("起始时间:"))
        self._start_time = QDoubleSpinBox()
        self._start_time.setRange(0, 99999)
        self._start_time.setValue(self._current_time)
        self._start_time.setSuffix(" 秒")
        time_layout.addWidget(self._start_time)
        time_layout.addWidget(QLabel("结束时间:"))
        self._end_time = QDoubleSpinBox()
        self._end_time.setRange(0, 99999)
        self._end_time.setValue(self._duration)
        self._end_time.setSuffix(" 秒")
        time_layout.addWidget(self._end_time)
        time_layout.addStretch()
        layout.addLayout(time_layout)

        self._btn_add = QPushButton("添加标注")
        self._btn_add.clicked.connect(self._on_add)
        layout.addWidget(self._btn_add)

    def _build_text_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        layout.addWidget(QLabel("标注文本:"))
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("输入标注文本...")
        self._text_edit.setMaximumHeight(100)
        layout.addWidget(self._text_edit)

        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("字体:"))
        self._font_combo = QComboBox()
        self._font_combo.addItems([
            "sans-serif", "serif", "monospace",
            "Arial", "Helvetica", "Times New Roman", "Courier New",
        ])
        self._font_combo.setEditable(True)
        font_layout.addWidget(self._font_combo)
        font_layout.addWidget(QLabel("字号:"))
        self._font_size = QSpinBox()
        self._font_size.setRange(8, 200)
        self._font_size.setValue(24)
        font_layout.addWidget(self._font_size)
        layout.addLayout(font_layout)

        style_layout = QHBoxLayout()
        self._btn_text_color = QPushButton()
        self._btn_text_color.setFixedSize(32, 32)
        self._btn_text_color.setStyleSheet(
            f"background-color: {self._text_color}; border: 1px solid #555;")
        self._btn_text_color.clicked.connect(lambda: self._pick_color("text"))
        style_layout.addWidget(QLabel("颜色:"))
        style_layout.addWidget(self._btn_text_color)

        self._chk_bold = QCheckBox("粗体")
        self._chk_italic = QCheckBox("斜体")
        self._chk_underline = QCheckBox("下划线")
        style_layout.addWidget(self._chk_bold)
        style_layout.addWidget(self._chk_italic)
        style_layout.addWidget(self._chk_underline)
        style_layout.addStretch()
        layout.addLayout(style_layout)

        layout.addStretch()
        return tab

    def _build_image_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        self._btn_select_image = QPushButton("选择图片...")
        self._btn_select_image.clicked.connect(self._on_select_image)
        layout.addWidget(self._btn_select_image)

        self._image_preview = QLabel("未选择图片")
        self._image_preview.setFixedSize(160, 120)
        self._image_preview.setAlignment(Qt.AlignCenter)
        self._image_preview.setStyleSheet(
            "background: #333; border: 1px solid #555; color: #888;")
        layout.addWidget(self._image_preview)

        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("宽度 (%):"))
        self._image_width = QSpinBox()
        self._image_width.setRange(1, 200)
        self._image_width.setValue(30)
        self._image_width.setSuffix("%")
        size_layout.addWidget(self._image_width)
        size_layout.addWidget(QLabel("高度 (%):"))
        self._image_height = QSpinBox()
        self._image_height.setRange(1, 200)
        self._image_height.setValue(10)
        self._image_height.setSuffix("%")
        size_layout.addWidget(self._image_height)
        size_layout.addStretch()
        layout.addLayout(size_layout)

        layout.addStretch()
        return tab

    def _build_figure_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        layout.addWidget(QLabel("箭头方向:"))

        grid = QGridLayout()
        grid.setSpacing(4)
        self._dir_group = QButtonGroup(self)
        self._dir_buttons: dict[str, QPushButton] = {}

        buttons_data = [
            ("↖", "up-left", 0, 0), ("↑", "up", 0, 1), ("↗", "up-right", 0, 2),
            ("←", "left", 1, 0),     ("", "", 1, 1),    ("→", "right", 1, 2),
            ("↙", "down-left", 2, 0), ("↓", "down", 2, 1), ("↘", "down-right", 2, 2),
        ]
        for symbol, dir_name, row, col in buttons_data:
            if not dir_name:
                continue
            btn = QPushButton(symbol)
            btn.setFixedSize(48, 48)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { font-size: 20px; border: 1px solid #555;
                              border-radius: 4px; }
                QPushButton:checked { background: #0078D4; color: white; }
            """)
            self._dir_group.addButton(btn)
            self._dir_buttons[dir_name] = btn
            grid.addWidget(btn, row, col)
            if dir_name == "right":
                btn.setChecked(True)

        layout.addLayout(grid)
        self._dir_group.buttonClicked.connect(self._on_direction_clicked)

        style_layout = QHBoxLayout()
        self._btn_figure_color = QPushButton()
        self._btn_figure_color.setFixedSize(32, 32)
        self._btn_figure_color.setStyleSheet(
            f"background-color: {self._figure_color}; border: 1px solid #555;")
        self._btn_figure_color.clicked.connect(lambda: self._pick_color("figure"))
        style_layout.addWidget(QLabel("颜色:"))
        style_layout.addWidget(self._btn_figure_color)

        style_layout.addWidget(QLabel("线宽:"))
        self._stroke_width = QSpinBox()
        self._stroke_width.setRange(1, 20)
        self._stroke_width.setValue(3)
        style_layout.addWidget(self._stroke_width)
        style_layout.addStretch()
        layout.addLayout(style_layout)

        layout.addStretch()
        return tab

    def _build_blur_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        layout.addWidget(QLabel("模糊强度:"))

        intensity_layout = QHBoxLayout()
        self._blur_slider = QSlider(Qt.Horizontal)
        self._blur_slider.setRange(1, 100)
        self._blur_slider.setValue(50)
        intensity_layout.addWidget(self._blur_slider)
        self._blur_label = QLabel("50")
        self._blur_slider.valueChanged.connect(
            lambda v: self._blur_label.setText(str(v)))
        intensity_layout.addWidget(self._blur_label)
        layout.addLayout(intensity_layout)

        color_layout = QHBoxLayout()
        self._btn_blur_color = QPushButton()
        self._btn_blur_color.setFixedSize(32, 32)
        self._btn_blur_color.setStyleSheet(
            f"background-color: {self._blur_color}; border: 1px solid #555;")
        self._btn_blur_color.clicked.connect(lambda: self._pick_color("blur"))
        color_layout.addWidget(QLabel("覆盖颜色:"))
        color_layout.addWidget(self._btn_blur_color)
        color_layout.addStretch()
        layout.addLayout(color_layout)

        layout.addStretch()
        return tab

    # ── 交互 ─────────────────────────────────────────────

    def _pick_color(self, target: str):
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        hex_color = color.name()
        if target == "text":
            self._text_color = hex_color
            self._btn_text_color.setStyleSheet(
                f"background-color: {hex_color}; border: 1px solid #555;")
        elif target == "figure":
            self._figure_color = hex_color
            self._btn_figure_color.setStyleSheet(
                f"background-color: {hex_color}; border: 1px solid #555;")
        elif target == "blur":
            self._blur_color = hex_color
            self._btn_blur_color.setStyleSheet(
                f"background-color: {hex_color}; border: 1px solid #555;")

    def _on_direction_clicked(self, _btn):
        for name, btn in self._dir_buttons.items():
            if btn.isChecked():
                self._selected_direction = name
                break

    def _on_select_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp)")
        if not path:
            return
        with open(path, "rb") as f:
            raw = f.read()
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime_map = {"png": "image/png", "jpg": "image/jpeg",
                    "jpeg": "image/jpeg", "gif": "image/gif", "bmp": "image/bmp"}
        mime = mime_map.get(ext, "image/png")
        b64 = base64.b64encode(raw).decode("ascii")
        self._image_data_url = f"data:{mime};base64,{b64}"

        pixmap = QPixmap(path)
        self._image_preview.setPixmap(
            pixmap.scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_add(self):
        tab_idx = self._tabs.currentIndex()
        type_map = {0: "text", 1: "image", 2: "figure", 3: "blur"}
        ann_type = type_map[tab_idx]

        region = AnnotationRegion(
            type=ann_type,
            start_ms=self._start_time.value() * 1000,
            end_ms=self._end_time.value() * 1000,
            x=50.0,
            y=50.0,
            width=30.0,
            height=10.0,
            color=self._text_color,
        )

        if ann_type == "text":
            region.content = self._text_edit.toPlainText()
            region.font_size = self._font_size.value()
            region.color = self._text_color
            region.font_family = self._font_combo.currentText()
            region.bold = self._chk_bold.isChecked()
            region.italic = self._chk_italic.isChecked()
            region.underline = self._chk_underline.isChecked()
        elif ann_type == "image":
            region.content = self._image_data_url
            region.width = float(self._image_width.value())
            region.height = float(self._image_height.value())
        elif ann_type == "figure":
            region.figure_data = FigureData(
                arrow_direction=self._selected_direction,
                color=self._figure_color,
                stroke_width=self._stroke_width.value(),
            )
            region.color = self._figure_color
        elif ann_type == "blur":
            region.blur_intensity = self._blur_slider.value()
            region.blur_color = self._blur_color

        self.annotation_created.emit(region)
