"""Tests for ui/timeline.py — 命令层无 Qt 依赖，渲染层需 Qt"""

import pytest


class TestTimelineCommands:
    """Command 模式数据层测试（不创建 QWidget）"""

    @pytest.fixture
    def mock_timeline(self):
        from unittest.mock import MagicMock
        from core.project import Track, Clip
        tl = MagicMock()
        tl._tracks = [
            Track(type="video", clips=[
                Clip(type="video", content="clip1", start=0.0, end=5.0),
            ]),
            Track(type="audio", clips=[
                Clip(type="audio", content="clip2", start=2.0, end=7.0),
            ]),
        ]
        return tl

    def test_move_clip_command(self, mock_timeline):
        from core.commands import MoveClipCommand
        cmd = MoveClipCommand(
            track_index=0, clip_index=0,
            old_start=0.0, new_start=1.0,
            old_end=5.0, new_end=6.0,
        )
        cmd.execute(mock_timeline)
        assert mock_timeline._tracks[0].clips[0].start == 1.0
        cmd.undo(mock_timeline)
        assert mock_timeline._tracks[0].clips[0].start == 0.0

    def test_move_clip_unchanged(self, mock_timeline):
        from core.commands import MoveClipCommand
        cmd = MoveClipCommand(0, 0, 0.0, 0.0, 5.0, 5.0)
        cmd.execute(mock_timeline)

    def test_delete_clip_command(self, mock_timeline):
        from core.commands import DeleteClipCommand
        cmd = DeleteClipCommand(track_index=0, clip_index=0)
        cmd.execute(mock_timeline)
        assert len(mock_timeline._tracks[0].clips) == 0
        cmd.undo(mock_timeline)
        assert len(mock_timeline._tracks[0].clips) == 1

    def test_split_clip_command(self, mock_timeline):
        from core.commands import SplitClipCommand
        cmd = SplitClipCommand(track_index=0, clip_index=0, split_time=2.5)
        cmd.execute(mock_timeline)
        assert mock_timeline._tracks[0].clips[0].end == pytest.approx(2.5)
        assert len(mock_timeline._tracks[0].clips) == 2
        cmd.undo(mock_timeline)
        assert len(mock_timeline._tracks[0].clips) == 1

    def test_split_preserves_source_ranges(self, mock_timeline):
        from core.commands import SplitClipCommand

        clip = mock_timeline._tracks[0].clips[0]
        clip.id = "left"
        clip.source_start = 10.0
        clip.source_end = 20.0
        clip.speed = 2.0
        clip.start = 0.0
        clip.end = 5.0

        cmd = SplitClipCommand(0, 0, split_time=2.0)
        cmd.execute(mock_timeline)
        left, right = mock_timeline._tracks[0].clips

        assert left.source_start == pytest.approx(10.0)
        assert left.source_end == pytest.approx(14.0)
        assert right.source_start == pytest.approx(14.0)
        assert right.source_end == pytest.approx(20.0)
        assert right.id != left.id

        cmd.undo(mock_timeline)
        assert clip.source_end == pytest.approx(20.0)

    def test_speed_change_keeps_source_range(self, mock_timeline):
        from core.commands import ChangeSpeedCommand

        clip = mock_timeline._tracks[0].clips[0]
        clip.source_start = 4.0
        clip.source_end = 14.0
        clip.start = 2.0
        clip.end = 12.0
        cmd = ChangeSpeedCommand(0, 0, old_speed=1.0,
                                 new_speed=2.0, old_end=12.0)

        cmd.execute(mock_timeline)

        assert clip.end == pytest.approx(7.0)
        assert clip.source_start == pytest.approx(4.0)
        assert clip.source_end == pytest.approx(14.0)


class TestTimelineData:
    def test_track_importable(self):
        from core.project import Track
        t = Track()
        assert t.type == "video"

    def test_track_all_types(self):
        from core.project import Track
        for type_ in ("video", "audio", "zoom", "text", "cursor"):
            t = Track(type=type_)
            assert t.type == type_

    def test_clip_with_content(self):
        from core.project import Clip
        c = Clip(type="text", content="Hello", start=0.0, end=5.0)
        assert c.content == "Hello"
        assert c.start == 0.0
        assert c.end == 5.0


class TestTimelineGui:
    """TimelineWidget 渲染测试 — 需要真实 PyQt5+GL 环境"""

    def test_widget_creation(self):
        pytest.importorskip("PyQt5.QtWidgets", reason="无 PyQt5 环境")
        from ui.timeline import TimelineWidget
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        w = TimelineWidget()
        assert w.tracks == []

    def test_set_tracks(self):
        pytest.importorskip("PyQt5.QtWidgets")
        from ui.timeline import TimelineWidget
        from core.project import Track, Clip
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        w = TimelineWidget()
        tracks = [Track(type="video", clips=[
            Clip(type="video", start=0, end=5),
        ])]
        w.set_tracks(tracks)
        assert len(w.tracks) == 1

    def test_duration_setter(self):
        pytest.importorskip("PyQt5.QtWidgets")
        from ui.timeline import TimelineWidget
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        w = TimelineWidget()
        w.duration = 120.0
        assert w.duration == 120.0

    def test_duration_expands_timeline_content_width(self, qapp):
        from ui.timeline import TimelineWidget, TRACK_HEADER_WIDTH

        w = TimelineWidget()
        w.duration = 120.0

        expected = TRACK_HEADER_WIDTH + int(120.0 * w._pixels_per_sec)
        assert w.minimumWidth() >= expected

    def test_duration_preserves_short_recordings(self):
        pytest.importorskip("PyQt5.QtWidgets")
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w.duration = 1.25

        assert w.duration == pytest.approx(1.25)

    def test_set_tracks_clears_undo_history(self):
        pytest.importorskip("PyQt5.QtWidgets")
        from ui.timeline import TimelineWidget
        from core.commands import MoveClipCommand

        w = TimelineWidget()
        w._undo_stack.append(MoveClipCommand(0, 0, 0, 1, 1, 2))
        w._redo_stack.append(MoveClipCommand(0, 0, 1, 0, 2, 1))

        w.set_tracks([])

        assert w.can_undo is False
        assert w.can_redo is False

    def test_drag_emits_clips_changed_once(self, qapp):
        pytest.importorskip("PyQt5.QtWidgets")
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from ui.timeline import TimelineWidget
        from core.project import Track, Clip

        w = TimelineWidget()
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=5.0),
        ])])
        changes = []
        w.clips_changed.connect(lambda: changes.append(True))

        start = QPointF(w._time_to_x(2.0), 40)
        end = QPointF(w._time_to_x(3.0), 40)
        w.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, start,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        ))
        w.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, end,
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier,
        ))
        w.mouseReleaseEvent(QMouseEvent(
            QEvent.MouseButtonRelease, end,
            Qt.LeftButton, Qt.NoButton, Qt.NoModifier,
        ))

        assert w.tracks[0].clips[0].start == pytest.approx(2.0)
        assert len(changes) == 1
        assert w.can_undo is True

    def test_empty_zoom_track_can_add_clip_by_double_click(self, qapp):
        pytest.importorskip("PyQt5.QtWidgets")
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from ui.timeline import TimelineWidget, RULER_HEIGHT, TRACK_HEIGHT
        from core.project import Track

        w = TimelineWidget()
        w.set_tracks([Track(type="zoom", clips=[])])
        emitted = []
        w.zoom_double_clicked.connect(
            lambda time_s, clip: emitted.append((time_s, clip)))
        pos = QPointF(w._time_to_x(3.0), RULER_HEIGHT + TRACK_HEIGHT / 2)

        w.mouseDoubleClickEvent(QMouseEvent(
            QEvent.MouseButtonDblClick, pos,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        ))

        assert len(emitted) == 1
        assert emitted[0][0] == pytest.approx(3.0)
        assert emitted[0][1] is None

    def test_double_click_existing_zoom_emits_that_clip(self, qapp):
        pytest.importorskip("PyQt5.QtWidgets")
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from ui.timeline import TimelineWidget, RULER_HEIGHT, TRACK_HEIGHT
        from core.project import Track, Clip

        clip = Clip(type="zoom", start=1.0, end=4.0,
                    rect=[100, 100, 400, 300])
        w = TimelineWidget()
        w.set_tracks([Track(type="zoom", clips=[clip])])
        emitted = []
        w.zoom_double_clicked.connect(
            lambda time_s, selected: emitted.append((time_s, selected)))
        pos = QPointF(w._time_to_x(2.0), RULER_HEIGHT + TRACK_HEIGHT / 2)

        w.mouseDoubleClickEvent(QMouseEvent(
            QEvent.MouseButtonDblClick, pos,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        ))

        assert len(emitted) == 1
        assert emitted[0][1] is clip

    def test_single_click_zoom_clip_emits_selected_clip(self, qapp):
        pytest.importorskip("PyQt5.QtWidgets")
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from ui.timeline import TimelineWidget, RULER_HEIGHT, TRACK_HEIGHT
        from core.project import Track, Clip

        clip = Clip(type="zoom", start=1.0, end=4.0,
                    rect=[100, 100, 400, 200])
        w = TimelineWidget()
        w.set_tracks([Track(type="zoom", clips=[clip])])
        selected = []
        w.zoom_clip_selected.connect(selected.append)
        pos = QPointF(w._time_to_x(2.0), RULER_HEIGHT + TRACK_HEIGHT / 2)

        w.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, pos,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        ))

        assert selected == [clip]
