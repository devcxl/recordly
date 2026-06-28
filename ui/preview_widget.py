"""预览组件 — 显示合成后的帧，支持播放控制"""

try:
    from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSlider, QHBoxLayout
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QPixmap, QImage
    _HAS_QT = True
except ImportError:
    _HAS_QT = False
    class QWidget: pass
    class QLabel: pass
    class QVBoxLayout: pass
    class QSlider: pass
    class QHBoxLayout: pass
    class Qt: AlignCenter = 4
    class QTimer: pass
    class QPixmap: pass
    class QImage: pass

from PIL import Image
from app.constants import DEFAULT_FPS


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

        self._timer = QTimer()
        self._timer.setInterval(1000 // DEFAULT_FPS)
        self._timer.timeout.connect(self._tick)
        self._frame_generator = None
        self._fps = DEFAULT_FPS

    def show_frame(self, pil_image: Image.Image | None):
        if pil_image is None:
            self._label.setText("无预览")
            return
        rgba = pil_image.convert("RGBA")
        qimage = QImage(rgba.tobytes(), rgba.width, rgba.height,
                        QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(
            self._label.width(), self._label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self._label.setPixmap(scaled)

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


class PlaybackController:
    """预览播放控制器，管理播放状态与帧索引"""

    def __init__(self, widget: PreviewWidget, compositor):
        self.widget = widget
        self.compositor = compositor
        self._playing = False
        self._paused = False
        self._current_frame = 0
        self._total_frames = 0
        self._step = 1
        self._on_frame_changed = None

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def current_frame(self) -> int:
        return self._current_frame

    def set_on_frame_changed(self, callback):
        self._on_frame_changed = callback

    def play(self, start: int = 0):
        self._total_frames = len(self.compositor._frames)
        self._current_frame = start
        self._playing = True
        self._paused = False
        self._step = 1
        self._start_generator()

    def _start_generator(self):
        def gen():
            idx = self._current_frame
            while idx < self._total_frames:
                if self._paused:
                    return
                if not self._playing:
                    return
                frame = self.compositor.compose_index(idx)
                self._current_frame = idx
                if self._on_frame_changed:
                    self._on_frame_changed(idx)
                idx += self._step
                yield frame
            self._playing = False
        self.widget.start_playback(gen())

    def pause(self):
        if not self._playing:
            return
        self._paused = not self._paused
        if self._paused:
            self.widget.stop_playback()
        else:
            self._start_generator()

    @property
    def is_paused(self) -> bool:
        return self._paused

    def stop(self):
        self._playing = False
        self._paused = False
        self._current_frame = 0
        self._step = 1
        self.widget.stop_playback()
        frame = self.compositor.compose_index(0)
        if frame:
            self.widget.show_frame(frame)
        if self._on_frame_changed:
            self._on_frame_changed(0)

    def seek(self, index: int):
        index = max(0, min(index, self._total_frames - 1))
        self._current_frame = index
        frame = self.compositor.compose_index(index)
        if frame:
            self.widget.show_frame(frame)
        if self._on_frame_changed:
            self._on_frame_changed(index)

    def step_forward(self):
        self.seek(self._current_frame + 1)

    def step_backward(self):
        self.seek(self._current_frame - 1)

    def fast_forward(self):
        self._step = min(self._step * 2, 16)
        if not self._paused and self._playing:
            self.widget.stop_playback()
            self._start_generator()

    def rewind(self):
        self._step = 1
        self.seek(self._current_frame - 10)

    def reset_speed(self):
        self._step = 1
