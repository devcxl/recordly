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
import numpy as np
import sounddevice as sd
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
        self._resize_edge: str | None = None
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
        p.setBrush(QBrush(QColor("#00ccff")))
        handle = 8
        for hx, hy in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):
            p.drawRect(hx - handle // 2, hy - handle // 2,
                       handle, handle)

    def _hit_test(self, wx, wy):
        """在 widget 坐标中命中具体边/角，保持可操作区域宽度稳定。"""
        if not self._rect:
            return None
        x, y, w, h = self._rect
        left_x, top_y = self._comp_to_widget(x, y)
        right_x, bottom_y = self._comp_to_widget(x + w, y + h)
        margin = self.HANDLE_MARGIN
        left = abs(wx - left_x) <= margin
        right = abs(wx - right_x) <= margin
        top = abs(wy - top_y) <= margin
        bottom = abs(wy - bottom_y) <= margin

        if top and left:
            return "top_left"
        if top and right:
            return "top_right"
        if bottom and left:
            return "bottom_left"
        if bottom and right:
            return "bottom_right"
        if (left_x + margin <= wx <= right_x - margin
                and top_y + margin <= wy <= bottom_y - margin):
            return "move"
        return None

    @staticmethod
    def _cursor_for_hit(hit: str | None):
        if hit in ("top_left", "bottom_right"):
            return Qt.SizeFDiagCursor
        if hit in ("top_right", "bottom_left"):
            return Qt.SizeBDiagCursor
        if hit == "move":
            return Qt.SizeAllCursor
        return Qt.ArrowCursor

    def _resize_from_corner(self, edge: str,
                            pointer: tuple[int, int]) -> tuple[int, int, int, int]:
        x, y, width, height = self._drag_orig
        comp_w, comp_h = self._comp_size
        aspect = comp_w / max(comp_h, 1)

        anchor_x = x + width if "left" in edge else x
        anchor_y = y + height if "top" in edge else y
        width_from_pointer = abs(pointer[0] - anchor_x)
        height_from_pointer = abs(pointer[1] - anchor_y)
        scale_x = width_from_pointer / max(width, 1)
        scale_y = height_from_pointer / max(height, 1)
        scale = (scale_x if abs(scale_x - 1) >= abs(scale_y - 1)
                 else scale_y)

        horizontal_limit = anchor_x if "left" in edge else comp_w - anchor_x
        vertical_limit = anchor_y if "top" in edge else comp_h - anchor_y
        max_width = max(1, min(horizontal_limit, vertical_limit * aspect))
        min_width = min(max_width, max(20, round(20 * aspect)))
        new_width = round(max(min_width, min(width * scale, max_width)))
        new_height = max(1, round(new_width / aspect))

        new_x = anchor_x - new_width if "left" in edge else anchor_x
        new_y = anchor_y - new_height if "top" in edge else anchor_y
        return new_x, new_y, new_width, new_height

    def mousePressEvent(self, event):
        if not self._rect or event.button() != Qt.LeftButton:
            return
        hit = self._hit_test(event.x(), event.y())
        if hit:
            self._dragging = hit == "move"
            self._resize_edge = None if hit == "move" else hit
            self._drag_start = self._widget_to_comp(event.x(), event.y())
            self._drag_orig = self._rect

    def mouseMoveEvent(self, event):
        if not self._rect:
            return
        if not self._dragging and not self._resize_edge:
            self.setCursor(self._cursor_for_hit(
                self._hit_test(event.x(), event.y())))
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
        elif self._resize_edge:
            self._rect = self._resize_from_corner(self._resize_edge, comp)
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


class AudioPreviewPlayer:
    """将编辑后的时间线音频送入声卡，并暴露已消费样本的时间。"""

    def __init__(self, audio_result, video_clips=None, stream_factory=None):
        self.samplerate = int(audio_result.samplerate)
        self.channels = int(audio_result.channels)
        self._stream_factory = stream_factory or sd.OutputStream
        self._timeline_data = self._build_timeline_data(
            audio_result.data, video_clips or []
        )
        self._cursor = 0
        self._stream = None
        self._active = False

    @property
    def timeline_data(self) -> np.ndarray:
        return self._timeline_data

    @property
    def current_time(self) -> float:
        return self._cursor / self.samplerate

    @property
    def duration(self) -> float:
        return len(self._timeline_data) / self.samplerate

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def finished(self) -> bool:
        return self._cursor >= len(self._timeline_data)

    def _normalise_data(self, data) -> np.ndarray:
        array = np.asarray(data, dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(-1, self.channels)
        return array

    def _build_timeline_data(self, data, clips) -> np.ndarray:
        source = self._normalise_data(data)
        if not clips:
            return source.copy()

        clips = sorted(clips, key=lambda clip: clip.start)
        frame_count = max(0, round(max(clip.end for clip in clips) * self.samplerate))
        output = np.zeros((frame_count, source.shape[1]), dtype=np.float32)
        source_axis = np.arange(len(source), dtype=np.float64)

        for clip in clips:
            out_start = max(0, round(clip.start * self.samplerate))
            out_end = min(frame_count, round(clip.end * self.samplerate))
            if out_end <= out_start:
                continue
            source_start = max(0.0, clip.source_start * self.samplerate)
            speed = max(float(clip.speed), 0.01)
            positions = source_start + np.arange(out_end - out_start) * speed
            source_limit = len(source)
            if clip.source_end is not None:
                source_limit = min(source_limit, clip.source_end * self.samplerate)
            valid = positions < source_limit
            if not valid.any() or not len(source):
                continue
            for channel in range(source.shape[1]):
                destination = output[out_start:out_end, channel]
                destination[valid] = np.interp(
                    positions[valid], source_axis, source[:, channel]
                ) * float(clip.volume)
        return output

    def _audio_callback(self, outdata, frames, _time_info, _status):
        end = min(self._cursor + frames, len(self._timeline_data))
        count = max(0, end - self._cursor)
        outdata.fill(0)
        if count:
            outdata[:count] = self._timeline_data[self._cursor:end]
        self._cursor = end

    def start(self, seconds: float | None = None) -> bool:
        if seconds is not None:
            self.seek(seconds)
        self.close()
        if not len(self._timeline_data):
            return False
        try:
            self._stream = self._stream_factory(
                samplerate=self.samplerate,
                channels=self._timeline_data.shape[1],
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            self._active = True
            return True
        except Exception:
            self.close()
            return False

    def pause(self):
        if self._stream is not None:
            self._stream.stop()
        self._active = False

    def resume(self) -> bool:
        return self.start()

    def seek(self, seconds: float):
        self._cursor = max(0, min(
            round(seconds * self.samplerate), len(self._timeline_data)
        ))

    def close(self):
        stream = self._stream
        self._stream = None
        self._active = False
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass


class PlaybackController:
    """预览播放控制器，管理播放状态与帧索引"""

    def __init__(self, widget: PreviewWidget, compositor,
                 audio_result=None, video_clips=None, audio_player=None):
        self.widget = widget
        self.compositor = compositor
        self._playing = False
        self._paused = False
        self._current_frame = 0
        self._total_frames = self._get_total_frames()
        self._step = 1
        self._on_frame_changed = None
        self._audio_player = audio_player
        if self._audio_player is None and audio_result is not None:
            self._audio_player = AudioPreviewPlayer(audio_result, video_clips)
        self._audio_clock = False

    def _get_total_frames(self) -> int:
        return int(getattr(
            self.compositor, "total_output_frames",
            len(self.compositor._frames),
        ))

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def current_frame(self) -> int:
        return self._current_frame

    def set_on_frame_changed(self, callback):
        self._on_frame_changed = callback

    def play(self, start: int = 0):
        self._total_frames = self._get_total_frames()
        if self._total_frames == 0:
            return
        if start >= self._total_frames - 1:
            start = 0
        self._current_frame = start
        self._playing = True
        self._paused = False
        self._step = 1
        self._audio_clock = bool(
            self._audio_player
            and self._audio_player.start(start / self.compositor.fps)
        )
        self._start_generator()

    def _start_generator(self):
        def gen():
            idx = self._current_frame
            while idx < self._total_frames:
                if self._paused:
                    return
                if not self._playing:
                    return
                if self._audio_clock:
                    idx = min(
                        int(self._audio_player.current_time * self.compositor.fps),
                        self._total_frames - 1,
                    )
                frame = self.compositor.compose_index(idx)
                self._current_frame = idx
                if self._on_frame_changed:
                    self._on_frame_changed(idx)
                yield frame
                if self._audio_clock and self._audio_player.finished:
                    self._playing = False
                    self._audio_player.close()
                    self._audio_clock = False
                    return
                if not self._audio_clock:
                    idx += self._step
            self._playing = False
        self.widget.start_playback(gen())

    def pause(self):
        if not self._playing:
            return
        self._paused = not self._paused
        if self._paused:
            self.widget.stop_playback()
            if self._audio_player:
                self._audio_player.pause()
        else:
            if self._audio_player:
                self._audio_clock = self._audio_player.resume()
            self._start_generator()

    @property
    def is_paused(self) -> bool:
        return self._paused

    def stop(self):
        self._playing = False
        self._paused = False
        self._current_frame = 0
        self._step = 1
        self._audio_clock = False
        if self._audio_player:
            self._audio_player.close()
            self._audio_player.seek(0)
        self.widget.stop_playback()
        frame = self.compositor.compose_index(0)
        if frame:
            self.widget.show_frame(frame)
        if self._on_frame_changed:
            self._on_frame_changed(0)

    def seek(self, index: int):
        self._total_frames = self._get_total_frames()
        if self._total_frames == 0:
            self._current_frame = 0
            return
        index = max(0, min(index, self._total_frames - 1))
        self._current_frame = index
        if self._audio_player:
            self._audio_player.seek(index / self.compositor.fps)
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
        if self._audio_clock and self._audio_player:
            self._audio_player.close()
            self._audio_clock = False
        if not self._paused and self._playing:
            self.widget.stop_playback()
            self._start_generator()

    def rewind(self):
        self._step = 1
        self.seek(self._current_frame - 10)

    def reset_speed(self):
        self._step = 1
