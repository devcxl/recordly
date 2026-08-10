"""Tests for ui/preview_widget.py — 需要 PyQt5 可用环境"""

import wave

import pytest
import numpy as np


def _write_wav(path: str, data, samplerate: int):
    """写入 16-bit PCM WAV（等价 core 导出逻辑，纯 wave 模块）"""
    arr = np.asarray(data, dtype=np.float32)
    arr = np.clip(arr, -1.0, 1.0)
    if arr.ndim == 1:
        channels = 1
        arr = arr.reshape(-1, 1)
    else:
        channels = arr.shape[1]
    samples = (arr * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(samples.tobytes())


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
    def test_timeline_data_matches_compose_audio(self, tmp_path):
        """相同 regions 下 timeline_data == compose_audio 输出（逐样本）"""
        from core.audio_mix import compose_audio
        from core.project import AudioRegion
        from ui.preview_widget import AudioPreviewPlayer

        samplerate = 1000
        mic_data = np.array([
            [0.10, -0.20], [0.30, 0.40], [-0.50, 0.60],
            [0.70, -0.80], [0.90, 1.00],
        ], dtype=np.float32)
        sys_data = np.array([
            [0.05, 0.15], [-0.25, 0.35], [0.45, -0.55],
            [0.65, 0.75], [-0.85, 0.95],
        ], dtype=np.float32)
        mic_path = str(tmp_path / "mic.wav")
        sys_path = str(tmp_path / "sys.wav")
        _write_wav(mic_path, mic_data, samplerate)
        _write_wav(sys_path, sys_data, samplerate)

        regions = [
            AudioRegion(start_ms=0.0, end_ms=5.0, source_start_ms=0.0,
                        source_end_ms=5.0, audio_path=mic_path, volume=1.0),
            AudioRegion(start_ms=0.0, end_ms=5.0, source_start_ms=0.0,
                        source_end_ms=5.0, audio_path=sys_path, volume=1.0),
        ]
        player = AudioPreviewPlayer(
            regions, samplerate, stream_factory=lambda **_: None)

        expected = compose_audio(regions, samplerate)
        assert expected is not None
        np.testing.assert_array_equal(player.timeline_data, expected)

    def test_output_callback_position_is_the_audio_master_clock(self, tmp_path):
        from core.project import AudioRegion
        from ui.preview_widget import AudioPreviewPlayer

        path = str(tmp_path / "audio.wav")
        _write_wav(path, np.ones((20, 1), dtype=np.float32), 10)
        regions = [AudioRegion(
            start_ms=0.0, end_ms=2000.0, source_start_ms=0.0,
            source_end_ms=2000.0, audio_path=path, volume=1.0,
        )]
        player = AudioPreviewPlayer(
            regions, 10, stream_factory=lambda **_: None)
        output = np.empty((4, 2), dtype=np.float32)

        player.seek(0.5)
        player._audio_callback(output, 4, None, None)

        # int16 wav 量化后 ≈1.0（32767/32768），用容差断言
        assert np.allclose(output, 1.0, atol=1e-3)
        assert player.current_time == pytest.approx(0.9)

    def test_empty_audio_falls_back_without_opening_output_device(self):
        from ui.preview_widget import AudioPreviewPlayer

        opened = []
        player = AudioPreviewPlayer(
            [], 10, stream_factory=lambda **kwargs: opened.append(kwargs)
        )

        assert player.start() is False
        assert opened == []

    def test_edits_change_timeline_data_like_compose_audio(self, tmp_path):
        """删除/移动/音量编辑后 timeline_data 与 compose_audio 语义一致变化"""
        from core.audio_mix import compose_audio
        from core.project import AudioRegion
        from ui.preview_widget import AudioPreviewPlayer

        samplerate = 1000
        data = np.array([
            [0.10, -0.20], [0.30, 0.40], [-0.50, 0.60],
            [0.70, -0.80], [0.90, 1.00],
        ], dtype=np.float32)
        path = str(tmp_path / "a.wav")
        _write_wav(path, data, samplerate)

        def player_for(regions):
            return AudioPreviewPlayer(
                regions, samplerate, stream_factory=lambda **_: None)

        # 基线：一个 0-5ms 的全量 region
        base = [AudioRegion(
            start_ms=0.0, end_ms=5.0, source_start_ms=0.0,
            source_end_ms=5.0, audio_path=path, volume=1.0,
        )]
        base_player = player_for(base)
        assert base_player.timeline_data is not None
        np.testing.assert_array_equal(
            base_player.timeline_data, compose_audio(base, samplerate))

        # 删除（regions 为空）→ timeline_data 变化（静音）
        deleted_player = player_for([])
        assert deleted_player.timeline_data.size == 0
        assert deleted_player.timeline_data.size != base_player.timeline_data.size

        # 移动（start_ms 2.5 → 样本后移，前段静音）
        moved = [AudioRegion(
            start_ms=2.5, end_ms=7.5, source_start_ms=0.0,
            source_end_ms=5.0, audio_path=path, volume=1.0,
        )]
        moved_player = player_for(moved)
        np.testing.assert_array_equal(
            moved_player.timeline_data, compose_audio(moved, samplerate))
        assert moved_player.timeline_data.shape[0] == 8
        assert moved_player.timeline_data[:2].tolist() == [[0.0, 0.0], [0.0, 0.0]]

        # 音量 0.5 → 样本减半
        quiet = [AudioRegion(
            start_ms=0.0, end_ms=5.0, source_start_ms=0.0,
            source_end_ms=5.0, audio_path=path, volume=0.5,
        )]
        quiet_player = player_for(quiet)
        np.testing.assert_array_equal(
            quiet_player.timeline_data, compose_audio(quiet, samplerate))
        assert quiet_player.timeline_data.shape == base_player.timeline_data.shape
        assert not np.array_equal(quiet_player.timeline_data,
                                  base_player.timeline_data)


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
