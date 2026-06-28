"""预览组件 — 显示合成后的帧，支持播放控制"""

try:
    from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSlider, QHBoxLayout
    from PyQt5.QtCore import Qt, QTimer, QRectF, pyqtSignal
    from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QBrush
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
    class QPainter: pass
    class QRectF: pass
    class QColor: pass
    class QPen: pass
    class QBrush: pass
    pyqtSignal = None

from PIL import Image
from app.constants import DEFAULT_FPS


class ZoomOverlay(QWidget):
    """预览区域上的缩放框叠加层"""

    rect_changed = pyqtSignal(int, int, int, int)  # x, y, w, h

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rect = None
        self._dragging = False
        self._drag_start = (0, 0)
        self._drag_orig = (0, 0, 0, 0)
        self._resize_edge = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self.hide()

    def set_rect(self, x, y, w, h):
        self._rect = (x, y, w, h)
        self.update()

    def clear_rect(self):
        self._rect = None
        self.hide()

    def paintEvent(self, event):
        if not self._rect:
            return
        p = QPainter(self)
        x, y, w, h = self._rect
        ow, oh = self.width(), self.height()
        # 缩放框坐标按 widget 尺寸映射
        p.setPen(QPen(QColor("#00ccff"), 2))
        p.setBrush(QBrush(QColor(0, 204, 255, 30)))
        p.drawRect(int(x), int(y), int(w), int(h))
        p.setPen(QColor("#00ccff"))
        p.drawText(int(x) + 4, int(y) + 14, "缩放区域")

    def mousePressEvent(self, event):
        if not self._rect or event.button() != Qt.LeftButton:
            return
        x, y, w, h = self._rect
        margin = 8
        edges = []
        if abs(event.x() - x) < margin:
            edges.append("left")
        if abs(event.x() - (x + w)) < margin:
            edges.append("right")
        if abs(event.y() - y) < margin:
            edges.append("top")
        if abs(event.y() - (y + h)) < margin:
            edges.append("bottom")

        if edges:
            self._resize_edge = edges
            self._drag_start = (event.x(), event.y())
            self._drag_orig = self._rect
        elif x <= event.x() <= x + w and y <= event.y() <= y + h:
            self._dragging = True
            self._drag_start = (event.x(), event.y())
            self._drag_orig = self._rect

    def mouseMoveEvent(self, event):
        if self._dragging and self._rect:
            dx = event.x() - self._drag_start[0]
            dy = event.y() - self._drag_start[1]
            x, y, w, h = self._drag_orig
            self._rect = (x + dx, y + dy, w, h)
            self.update()
        elif self._resize_edge and self._rect:
            dx = event.x() - self._drag_start[0]
            dy = event.y() - self._drag_start[1]
            x, y, w, h = self._drag_orig
            edges = self._resize_edge
            if "left" in edges:
                x += dx
                w -= dx
            if "right" in edges:
                w += dx
            if "top" in edges:
                y += dy
                h -= dy
            if "bottom" in edges:
                h += dy
            self._rect = (max(0, x), max(0, y), max(20, w), max(20, h))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._dragging or self._resize_edge:
            self._dragging = False
            self._resize_edge = None
            if self._rect:
                self.rect_changed.emit(*self._rect)


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
        self._overlay.hide()

        self._timer = QTimer()
        self._timer.setInterval(1000 // DEFAULT_FPS)
        self._timer.timeout.connect(self._tick)
        self._frame_generator = None
        self._fps = DEFAULT_FPS

    def show_zoom_rect(self, rect):
        if rect:
            ow, oh = self._overlay.width(), self._overlay.height()
            scale_x = ow / max(self._label.width(), 1)
            scale_y = oh / max(self._label.height(), 1)
            scaled = (int(rect[0] * scale_x), int(rect[1] * scale_y),
                      int(rect[2] * scale_x), int(rect[3] * scale_y))
            self._overlay.set_rect(*scaled)
            self._overlay.show()
        else:
            self._overlay.clear_rect()

    @property
    def overlay(self):
        return self._overlay

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
        self._overlay.resize(self._label.width(), self._label.height())

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
        self._overlay.resize(self._label.width(), self._label.height())


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
