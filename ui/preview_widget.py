"""预览组件 — 显示合成后的帧，支持播放控制"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
from PIL import Image

from app.constants import DEFAULT_FPS
from ui.zoom_overlay import ZoomOverlay


class PreviewWidget(QWidget):
    """实时预览组件，显示 Compositor 输出的帧"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("background: #1a1a1a;")
        self._label.setMinimumSize(320, 240)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self.setLayout(layout)

        self._overlay = ZoomOverlay(self._label)
        self._extra_overlays: list = []
        self._last_frame: Image.Image | None = None

        self._timer = QTimer()
        self._timer.setInterval(1000 // DEFAULT_FPS)
        self._timer.timeout.connect(self._tick)
        self._frame_generator = None
        self._fps = DEFAULT_FPS

    def add_overlay(self, overlay):
        """注册额外叠加层，使其随 label resize 自动更新尺寸"""
        self._extra_overlays.append(overlay)
        overlay.resize(self._label.size())

    def show_zoom_rect(self, rect, comp_w=1920, comp_h=1080):
        if rect and self._overlay.isVisible():
            self._overlay.set_rect(*rect, comp_w, comp_h)
        elif rect:
            self._overlay.set_rect(*rect, comp_w, comp_h)

    def hide_zoom_rect(self):
        self._overlay.clear_rect()

    @property
    def overlay(self):
        return self._overlay

    def show_frame(self, pil_image: Image.Image | None):
        if pil_image is None:
            self._last_frame = None
            self._label.setText("无预览")
            return
        self._last_frame = pil_image.copy()
        self._render_last_frame()

    def _render_last_frame(self):
        if self._last_frame is None:
            return
        rgba = self._last_frame.convert("RGBA")
        qimage = QImage(rgba.tobytes(), rgba.width, rgba.height,
                        QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(
            self._label.width(), self._label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self._label.setPixmap(scaled)
        self._resize_overlays()
        if self._overlay.isVisible():
            self._overlay.update()

    def _resize_overlays(self):
        size = self._label.size()
        self._overlay.resize(size)
        for overlay in self._extra_overlays:
            overlay.resize(size)
            if overlay.isVisible():
                overlay.update()

    def start_playback(self, frame_generator):
        self._frame_generator = frame_generator
        self._timer.start()

    def stop_playback(self):
        self._timer.stop()
        self._frame_generator = None

    def set_fps(self, fps: int):
        self._fps = fps
        self._timer.setInterval(1000 // fps)

    def _tick(self):
        if self._frame_generator:
            try:
                frame = next(self._frame_generator)
                self.show_frame(frame)
            except StopIteration:
                self.stop_playback()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_overlays()
        self._render_last_frame()
