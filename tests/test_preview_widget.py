"""Tests for ui/preview_widget.py — 需要 PyQt5 可用环境"""

import pytest
import numpy as np


def _has_pyqt5():
    """检查 PyQt5 是否可导入"""
    try:
        from PyQt5.QtWidgets import QWidget  # noqa: F401
        return True
    except ImportError:
        return False


class TestPreviewWidgetImport:
    def test_importable(self):
        """验证模块可导入"""
        if not _has_pyqt5():
            pytest.skip("PyQt5 不可用")
        from ui.preview_widget import PreviewWidget
        assert PreviewWidget is not None

    @pytest.mark.skipif(not _has_pyqt5(), reason="PyQt5 不可用")
    def test_creation(self, qapp):
        from ui.preview_widget import PreviewWidget
        w = PreviewWidget()
        assert w is not None

    @pytest.mark.skipif(not _has_pyqt5(), reason="PyQt5 不可用")
    def test_label_initialized(self, qapp):
        from ui.preview_widget import PreviewWidget
        w = PreviewWidget()
        assert hasattr(w, '_label') or hasattr(w, 'label')

    @pytest.mark.skipif(not _has_pyqt5(), reason="PyQt5 不可用")
    def test_resize_rescales_last_frame(self, qapp):
        from PIL import Image
        from ui.preview_widget import PreviewWidget

        w = PreviewWidget()
        w.resize(640, 480)
        w.show()
        qapp.processEvents()
        w.show_frame(Image.new("RGB", (1920, 1080), "red"))
        qapp.processEvents()
        before = w._label.pixmap().width()

        w.resize(1000, 700)
        qapp.processEvents()

        assert w._label.pixmap().width() > before

    @pytest.mark.skipif(not _has_pyqt5(), reason="PyQt5 不可用")
    def test_resize_updates_extra_overlays(self, qapp):
        from PyQt5.QtWidgets import QWidget
        from ui.preview_widget import PreviewWidget

        w = PreviewWidget()
        extra = QWidget(w._label)
        w.add_overlay(extra)
        w.resize(800, 600)
        w.show()
        qapp.processEvents()

        assert extra.size() == w._label.size()


class TestPlaybackController:
    def test_audio_clock_selects_video_frame(self):
        from ui.preview_widget import PlaybackController

        class FakeWidget:
            def start_playback(self, generator):
                self.generator = generator

        class FakeCompositor:
            _frames = list(range(100))
            fps = 10

            def compose_index(self, index):
                self.composed = index
                return index

        class FakeAudioPlayer:
            current_time = 1.2
            finished = False

            def start(self, _seconds=None):
                return True

        widget = FakeWidget()
        compositor = FakeCompositor()
        playback = PlaybackController(
            widget, compositor, audio_player=FakeAudioPlayer()
        )

        playback.play(0)
        next(widget.generator)

        assert compositor.composed == 12
        assert playback.current_frame == 12

    def test_finished_audio_clock_is_closed(self):
        from ui.preview_widget import PlaybackController

        class FakeWidget:
            def start_playback(self, generator):
                self.generator = generator

        class FakeCompositor:
            _frames = list(range(10))
            fps = 10

            def compose_index(self, index):
                return index

        class FakeAudioPlayer:
            current_time = 0.9
            finished = True
            closed = False

            def start(self, _seconds=None):
                return True

            def close(self):
                self.closed = True

        widget = FakeWidget()
        audio = FakeAudioPlayer()
        playback = PlaybackController(
            widget, FakeCompositor(), audio_player=audio
        )

        playback.play(0)
        next(widget.generator)
        with pytest.raises(StopIteration):
            next(widget.generator)

        assert audio.closed is True

    def test_seek_works_before_first_play(self):
        from ui.preview_widget import PlaybackController

        class FakeWidget:
            def show_frame(self, _frame):
                pass

        class FakeCompositor:
            def __init__(self):
                self._frames = list(range(10))
                self.composed = []

            def compose_index(self, index):
                self.composed.append(index)
                return None

        compositor = FakeCompositor()
        playback = PlaybackController(FakeWidget(), compositor)
        playback.seek(7)

        assert playback.total_frames == 10
        assert playback.current_frame == 7
        assert compositor.composed == [7]

    def test_uses_edited_timeline_frame_count(self):
        from ui.preview_widget import PlaybackController

        class FakeWidget:
            def show_frame(self, _frame):
                pass

        class FakeCompositor:
            _frames = list(range(10))
            total_output_frames = 4

            def __init__(self):
                self.composed = []

            def compose_index(self, index):
                self.composed.append(index)
                return None

        compositor = FakeCompositor()
        playback = PlaybackController(FakeWidget(), compositor)
        playback.seek(9)

        assert playback.total_frames == 4
        assert playback.current_frame == 3
        assert compositor.composed == [3]

    def test_replay_after_last_frame_restarts_from_zero(self):
        from ui.preview_widget import PlaybackController

        class FakeWidget:
            def start_playback(self, generator):
                self.generator = generator

            def show_frame(self, _frame):
                pass

        class FakeCompositor:
            _frames = list(range(5))
            total_output_frames = 5

            def compose_index(self, index):
                return index

        widget = FakeWidget()
        playback = PlaybackController(widget, FakeCompositor())
        playback._current_frame = 4
        playback._playing = False

        playback.play(playback.current_frame)

        assert playback.current_frame == 0


class TestAudioPreviewPlayer:
    def test_builds_audio_for_trimmed_and_sped_up_video_clips(self):
        from core.audio_capture import AudioResult
        from core.project import Clip
        from ui.preview_widget import AudioPreviewPlayer

        audio = AudioResult(
            data=np.arange(20, dtype=np.float32).reshape(-1, 1),
            samplerate=10,
            channels=1,
        )
        clips = [Clip(
            type="video", start=0.0, end=0.5,
            source_start=1.0, source_end=2.0, speed=2.0,
        )]

        player = AudioPreviewPlayer(audio, clips, stream_factory=lambda **_: None)

        assert player.timeline_data[:, 0].tolist() == [10, 12, 14, 16, 18]

    def test_output_callback_position_is_the_audio_master_clock(self):
        from core.audio_capture import AudioResult
        from ui.preview_widget import AudioPreviewPlayer

        audio = AudioResult(
            data=np.ones((20, 1), dtype=np.float32),
            samplerate=10,
            channels=1,
        )
        player = AudioPreviewPlayer(audio, [], stream_factory=lambda **_: None)
        output = np.empty((4, 1), dtype=np.float32)

        player.seek(0.5)
        player._audio_callback(output, 4, None, None)

        assert output.tolist() == [[1.0], [1.0], [1.0], [1.0]]
        assert player.current_time == pytest.approx(0.9)

    def test_empty_audio_falls_back_without_opening_output_device(self):
        from core.audio_capture import AudioResult
        from ui.preview_widget import AudioPreviewPlayer

        opened = []
        audio = AudioResult(
            data=np.empty((0, 1), dtype=np.float32),
            samplerate=10,
            channels=1,
        )
        player = AudioPreviewPlayer(
            audio, [], stream_factory=lambda **kwargs: opened.append(kwargs)
        )

        assert player.start() is False
        assert opened == []


class TestZoomOverlay:
    @pytest.mark.skipif(not _has_pyqt5(), reason="PyQt5 不可用")
    def test_dragging_corner_resizes_with_video_aspect(self, qapp):
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from PyQt5.QtWidgets import QLabel
        from ui.preview_widget import ZoomOverlay

        label = QLabel()
        label.resize(1000, 1000)
        overlay = ZoomOverlay(label)
        overlay.resize(label.size())
        overlay.set_rect(100, 50, 400, 400, 1000, 1000)

        press = QPointF(100, 50)
        move = QPointF(200, 150)
        overlay.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, press,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        ))
        overlay.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, move,
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier,
        ))
        overlay.mouseReleaseEvent(QMouseEvent(
            QEvent.MouseButtonRelease, move,
            Qt.LeftButton, Qt.NoButton, Qt.NoModifier,
        ))

        x, y, width, height = overlay._rect
        assert width < 400
        assert height < 400
        assert width / height == pytest.approx(1.0, rel=0.01)
        assert x + width == 500
        assert y + height == 450

    @pytest.mark.skipif(not _has_pyqt5(), reason="PyQt5 不可用")
    def test_dragging_inside_moves_target_region(self, qapp):
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from PyQt5.QtWidgets import QLabel
        from ui.preview_widget import ZoomOverlay

        label = QLabel()
        label.resize(1000, 500)
        overlay = ZoomOverlay(label)
        overlay.resize(label.size())
        overlay.set_rect(100, 100, 400, 200, 1000, 500)

        overlay.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, QPointF(300, 200),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        ))
        overlay.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, QPointF(400, 250),
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier,
        ))
        overlay.mouseReleaseEvent(QMouseEvent(
            QEvent.MouseButtonRelease, QPointF(400, 250),
            Qt.LeftButton, Qt.NoButton, Qt.NoModifier,
        ))

        assert overlay._rect == (200, 150, 400, 200)

    def test_zoom_rect_change_refreshes_current_frame(self):
        from core.project import Clip, Track
        from app.main_window import MainWindow

        clip = Clip(type="zoom", start=0, end=3,
                    rect=[10, 10, 100, 50])

        class FakeCompositor:
            def __init__(self):
                self.loaded = None

            def load_manual_zoom_clips(self, clips):
                self.loaded = clips

        class FakePreview:
            def hide_zoom_rect(self):
                pass

        class FakePlayback:
            current_frame = 12

            def __init__(self):
                self.seeks = []

            def seek(self, frame):
                self.seeks.append(frame)

        class FakeTimeline:
            tracks = [Track(type="zoom", clips=[clip])]

        class FakeWindow:
            _editing_zoom_clip = clip
            _timeline = FakeTimeline()
            _compositor = FakeCompositor()
            _preview = FakePreview()
            _playback = FakePlayback()

        window = FakeWindow()
        MainWindow._on_zoom_rect_changed(window, 20, 15, 80, 40)

        assert clip.rect == [20, 15, 80, 40]
        assert window._compositor.loaded == [clip]
        assert window._playback.seeks == [12]
