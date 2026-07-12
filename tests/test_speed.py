"""测试速度模块 — core/speed.py"""

import pytest
from core.speed import (
    timeline_to_source_time,
    source_to_timeline_time,
    get_clip_source_end,
    plan_clip_speed_change,
    format_speed_label,
)


class TestTimelineToSourceTime:
    def test_speed_one(self):
        """速度 1.0 时，时间线时间等于源时间"""
        assert timeline_to_source_time(5.0, 0.0, 1.0) == 5.0

    def test_speed_two(self):
        """速度 2.0 时，时间线推进 1 单位 = 源推进 2 单位"""
        assert timeline_to_source_time(5.0, 0.0, 2.0) == 10.0

    def test_speed_half(self):
        """速度 0.5 时，时间线推进 1 单位 = 源推进 0.5 单位"""
        assert timeline_to_source_time(5.0, 0.0, 0.5) == 2.5

    def test_with_offset(self):
        """clip 偏移后正确映射"""
        assert timeline_to_source_time(10.0, 5.0, 2.0) == 15.0  # 5 + (10-5)*2

    def test_at_clip_start(self):
        """在 clip 起点处，源时间等于 clip 起点"""
        assert timeline_to_source_time(3.0, 3.0, 2.0) == 3.0


class TestSourceToTimelineTime:
    def test_speed_one(self):
        assert source_to_timeline_time(5.0, 0.0, 1.0) == 5.0

    def test_speed_two(self):
        assert source_to_timeline_time(10.0, 0.0, 2.0) == 5.0

    def test_speed_half(self):
        assert source_to_timeline_time(5.0, 0.0, 0.5) == 10.0

    def test_with_offset(self):
        assert source_to_timeline_time(15.0, 5.0, 2.0) == 10.0  # 5 + (15-5)/2

    def test_roundtrip(self):
        """正反变换应等值"""
        for t in [0.0, 1.0, 5.0, 10.0]:
            for s in [0.5, 1.0, 2.0]:
                assert source_to_timeline_time(timeline_to_source_time(t, 0.0, s), 0.0, s) == pytest.approx(t)


class TestGetClipSourceEnd:
    def test_speed_one(self):
        assert get_clip_source_end(0.0, 10.0, 1.0) == 10.0

    def test_speed_two(self):
        """2x 速度时，clip 在源中覆盖更长时间"""
        assert get_clip_source_end(0.0, 5.0, 2.0) == 10.0

    def test_speed_half(self):
        """0.5x 速度时，clip 在源中覆盖更短时间"""
        assert get_clip_source_end(0.0, 10.0, 0.5) == 5.0


class TestPlanClipSpeedChange:
    def test_increase_speed(self):
        """速度从 1.0 变到 2.0，clip 时间线长度减半"""
        result = plan_clip_speed_change(0.0, 10.0, 1.0, 2.0)
        assert result == {"new_end": 5.0}

    def test_decrease_speed(self):
        """速度从 1.0 变到 0.5，clip 时间线长度翻倍"""
        result = plan_clip_speed_change(0.0, 10.0, 1.0, 0.5)
        assert result == {"new_end": 20.0}

    def test_no_change(self):
        """速度不变，end 不变"""
        result = plan_clip_speed_change(2.0, 8.0, 1.0, 1.0)
        assert result == {"new_end": 8.0}

    def test_blocks_overlap(self):
        """如果新 end 超过下一个 clip，返回 blocked_reason"""
        result = plan_clip_speed_change(0.0, 10.0, 1.0, 0.5, next_clip_start=12.0)
        assert result == {"blocked_reason": "clip-overlap"}

    def test_allows_no_overlap(self):
        """新 end 没超过下一个 clip 时正常返回 new_end"""
        result = plan_clip_speed_change(0.0, 10.0, 1.0, 0.5, next_clip_start=21.0)
        assert result == {"new_end": 20.0}

    def test_zero_speed(self):
        """速度为 0 返回 blocked"""
        result = plan_clip_speed_change(0.0, 10.0, 1.0, 0.0)
        assert result == {"blocked_reason": "invalid-speed"}

    def test_negative_speed(self):
        """速度为负数返回 blocked"""
        result = plan_clip_speed_change(0.0, 10.0, 1.0, -1.0)
        assert result == {"blocked_reason": "invalid-speed"}


class TestFormatSpeedLabel:
    def test_normal_speed(self):
        """1.0 返回空字符串"""
        assert format_speed_label(1.0) == ""

    def test_two_x(self):
        assert format_speed_label(2.0) == "2x"

    def test_one_point_five(self):
        assert format_speed_label(1.5) == "1.5x"

    def test_point_five(self):
        assert format_speed_label(0.5) == "0.5x"

    def test_one_point_two_five(self):
        assert format_speed_label(1.25) == "1.25x"
