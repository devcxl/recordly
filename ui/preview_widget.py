"""预览组件 — 显示合成后的帧"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QPixmap
    _HAS_QT = True
except ImportError:
    _HAS_QT = False
    # 降级：无 PyQt5 时用普通 object
    class QWidget:
        pass
    class QLabel:
        pass
    class QVBoxLayout:
        pass
    class Qt:
        AlignCenter = 4
    class QTimer:
        pass
    class QPixmap:
        pass

from PIL import Image
from PIL.ImageQt import toqpixmap
from app.constants import DEFAULT_FPS


class PreviewWidget(QWidget):
    """实时预览组件，渲染 Compositor 输出的 Pillow Image"""

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

        self._timer = QTimer()
        self._timer.setInterval(1000 // DEFAULT_FPS)
        self._timer.timeout.connect(self._tick)
        self._frame_generator = None
        self._fps = DEFAULT_FPS

    def show_frame(self, pil_image: Image.Image | None):
        """设置当前显示帧"""
        if pil_image is None:
            self._label.setText("无预览")
            return
        # PIL → QPixmap
        qimage = ImageQt(pil_image.convert("RGBA"))
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(
            self._label.width(), self._label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self._label.setPixmap(scaled)

    def start_playback(self, frame_generator):
        """开始播放帧序列"""
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
        # 窗口缩放时重绘当前帧


class PreviewController:
    """预览控制器，连接 Compositor → PreviewWidget"""

    def __init__(self, widget: PreviewWidget, compositor):
        self.widget = widget
        self.compositor = compositor
        self._playing = False

    def play(self, start: int = 0, end: int = None):
        """以默认帧率播放"""
        self._playing = True
        gen = self.compositor.render_all(start=start, end=end)
        self.widget.start_playback(gen)

    def stop(self):
        self._playing = False
        self.widget.stop_playback()

    def show_frame_at(self, index: int):
        """跳转到指定帧"""
        frame = self.compositor.compose_index(index)
        self.widget.show_frame(frame)
