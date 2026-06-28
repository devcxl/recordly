"""测试项目序列化 — core/project.py"""

import os
import json
import tempfile
from core.project import Project, Track, Clip, SourceInfo, CursorSettings, FrameStyle


class TestProject:
    def test_create_default_project(self):
        """默认项目有正确的初始值"""
        p = Project()
        assert p.version == "1.0"
        assert p.timeline == []
        assert p.source is None
        assert isinstance(p.cursor, CursorSettings)
        assert isinstance(p.frame_style, FrameStyle)

    def test_save_and_load_roundtrip(self):
        """保存再加载应恢复所有字段"""
        p = Project()
        p.source = SourceInfo(
            video="test.mp4", fps=30,
            width=1920, height=1080, duration=10.0,
        )
        p.timeline.append(Track(type="video", clips=[
            Clip(type="video", start=0, end=5, content="track1"),
        ]))
        p.timeline.append(Track(type="audio", clips=[
            Clip(type="audio", start=1, end=3, content="mic"),
        ]))
        p.cursor.smooth = True
        p.cursor.trail = True
        p.cursor.style = "macos-dark"
        p.frame_style.background = "gradient"
        p.frame_style.padding = 60

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            p.save(path)

            # 验证文件内容
            with open(path) as f:
                data = json.load(f)
            assert data["version"] == "1.0"
            assert len(data["timeline"]) == 2
            assert data["source"]["fps"] == 30
            assert data["cursor"]["style"] == "macos-dark"
            assert data["frame_style"]["padding"] == 60

            # 加载验证
            loaded = Project.load(path)
            assert loaded.version == "1.0"
            assert loaded.source.fps == 30
            assert loaded.source.width == 1920
            assert len(loaded.timeline) == 2
            assert loaded.timeline[0].clips[0].content == "track1"
            assert loaded.cursor.smooth is True
            assert loaded.frame_style.background == "gradient"
        finally:
            os.unlink(path)

    def test_save_empty_timeline(self):
        """空时间线可以保存和加载"""
        p = Project()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            p.save(path)
            loaded = Project.load(path)
            assert loaded.timeline == []
        finally:
            os.unlink(path)

    def test_save_without_source(self):
        """没有 source 信息的项目也可以保存"""
        p = Project()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            p.save(path)
            loaded = Project.load(path)
            assert loaded.source is None
        finally:
            os.unlink(path)

    def test_version_preserved(self):
        """版本号在保存/加载后保持不变"""
        p = Project()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            p.save(path)
            loaded = Project.load(path)
            assert loaded.version == "1.0"
        finally:
            os.unlink(path)


class TestTrack:
    def test_default_values(self):
        t = Track()
        assert t.type == "video"
        assert t.clips == []

    def test_custom_track(self):
        t = Track(type="zoom", name="缩放", clips=[
            Clip(type="zoom", start=2.0, end=8.0,
                 speed=2.0, content="zoom-in",
                 rect=[100, 200, 500, 300]),
        ])
        assert t.type == "zoom"
        assert t.clips[0].rect == [100, 200, 500, 300]


class TestSourceInfo:
    def test_default_values(self):
        s = SourceInfo()
        assert s.video == ""
        assert s.audio_mic == ""
        assert s.fps == 30
        assert s.duration == 0.0

    def test_custom_source(self):
        s = SourceInfo(video="rec.mp4", fps=60,
                       width=3840, height=2160)
        assert s.video == "rec.mp4"
        assert s.width == 3840
