"""Tests for ui/timeline.py — 命令层无 Qt 依赖，渲染层需 Qt"""

import pytest


class TestTimelineCommands:
    """Command 模式数据层测试（不创建 QWidget）"""

    @pytest.fixture
    def mock_timeline(self):
        from unittest.mock import MagicMock
        from core.project import Track
        tl = MagicMock()
        tl._tracks = [
            Track(type="video", content="clip1", start=0.0, end=5.0),
            Track(type="audio", content="clip2", start=2.0, end=7.0),
        ]
        return tl

    def test_move_clip_command(self, mock_timeline):
        from core.commands import MoveClipCommand
        cmd = MoveClipCommand(
            track_index=0,
            old_start=0.0, new_start=1.0,
            old_end=5.0, new_end=6.0,
        )
        cmd.execute(mock_timeline)
        assert mock_timeline._tracks[0].start == 1.0
        cmd.undo(mock_timeline)
        assert mock_timeline._tracks[0].start == 0.0

    def test_move_clip_unchanged(self, mock_timeline):
        from core.commands import MoveClipCommand
        cmd = MoveClipCommand(0, 0.0, 0.0, 5.0, 5.0)
        cmd.execute(mock_timeline)

    def test_delete_clip_command(self, mock_timeline):
        from core.commands import DeleteClipCommand
        cmd = DeleteClipCommand(track_index=0)
        cmd.execute(mock_timeline)
        assert len(mock_timeline._tracks) == 1
        cmd.undo(mock_timeline)
        assert len(mock_timeline._tracks) == 2

    def test_split_clip_command(self, mock_timeline):
        from core.commands import SplitClipCommand
        cmd = SplitClipCommand(track_index=0, split_time=2.5)
        cmd.execute(mock_timeline)
        assert mock_timeline._tracks[0].end == pytest.approx(2.5)
        assert len(mock_timeline._tracks) == 3
        cmd.undo(mock_timeline)
        assert len(mock_timeline._tracks) == 2


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

    def test_track_with_content(self):
        from core.project import Track
        t = Track(type="text", content="Hello", start=0.0, end=5.0)
        assert t.content == "Hello"
        assert t.start == 0.0
        assert t.end == 5.0


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
        from core.project import Track
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        w = TimelineWidget()
        tracks = [Track(type="video", start=0, end=5)]
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
