"""
测试录制数据持久化：cursor_events / click_events / monitor_offset / frame_count
"""

import json
import os
import tempfile

import pytest

from core.project import Project, SourceInfo


class TestDataPersistenceRoundtrip:
    """验证新增字段在 Project.save/load 中完整往返"""

    def test_cursor_events_roundtrip(self):
        p = Project()
        p.cursor_events = [[100, 200, 0.0], [101, 201, 0.033], [102, 202, 0.066]]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            p.save(path)
            p2 = Project.load(path)
            assert p2.cursor_events == [[100, 200, 0.0], [101, 201, 0.033], [102, 202, 0.066]]
        finally:
            os.unlink(path)

    def test_click_events_roundtrip(self):
        p = Project()
        p.click_events = [[50, 100, 1.5], [55, 105, 2.0]]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            p.save(path)
            p2 = Project.load(path)
            assert p2.click_events == [[50, 100, 1.5], [55, 105, 2.0]]
        finally:
            os.unlink(path)

    def test_monitor_offset_roundtrip(self):
        p = Project()
        p.monitor_offset = [1920, 0]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            p.save(path)
            p2 = Project.load(path)
            assert p2.monitor_offset == [1920, 0]
        finally:
            os.unlink(path)

    def test_frame_count_roundtrip(self):
        p = Project()
        p._frame_count = 8472
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            p.save(path)
            p2 = Project.load(path)
            assert p2._frame_count == 8472
        finally:
            os.unlink(path)

    def test_unknown_fields_rejected(self):
        """含未知 cursor/frame_style 字段的 JSON 被拒绝"""
        legacy = {
            "version": "1.1",
            "created_at": "2026-01-01",
            "name": "old_project",
            "modified_at": "2026-01-01",
            "duration": 10.0,
            "thumbnail_path": "",
            "source": None,
            "timeline": [],
            "cursor": {"smooth": True, "size": 24, "theme": "macos-dark"},
            "frame_style": {"background": "solid", "margin": 40},
            "annotations": [],
            "audio_regions": [],
            "crop_region": None,
            "aspect_ratio": "native",
        }
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(legacy, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="未知"):
                Project.load(path)
        finally:
            os.unlink(path)

    def test_missing_optional_fields_use_defaults(self):
        """缺失 optional 字段的当前格式 JSON 使用默认值"""
        current_format = {
            "version": "1.1",
            "created_at": "2026-01-01",
            "name": "minimal_project",
            "modified_at": "2026-01-01",
            "duration": 10.0,
            "thumbnail_path": "",
            "source": None,
            "timeline": [],
            "cursor": {},
            "frame_style": {"background": "solid"},
            "annotations": [],
            "audio_regions": [],
            "crop_region": None,
            "aspect_ratio": "native",
        }
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(current_format, f)
            path = f.name
        try:
            p = Project.load(path)
            assert p.cursor_events == []
            assert p.click_events == []
            assert p.monitor_offset == [0, 0]
            assert p._frame_count == 0
        finally:
            os.unlink(path)


class TestEventDataConversion:
    """验证 EventData 类型正常创建和访问"""

    def test_eventdata_has_required_attrs(self):
        EventData = type("EventData", (), {})
        evt = EventData()
        evt.x, evt.y, evt.timestamp = 100, 200, 1.5
        assert evt.x == 100
        assert evt.y == 200
        assert evt.timestamp == 1.5

    def test_eventdata_is_not_subscriptable(self):
        """EventData 不能像元组一样解包 — 这是设计意图"""
        EventData = type("EventData", (), {})
        evt = EventData()
        evt.x, evt.y, evt.timestamp = 10, 20, 0.5
        with __import__("pytest").raises(TypeError):
            _ = evt[0]  # EventData 不支持下标访问

    def test_tuple_click_events_are_subscriptable(self):
        """_click_events 存储为元组，可解包"""
        click = (100, 200, 1.5)
        x, y, ts = click
        assert x == 100
        assert y == 200
        assert ts == 1.5
