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

    def test_add_clip_command_appends_and_records_index(self, mock_timeline):
        from core.commands import AddClipCommand

        cmd = AddClipCommand(track_index=0, clip_data={
            "id": "zoom-1",
            "type": "zoom",
            "start": 1.0,
            "end": 3.0,
        })

        cmd.execute(mock_timeline)

        assert cmd.clip_index == 1
        assert mock_timeline._tracks[0].clips[1].id == "zoom-1"

    def test_add_clip_command_inserts_at_fixed_index(self, mock_timeline):
        from core.commands import AddClipCommand

        cmd = AddClipCommand(
            track_index=0,
            clip_index=0,
            clip_data={"type": "zoom", "content": "inserted"},
        )

        cmd.execute(mock_timeline)

        assert [clip.content for clip in mock_timeline._tracks[0].clips] == [
            "inserted", "clip1",
        ]

    def test_add_clip_command_redo_restores_modified_clip_data(
            self, mock_timeline):
        from dataclasses import asdict
        from core.commands import AddClipCommand

        cmd = AddClipCommand(
            track_index=0,
            clip_index=0,
            clip_data={
                "id": "zoom-2",
                "type": "zoom",
                "start": 2.0,
                "end": 4.0,
                "rect": [10, 20, 300, 200],
                "transition_duration": 0.4,
            },
        )
        cmd.execute(mock_timeline)
        created = mock_timeline._tracks[0].clips[0]
        created.rect = [50, 60, 640, 360]
        created.transition_duration = 0.8
        expected = asdict(created)

        cmd.undo(mock_timeline)
        assert [clip.content for clip in mock_timeline._tracks[0].clips] == [
            "clip1",
        ]

        cmd.execute(mock_timeline)
        restored = mock_timeline._tracks[0].clips[0]
        assert asdict(restored) == expected

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

    @staticmethod
    def _drag_clip(timeline, track_index, clip_index, press_time,
                   candidate_start, release=False):
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from ui.timeline import RULER_HEIGHT, TRACK_HEADER_WIDTH, TRACK_HEIGHT

        clip = timeline.tracks[track_index].clips[clip_index]
        y = RULER_HEIGHT + track_index * TRACK_HEIGHT + TRACK_HEIGHT / 2
        press = QPointF(
            TRACK_HEADER_WIDTH + press_time * timeline._pixels_per_sec, y)
        move = QPointF(
            press.x() + (candidate_start - clip.start)
            * timeline._pixels_per_sec,
            y,
        )
        timeline.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, press,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        ))
        timeline.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, move,
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier,
        ))
        if release:
            timeline.mouseReleaseEvent(QMouseEvent(
                QEvent.MouseButtonRelease, move,
                Qt.LeftButton, Qt.NoButton, Qt.NoModifier,
            ))

    @pytest.mark.parametrize(
        "pixels_per_sec, target, moving, press_time, candidate_start, "
        "expected_start, alignment",
        [
            (32.0, (1.0, 3.0), (6.0, 8.0), 7.0, 3.25, 3.0, 3.0),
            (32.0, (1.0, 3.0), (6.0, 8.0), 7.0,
             3.265625, 3.265625, None),
            (32.0, (8.0, 10.0), (3.0, 5.0), 4.0, 5.75, 6.0, 8.0),
            (32.0, (8.0, 10.0), (3.0, 5.0), 4.0,
             5.734375, 5.734375, None),
            (64.0, (1.0, 3.0), (6.0, 8.0), 7.0, 3.125, 3.0, 3.0),
            (64.0, (1.0, 3.0), (6.0, 8.0), 7.0,
             3.1328125, 3.1328125, None),
        ],
    )
    def test_video_drag_snap_threshold_for_both_edges(
            self, qapp, pixels_per_sec, target, moving, press_time,
            candidate_start, expected_start, alignment):
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = pixels_per_sec
        w.duration = 20.0
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=target[0], end=target[1]),
            Clip(type="video", start=moving[0], end=moving[1]),
        ])])

        self._drag_clip(w, 0, 1, press_time, candidate_start)

        moving_clip = w.tracks[0].clips[1]
        assert moving_clip.start == pytest.approx(expected_start)
        assert moving_clip.end == pytest.approx(expected_start + 2.0)
        assert w._snap_alignment_time == alignment

    @pytest.mark.parametrize(
        "target_ends, expected_alignment",
        [
            ((5.2, 5.1), 5.1),
            ((5.2, 4.8), 5.2),
        ],
    )
    def test_video_drag_snap_uses_nearest_then_clip_order(
            self, qapp, target_ends, expected_alignment):
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = 32.0
        w.duration = 20.0
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=4.0, end=target_ends[0]),
            Clip(type="video", start=4.2, end=target_ends[1]),
            Clip(type="video", start=10.0, end=12.0),
        ])])

        self._drag_clip(w, 0, 2, 11.0, 5.0)

        moving_clip = w.tracks[0].clips[2]
        assert moving_clip.start == pytest.approx(expected_alignment)
        assert moving_clip.end == pytest.approx(expected_alignment + 2.0)
        assert w._snap_alignment_time == pytest.approx(expected_alignment)

    def test_snap_alignment_clears_after_drag_release(self, qapp):
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = 32.0
        w.duration = 20.0
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=3.0),
            Clip(type="video", start=6.0, end=8.0),
        ])])

        self._drag_clip(w, 0, 1, 7.0, 3.25, release=True)

        assert w._snap_alignment_time is None

    def test_new_mouse_press_clears_snap_alignment(self, qapp):
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from core.project import Clip, Track
        from ui.timeline import RULER_HEIGHT, TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = 32.0
        w.duration = 20.0
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=3.0),
            Clip(type="video", start=6.0, end=8.0),
        ])])
        self._drag_clip(w, 0, 1, 7.0, 3.25)
        assert w._snap_alignment_time == pytest.approx(3.0)

        ruler_press = QPointF(w._time_to_x(10.0), RULER_HEIGHT / 2)
        w.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, ruler_press,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        ))

        assert w._drag_state == "playhead"
        assert w._snap_alignment_time is None

    def test_set_tracks_clears_snap_alignment(self, qapp):
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = 32.0
        w.duration = 20.0
        tracks = [Track(type="video", clips=[
            Clip(type="video", start=1.0, end=3.0),
            Clip(type="video", start=6.0, end=8.0),
        ])]
        w.set_tracks(tracks)
        self._drag_clip(w, 0, 1, 7.0, 3.25)
        assert w._snap_alignment_time == pytest.approx(3.0)

        w.set_tracks([])

        assert w._snap_alignment_time is None

    def test_snap_alignment_paints_only_in_track_area(self, qapp):
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QImage, QPainter
        from core.project import Track
        from ui.timeline import RULER_HEIGHT, TRACK_HEIGHT, TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = 32.0
        w.duration = 20.0
        w.set_tracks([Track(type="video")])
        w.resize(w.minimumWidth(), w.minimumHeight())

        def render(alignment):
            w._snap_alignment_time = alignment
            image = QImage(w.size(), QImage.Format_ARGB32)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            w.render(painter)
            painter.end()
            return image

        without_line = render(None)
        with_line = render(10.0)
        x = w._time_to_x(10.0)

        assert any(
            without_line.pixel(x, y) != with_line.pixel(x, y)
            for y in range(RULER_HEIGHT, RULER_HEIGHT + TRACK_HEIGHT)
        )
        assert all(
            without_line.pixel(x, y) == with_line.pixel(x, y)
            for y in range(RULER_HEIGHT)
        )

    def test_drag_undo_redo_preserves_non_position_fields(self, qapp):
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        clip = Clip(
            type="video", content="recording", start=1.0, end=3.0,
            source_start=10.0, source_end=14.0, speed=2.0,
        )
        w = TimelineWidget()
        w.duration = 20.0
        w.set_tracks([Track(type="video", clips=[clip])])

        self._drag_clip(w, 0, 0, 2.0, 4.0, release=True)

        assert len(w._undo_stack) == 1
        assert (clip.start, clip.end, clip.source_start, clip.source_end,
                clip.speed, clip.content) == (
            4.0, 6.0, 10.0, 14.0, 2.0, "recording",
        )

        w.undo()
        assert (clip.start, clip.end, clip.source_start, clip.source_end,
                clip.speed, clip.content) == (
            1.0, 3.0, 10.0, 14.0, 2.0, "recording",
        )

        w.redo()
        assert (clip.start, clip.end, clip.source_start, clip.source_end,
                clip.speed, clip.content) == (
            4.0, 6.0, 10.0, 14.0, 2.0, "recording",
        )

    def test_five_pixel_snap_creates_one_undoable_move_command(self, qapp):
        from core.commands import MoveClipCommand
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        clip = Clip(
            type="video", content="recording", start=3.005, end=5.005,
            source_start=10.0, source_end=14.0, speed=2.0,
        )
        w = TimelineWidget()
        w._pixels_per_sec = 1000.0
        w.duration = 20.0
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=3.0),
            clip,
        ])])
        changes = []
        w.clips_changed.connect(lambda: changes.append(True))
        original_undo_count = len(w._undo_stack)

        self._drag_clip(w, 0, 1, 4.005, 3.005, release=True)

        assert (clip.start, clip.end) == pytest.approx((3.0, 5.0))
        assert len(w._undo_stack) == original_undo_count + 1
        assert isinstance(w._undo_stack[-1], MoveClipCommand)
        assert changes == [True]
        assert (clip.source_start, clip.source_end, clip.speed, clip.content) == (
            10.0, 14.0, 2.0, "recording",
        )

        w.undo()
        assert (clip.start, clip.end) == pytest.approx((3.005, 5.005))
        assert (clip.source_start, clip.source_end, clip.speed, clip.content) == (
            10.0, 14.0, 2.0, "recording",
        )

        w.redo()
        assert (clip.start, clip.end) == pytest.approx((3.0, 5.0))
        assert (clip.source_start, clip.source_end, clip.speed, clip.content) == (
            10.0, 14.0, 2.0, "recording",
        )

    @pytest.mark.parametrize(
        "track_type, moving_type",
        [("audio", "video"), ("video", "audio"), ("zoom", "zoom")],
    )
    def test_drag_snap_requires_video_track_and_clip(
            self, qapp, track_type, moving_type):
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = 32.0
        w.duration = 20.0
        w.set_tracks([Track(type=track_type, clips=[
            Clip(type="video", start=1.0, end=3.0),
            Clip(type=moving_type, start=6.0, end=8.0),
        ])])

        self._drag_clip(w, 0, 1, 7.0, 3.25)

        assert w.tracks[0].clips[1].start == pytest.approx(3.25)
        assert w._snap_alignment_time is None

    def test_drag_snap_does_not_use_other_video_tracks(self, qapp):
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = 32.0
        w.duration = 20.0
        w.set_tracks([
            Track(type="video", clips=[
                Clip(type="video", start=1.0, end=3.0),
            ]),
            Track(type="video", clips=[
                Clip(type="video", start=6.0, end=8.0),
            ]),
        ])

        self._drag_clip(w, 1, 0, 7.0, 3.25)

        assert w.tracks[1].clips[0].start == pytest.approx(3.25)
        assert w._snap_alignment_time is None

    def test_resize_does_not_snap_clip_edges(self, qapp):
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from core.project import Clip, Track
        from ui.timeline import RULER_HEIGHT, TRACK_HEIGHT, TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = 32.0
        w.duration = 20.0
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=3.0),
            Clip(type="video", start=6.0, end=8.0),
        ])])
        y = RULER_HEIGHT + TRACK_HEIGHT / 2
        press = QPointF(w._time_to_x(6.0), y)
        move = QPointF(press.x() + (3.25 - 6.0) * w._pixels_per_sec, y)

        w.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, press,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        ))
        w.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, move,
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier,
        ))

        assert w._drag_state == "resize_left"
        assert w.tracks[0].clips[1].start == pytest.approx(3.25)
        assert w._snap_alignment_time is None

    def test_snap_alignment_clears_after_leaving_threshold(self, qapp):
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from core.project import Clip, Track
        from ui.timeline import RULER_HEIGHT, TRACK_HEIGHT, TimelineWidget

        w = TimelineWidget()
        w._pixels_per_sec = 32.0
        w.duration = 20.0
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=3.0),
            Clip(type="video", start=6.0, end=8.0),
        ])])
        self._drag_clip(w, 0, 1, 7.0, 3.25)
        assert w._snap_alignment_time == pytest.approx(3.0)

        y = RULER_HEIGHT + TRACK_HEIGHT / 2
        move = QPointF(
            w._drag_start_x + (3.5 - w._drag_orig_start)
            * w._pixels_per_sec,
            y,
        )
        w.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, move,
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier,
        ))

        assert w.tracks[0].clips[1].start == pytest.approx(3.5)
        assert w._snap_alignment_time is None

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

    def test_x_key_splits_playhead_video_without_selection(self, qapp):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=5.0),
        ])])
        w.playhead = 3.0

        QTest.keyClick(w, Qt.Key_X, Qt.NoModifier)

        assert [(clip.start, clip.end) for clip in w.tracks[0].clips] == [
            (1.0, 3.0), (3.0, 5.0),
        ]

    def test_x_key_without_playhead_video_only_emits_status(self, qapp):
        from copy import deepcopy
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        from core.commands import MoveClipCommand
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=2.0),
        ])])
        w.playhead = 3.0
        w._selected_track = 0
        w._selected_clip = 0
        undo_command = MoveClipCommand(0, 0, 1.0, 1.5, 2.0, 2.5)
        redo_command = MoveClipCommand(0, 0, 1.5, 1.0, 2.5, 2.0)
        w._undo_stack.append(undo_command)
        w._redo_stack.append(redo_command)
        original_tracks = deepcopy(w.tracks)
        messages = []
        changes = []
        w.status_message.connect(messages.append)
        w.clips_changed.connect(lambda: changes.append(True))

        QTest.keyClick(w, Qt.Key_X, Qt.NoModifier)

        assert messages == ["播放头下无视频片段"]
        assert changes == []
        assert w.tracks == original_tracks
        assert (w._selected_track, w._selected_clip) == (0, 0)
        assert w._undo_stack == [undo_command]
        assert w._redo_stack == [redo_command]

    def test_playhead_video_uses_track_then_clip_order(self, qapp):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w.set_tracks([
            Track(type="audio", clips=[
                Clip(type="video", content="wrong track", start=0.0, end=8.0),
            ]),
            Track(type="video", clips=[
                Clip(type="audio", content="wrong clip", start=0.0, end=8.0),
                Clip(type="video", content="first", start=1.0, end=7.0),
                Clip(type="video", content="second", start=2.0, end=6.0),
            ]),
            Track(type="video", clips=[
                Clip(type="video", content="later track", start=0.0, end=8.0),
            ]),
        ])
        w.playhead = 4.0

        QTest.keyClick(w, Qt.Key_X, Qt.NoModifier)

        assert [(clip.content, clip.start, clip.end)
                for clip in w.tracks[1].clips] == [
            ("wrong clip", 0.0, 8.0),
            ("first", 1.0, 4.0),
            ("first", 4.0, 7.0),
            ("second", 2.0, 6.0),
        ]
        assert len(w.tracks[0].clips) == 1
        assert len(w.tracks[2].clips) == 1

    def test_x_key_ignores_audio_covering_playhead(self, qapp):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w.set_tracks([Track(type="audio", clips=[
            Clip(type="audio", start=1.0, end=5.0),
        ])])
        w.playhead = 3.0
        messages = []
        w.status_message.connect(messages.append)

        QTest.keyClick(w, Qt.Key_X, Qt.NoModifier)

        assert len(w.tracks[0].clips) == 1
        assert messages == ["播放头下无视频片段"]

    @pytest.mark.parametrize("playhead", [1.0, 5.0])
    def test_playhead_video_edges_are_not_split(self, qapp, playhead):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=5.0),
        ])])
        w.playhead = playhead
        messages = []
        w.status_message.connect(messages.append)

        QTest.keyClick(w, Qt.Key_X, Qt.NoModifier)

        assert len(w.tracks[0].clips) == 1
        assert messages == ["播放头下无视频片段"]

    @pytest.mark.parametrize("modifier_names", [
        ("ControlModifier",),
        ("ShiftModifier",),
        ("AltModifier",),
        ("ControlModifier", "ShiftModifier"),
    ])
    def test_x_key_with_modifiers_is_ignored(self, qapp, modifier_names):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        w = TimelineWidget()
        w.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=5.0),
        ])])
        w.playhead = 3.0
        messages = []
        w.status_message.connect(messages.append)
        modifiers = Qt.NoModifier
        for name in modifier_names:
            modifiers |= getattr(Qt, name)

        QTest.keyClick(w, Qt.Key_X, modifiers)

        assert len(w.tracks[0].clips) == 1
        assert messages == []
        assert w.can_undo is False

    def test_x_key_source_ranges_and_undo_redo_match_s_path(self, qapp):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        def make_timeline():
            timeline = TimelineWidget()
            timeline.set_tracks([Track(type="video", clips=[Clip(
                id="source", type="video", content="recording",
                start=1.0, end=5.0, source_start=10.0,
                source_end=18.0, speed=2.0,
            )])])
            timeline.playhead = 3.0
            return timeline

        def split_state(timeline):
            return [(clip.start, clip.end, clip.source_start,
                     clip.source_end, clip.speed, clip.content)
                    for clip in timeline.tracks[0].clips]

        x_timeline = make_timeline()
        s_timeline = make_timeline()
        s_timeline._selected_track = 0
        s_timeline._selected_clip = 0

        QTest.keyClick(x_timeline, Qt.Key_X, Qt.NoModifier)
        s_timeline._split_clip(0, 0)

        assert split_state(x_timeline) == split_state(s_timeline) == [
            (1.0, 3.0, 10.0, 14.0, 2.0, "recording"),
            (3.0, 5.0, 14.0, 18.0, 2.0, "recording"),
        ]
        assert x_timeline.can_undo is True
        x_timeline.undo()
        assert split_state(x_timeline) == [
            (1.0, 5.0, 10.0, 18.0, 2.0, "recording"),
        ]
        assert x_timeline.can_redo is True
        x_timeline.redo()
        assert split_state(x_timeline) == split_state(s_timeline)

    def test_x_key_only_applies_with_timeline_focus(self, qapp):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        from PyQt5.QtWidgets import QLineEdit, QVBoxLayout, QWidget
        from core.project import Clip, Track
        from ui.timeline import TimelineWidget

        window = QWidget()
        layout = QVBoxLayout(window)
        timeline = TimelineWidget()
        timeline.set_tracks([Track(type="video", clips=[
            Clip(type="video", start=1.0, end=5.0),
        ])])
        timeline.playhead = 3.0
        editor = QLineEdit()
        layout.addWidget(timeline)
        layout.addWidget(editor)
        window.show()
        window.activateWindow()
        editor.setFocus()
        qapp.processEvents()

        QTest.keyClick(editor, Qt.Key_X, Qt.NoModifier)

        assert editor.text() == "x"
        assert len(timeline.tracks[0].clips) == 1
        assert timeline.can_undo is False
        window.close()

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
