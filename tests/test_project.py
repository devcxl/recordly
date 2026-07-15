"""测试项目序列化 — core/project.py"""

import os
import json
import tempfile
from core.project import Project, Track, Clip, SourceInfo, CursorSettings, FrameStyle


class TestProject:
    def test_create_default_project(self):
        """默认项目有正确的初始值"""
        p = Project()
        assert p.version == "1.1"
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
            assert data["version"] == "1.1"
            assert len(data["timeline"]) == 2
            assert data["source"]["fps"] == 30
            assert data["cursor"]["style"] == "macos-dark"
            assert data["frame_style"]["padding"] == 60

            # 加载验证
            loaded = Project.load(path)
            assert loaded.version == "1.1"
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
            assert loaded.version == "1.1"
        finally:
            os.unlink(path)

    def test_new_fields_roundtrip(self):
        """新字段 name/modified_at/duration/thumbnail_path 保存/加载后正确保留"""
        p = Project()
        p.name = "My Project"
        p.duration = 120.5
        p.thumbnail_path = "/thumbnails/proj.png"

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            p.save(path)
            loaded = Project.load(path)
            assert loaded.name == "My Project"
            assert loaded.duration == 120.5
            assert loaded.thumbnail_path == "/thumbnails/proj.png"
            # modified_at 在 save() 中被设为当前时间，非空即可
            assert loaded.modified_at != ""
        finally:
            os.unlink(path)

    def test_load_legacy_json_without_new_fields(self):
        """加载旧版 JSON（无新字段）不报错，默认值生效"""
        legacy = {
            "version": "1.0",
            "created_at": "2024-01-01T00:00:00",
            "source": None,
            "timeline": [],
            "cursor": {},
            "frame_style": {},
            "annotations": [],
            "audio_regions": [],
            "crop_region": None,
            "aspect_ratio": "native",
        }
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w",
                                         delete=False) as f:
            json.dump(legacy, f)
            path = f.name
        try:
            loaded = Project.load(path)
            assert loaded.name == ""
            assert loaded.modified_at == ""
            assert loaded.duration == 0.0
            assert loaded.thumbnail_path == ""
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


class TestAudioRegionSync:
    def test_tracks_move_delete_and_split(self):
        from core.project import (
            AudioRegion, sync_audio_regions_from_clips,
        )

        original = AudioRegion(
            id="audio-1", start_ms=0, end_ms=4000,
            source_start_ms=0, source_end_ms=4000,
            audio_path="/tmp/music.wav", volume=0.5, name="music.wav",
        )
        moved = Clip(
            id="audio-1", type="audio_extra",
            start=2.0, end=4.0,
            source_start=0.0, source_end=2.0,
            source_path="/tmp/music.wav", volume=0.5,
            content="music.wav",
        )
        split = Clip(
            id="audio-2", type="audio_extra",
            start=4.0, end=6.0,
            source_start=2.0, source_end=4.0,
            source_path="/tmp/music.wav", volume=0.5,
            content="music.wav",
        )

        synced = sync_audio_regions_from_clips([moved, split], [original])

        assert [region.id for region in synced] == ["audio-1", "audio-2"]
        assert synced[0].start_ms == 2000
        assert synced[0].end_ms == 4000
        assert synced[1].source_start_ms == 2000
        assert synced[1].source_end_ms == 4000

        after_delete = sync_audio_regions_from_clips([split], synced)
        assert [region.id for region in after_delete] == ["audio-2"]


class TestAtomicSave:
    def test_atomic_save_preserves_original_on_failure(self, monkeypatch):
        project = Project()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            # 先保存一次
            project.save(path)
            with open(path) as f:
                original = f.read()

            # 模拟写入中途磁盘满
            monkeypatch.setattr("json.dump", lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")))

            try:
                project.save(path)
            except OSError:
                pass

            # 原文件内容不变
            with open(path) as f:
                assert f.read() == original
        finally:
            os.unlink(path)

    def test_atomic_save_no_temp_leftover(self):
        project = Project()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "project.json")
            project.save(path)
            assert os.path.exists(path)
            # 临时文件应已通过 os.replace 清理
            temps = [f for f in os.listdir(tmpdir) if f.startswith(".project-")]
            assert len(temps) == 0
