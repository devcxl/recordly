"""Clip 属性检查器面板 — 选中 audio clip 时显示音量滑块控制。

集成点：
- 监听 timeline 的 clip_volume_changed 信号实时更新数值标签
- 自身 slider valueChanged 修改 clip.volume 并触发 timeline 重绘
- 用户调整完成后由调用方处理 preview 重渲染
"""

try:
    from PyQt5.QtWidgets import (
        QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSlider, QPushButton,
        QSizePolicy,
    )
    from PyQt5.QtCore import Qt, pyqtSignal
    _HAS_QT = True
except ImportError:
    _HAS_QT = False
    class QWidget: pass
    class QHBoxLayout: pass
    class QVBoxLayout: pass
    class QLabel: pass
    class QSlider:
        Horizontal = 1
    class QPushButton: pass
    class QSizePolicy:
        Expanding = 7
        Preferred = 5
    class Qt:
        AlignCenter = 4
        Horizontal = 1
    pyqtSignal = None


class InspectorPanel(QWidget):
    """底部属性面板：选中 audio clip 时显示音量控制。

    信号：
    volume_changing(ti, ci, new_volume)        — 拖动中（实时）
    volume_committed(ti, ci, old, new)         — 拖动结束
    """

    if _HAS_QT:
        volume_changing = pyqtSignal(int, int, float)
        volume_committed = pyqtSignal(int, int, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inspectorPanel")
        self._track_idx = -1
        self._clip_idx = -1
        self._old_volume = 1.0
        self._dragging = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 6, 12, 6)
        outer.setSpacing(12)

        # 标题
        self._title_label = QLabel("未选中 clip")
        self._title_label.setObjectName("inspectorTitle")
        self._title_label.setMinimumWidth(160)
        outer.addWidget(self._title_label)

        # 静音按钮
        self._mute_btn = QPushButton("静音")
        self._mute_btn.setObjectName("muteButton")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setFixedWidth(64)
        self._mute_btn.toggled.connect(self._on_mute_toggled)
        outer.addWidget(self._mute_btn)

        # 音量标签
        vol_label = QLabel("音量:")
        outer.addWidget(vol_label)

        # slider
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setObjectName("volumeSlider")
        self._slider.setMinimum(0)
        self._slider.setMaximum(200)  # 0-200 (%)
        self._slider.setValue(100)
        self._slider.setMinimumWidth(200)
        self._slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._slider.setEnabled(False)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._slider.valueChanged.connect(self._on_slider_value_changed)
        outer.addWidget(self._slider, 1)

        # 百分比数值
        self._value_label = QLabel("100%")
        self._value_label.setObjectName("volumeValueLabel")
        self._value_label.setMinimumWidth(60)
        self._value_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._value_label)

        self.setVisible(False)
        self.setFixedHeight(56)

    # ── 公共 API ─────────────────────────────────────────

    def show_clip(self, track_idx: int, clip_idx: int, clip):
        """显示选中 clip 的属性；clip=None 表示隐藏面板。"""
        if clip is None:
            self.clear()
            return
        self._track_idx = track_idx
        self._clip_idx = clip_idx
        volume = max(0.0, min(getattr(clip, "volume", 1.0), 2.0))
        self._old_volume = volume
        clip_name = clip.type
        if getattr(clip, "content", ""):
            base = clip.content if len(clip.content) <= 24 else clip.content[:22] + "..."
            clip_name = f"{clip.type} — {base}"
        self._title_label.setText(f"▸ {clip_name}")
        # 阻止 valueChanged 触发循环更新
        self._slider.blockSignals(True)
        self._slider.setValue(int(round(volume * 100)))
        self._slider.setEnabled(True)
        self._slider.blockSignals(False)
        self._update_value_label(volume)
        self._mute_btn.blockSignals(True)
        self._mute_btn.setChecked(volume <= 0.0)
        self._mute_btn.setEnabled(True)
        self._mute_btn.blockSignals(False)
        self.setVisible(True)

    def clear(self):
        """清空面板（无选中 clip）。"""
        self._track_idx = -1
        self._clip_idx = -1
        self._title_label.setText("未选中 clip")
        self._slider.blockSignals(True)
        self._slider.setValue(100)
        self._slider.setEnabled(False)
        self._slider.blockSignals(False)
        self._mute_btn.blockSignals(True)
        self._mute_btn.setChecked(False)
        self._mute_btn.setEnabled(False)
        self._mute_btn.blockSignals(False)
        self._value_label.setText("—")
        self.setVisible(False)

    def update_volume_display(self, track_idx: int, clip_idx: int,
                              volume: float):
        """外部（timeline mini slider 拖动）触发的同步显示，不发射信号。
        仅当面板当前显示的就是目标 clip 时才更新，避免拖动别的 clip 时误刷新。
        """
        if (self._track_idx != track_idx or self._clip_idx != clip_idx
                or self._track_idx < 0):
            return
        volume = max(0.0, min(volume, 2.0))
        self._slider.blockSignals(True)
        self._slider.setValue(int(round(volume * 100)))
        self._slider.blockSignals(False)
        self._update_value_label(volume)
        self._mute_btn.blockSignals(True)
        self._mute_btn.setChecked(volume <= 0.0)
        self._mute_btn.blockSignals(False)

    # ── 槽 ─────────────────────────────────────────────

    def _on_slider_pressed(self):
        if self._track_idx < 0:
            return
        self._dragging = True
        self._old_volume = self._slider.value() / 100.0

    def _on_slider_value_changed(self, value: int):
        if self._track_idx < 0:
            return
        volume = value / 100.0
        self._update_value_label(volume)
        self._mute_btn.blockSignals(True)
        self._mute_btn.setChecked(volume <= 0.0)
        self._mute_btn.blockSignals(False)
        self.volume_changing.emit(self._track_idx, self._clip_idx, volume)

    def _on_slider_released(self):
        if self._track_idx < 0 or not self._dragging:
            self._dragging = False
            return
        new_volume = self._slider.value() / 100.0
        old_volume = self._old_volume
        self._dragging = False
        if abs(old_volume - new_volume) > 0.001:
            self.volume_committed.emit(
                self._track_idx, self._clip_idx, old_volume, new_volume)

    def _on_mute_toggled(self, checked: bool):
        if self._track_idx < 0:
            return
        new_volume = 0.0 if checked else 1.0
        self._slider.blockSignals(True)
        self._slider.setValue(int(round(new_volume * 100)))
        self._slider.blockSignals(False)
        self._update_value_label(new_volume)
        self.volume_changing.emit(self._track_idx, self._clip_idx, new_volume)
        # 静音切换立即 commit（不需要 drag 释放事件）
        old_volume = self._old_volume
        if abs(old_volume - new_volume) > 0.001:
            self._old_volume = new_volume
            self.volume_committed.emit(
                self._track_idx, self._clip_idx, old_volume, new_volume)

    def _update_value_label(self, volume: float):
        if volume <= 0.001:
            self._value_label.setText("静音")
        else:
            self._value_label.setText(f"{int(round(volume * 100))}%")