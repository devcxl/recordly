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
    class Qt:
        AlignCenter = 4
        KeepAspectRatio = 128
        SmoothTransformation = 256
        WA_TransparentForMouseEvents = 256
        LeftButton = 1
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
    """预览区域上的缩放框叠加层（坐标 = 合成器分辨率）"""

    rect_changed = pyqtSignal(int, int, int, int)

    HANDLE_MARGIN = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rect = None
        self._comp_size = (1920, 1080)
        self._dragging = False
        self._resizing = False
        self._drag_start = (0, 0)
        self._drag_orig = (0, 0, 0, 0)
        self.hide()

    def set_rect(self, x, y, w, h, comp_w=1920, comp_h=1080):
        self._rect = (x, y, w, h)
        self._comp_size = (comp_w, comp_h)
        self.show()
        self.update()

    def clear_rect(self):
        self._rect = None
        self.hide()

    def _label_rect(self):
        """返回 label 内 pixmap 的显示矩形（像素坐标）"""
        p = self.parent().pixmap() if self.parent() else None
        if not p or p.isNull():
            return (0, 0, self.width(), self.height())
        pw, ph = p.width(), p.height()
        lw, lh = self.width(), self.height()
        ox = max(0, (lw - pw) // 2)
        oy = max(0, (lh - ph) // 2)
        return (ox, oy, pw, ph)

    def _comp_to_widget(self, cx, cy):
        """合成坐标 → widget 坐标"""
        ox, oy, dw, dh = self._label_rect()
        cw, ch = self._comp_size
        if cw <= 0 or ch <= 0:
            return (cx, cy)
        return (int(ox + cx * dw / cw), int(oy + cy * dh / ch))

    def _widget_to_comp(self, wx, wy):
        """widget 坐标 → 合成坐标"""
        ox, oy, dw, dh = self._label_rect()
        cw, ch = self._comp_size
        if dw <= 0 or dh <= 0:
            return (wx, wy)
        return (int((wx - ox) * cw / dw), int((wy - oy) * ch / dh))

    def paintEvent(self, event):
        if not self._rect:
            return
        p = QPainter(self)
        x1, y1 = self._comp_to_widget(self._rect[0], self._rect[1])
        x2, y2 = self._comp_to_widget(self._rect[0] + self._rect[2],
                                       self._rect[1] + self._rect[3])
        p.setPen(QPen(QColor("#00ccff"), 2))
        p.setBrush(QBrush(QColor(0, 204, 255, 30)))
        p.drawRect(x1, y1, x2 - x1, y2 - y1)
        p.setPen(QColor("#00ccff"))
        p.drawText(x1 + 4, y1 + 14, "缩放区域")

    def _hit_test(self, wx, wy):
        """检测点击位置：返回 'move', 'resize', 或 None"""
        if not self._rect:
            return None
        cx, cy = self._widget_to_comp(wx, wy)
        x, y, w, h = self._rect
        left = abs(cx - x) < self.HANDLE_MARGIN
        right = abs(cx - (x + w)) < self.HANDLE_MARGIN
        top = abs(cy - y) < self.HANDLE_MARGIN
        bottom = abs(cy - (y + h)) < self.HANDLE_MARGIN
        if left or right or top or bottom:
            return "resize"
        if x <= cx <= x + w and y <= cy <= y + h:
            return "move"
        return None

    def mousePressEvent(self, event):
        if not self._rect or event.button() != Qt.LeftButton:
            return
        hit = self._hit_test(event.x(), event.y())
        if hit:
            self._dragging = hit == "move"
            self._resizing = hit == "resize"
            self._drag_start = self._widget_to_comp(event.x(), event.y())
            self._drag_orig = self._rect

    def mouseMoveEvent(self, event):
        if not self._rect:
            return
        cw, ch = self._comp_size
        comp = self._widget_to_comp(event.x(), event.y())
        dx = comp[0] - self._drag_start[0]
        dy = comp[1] - self._drag_start[1]
        x, y, w, h = self._drag_orig

        if self._dragging:
            new_x = max(0, min(x + dx, cw - w))
            new_y = max(0, min(y + dy, ch - h))
            self._rect = (new_x, new_y, w, h)
            self.update()
        elif self._resizing:
            new_x, new_y, new_w, new_h = x, y, w, h
            if dx < 0:
                new_x = max(0, x + dx)
                new_w = x + w - new_x
            else:
                new_w = min(cw - new_x, max(20, w + dx))
            if dy < 0:
                new_y = max(0, y + dy)
                new_h = y + h - new_y
            else:
                new_h = min(ch - new_y, max(20, h + dy))
            self._rect = (new_x, new_y, new_w, new_h)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._dragging or self._resizing:
            self._dragging = False
            self._resizing = False
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

        self._timer = QTimer()
        self._timer.setInterval(1000 // DEFAULT_FPS)
        self._timer.timeout.connect(self._tick)
        self._frame_generator = None
        self._fps = DEFAULT_FPS

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
        if self._overlay.isVisible():
            self._overlay.update()

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
