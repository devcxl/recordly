"""Tests for core/aspect_ratio.py"""

from core.aspect_ratio import (
    parse_aspect_ratio,
    normalize_even,
    calculate_export_dimensions,
    ExportDimensions,
)


class TestParseAspectRatio:
    def test_native_returns_none(self):
        assert parse_aspect_ratio("native") is None

    def test_16_9(self):
        assert parse_aspect_ratio("16:9") == 16 / 9

    def test_1_1(self):
        assert parse_aspect_ratio("1:1") == 1.0

    def test_4_5(self):
        assert parse_aspect_ratio("4:5") == 0.8

    def test_zero_division_returns_none(self):
        assert parse_aspect_ratio("1:0") is None

    def test_invalid_format_returns_none(self):
        assert parse_aspect_ratio("invalid") is None


class TestNormalizeEven:
    def test_odd_becomes_even(self):
        assert normalize_even(3) == 2

    def test_even_stays_even(self):
        assert normalize_even(4) == 4

    def test_zero(self):
        assert normalize_even(0) == 0

    def test_one(self):
        assert normalize_even(1) == 0


class TestCalculateExportDimensions:
    def test_native_returns_source(self):
        d = calculate_export_dimensions(1920, 1080, "native")
        assert d == ExportDimensions(1920, 1080)

    def test_16_9_exact_match(self):
        d = calculate_export_dimensions(1920, 1080, "16:9")
        assert d == ExportDimensions(1920, 1080)

    def test_1_1_from_landscape(self):
        d = calculate_export_dimensions(1920, 1080, "1:1")
        assert d == ExportDimensions(1080, 1080)

    def test_4_5_portrait(self):
        d = calculate_export_dimensions(1920, 1080, "4:5")
        # 4:5=0.8, current=1.778, wider → fit height: h=1080, w=1080*0.8=864
        assert d == ExportDimensions(864, 1080)

    def test_9_16_vertical(self):
        d = calculate_export_dimensions(1920, 1080, "9:16")
        # 9:16=0.5625, current=1.778, wider → h=1080, w=1080*0.5625=607.5→606
        assert d == ExportDimensions(606, 1080)

    def test_custom_ratio(self):
        d = calculate_export_dimensions(1920, 1080, "21:9")
        # 21:9≈2.333, current=1.778, taller → w=1920, h=1920/2.333=823→822
        assert d == ExportDimensions(1920, 822)

    def test_quality_reduces_resolution(self):
        d = calculate_export_dimensions(1920, 1080, "native", quality=0.5)
        assert d == ExportDimensions(960, 540)

    def test_crop_region_applied(self):
        d = calculate_export_dimensions(
            1920, 1080, "16:9", crop_width=0.5, crop_height=1.0)
        # cw=960, ch=1080, ratio=16:9→1.778, current=0.889, taller → w=960, h=960/1.778=540
        assert d == ExportDimensions(960, 540)

    def test_all_values_even(self):
        d = calculate_export_dimensions(1921, 1081, "4:3")
        assert d.width % 2 == 0
        assert d.height % 2 == 0

    def test_zero_source_dimensions(self):
        d = calculate_export_dimensions(0, 0, "16:9")
        assert d.width == 2
        assert d.height == 2

    # ── 分辨率上限测试 ────────────────────────────────────

    def test_max_height_caps_16_9(self):
        """1080p 上限：3840×2160 的 16:9 源应缩放到 1920×1080"""
        d = calculate_export_dimensions(3840, 2160, "native", max_height=1080)
        assert d.width == 1920
        assert d.height == 1080

    def test_max_height_caps_square(self):
        """1080p 上限 + 1:1 宽高比：2160×2160 → 1080×1080"""
        d = calculate_export_dimensions(3840, 2160, "1:1", max_height=1080)
        assert d.width == 1080
        assert d.height == 1080

    def test_max_height_caps_vertical(self):
        """1080p 上限 + 9:16 宽高比：1215×2160 → 606×1080（经偶数归一化）"""
        d = calculate_export_dimensions(3840, 2160, "9:16", max_height=1080)
        assert d.width == 606
        assert d.height == 1080

    def test_max_height_no_upscale(self):
        """源小于上限时不应放大：640×480 源 + 1080p 上限 → 保持原尺寸"""
        d = calculate_export_dimensions(640, 480, "native", max_height=1080)
        assert d.width == 640
        assert d.height == 480

    def test_max_height_with_quality(self):
        """1080p + 50% 质量：先缩放到 1080p，再乘质量"""
        d = calculate_export_dimensions(3840, 2160, "native", max_height=1080, quality=0.5)
        assert d.width == 960
        assert d.height == 540

    def test_max_height_none_no_effect(self):
        """max_height=None 与不传等价"""
        d1 = calculate_export_dimensions(1920, 1080, "native", max_height=None)
        d2 = calculate_export_dimensions(1920, 1080, "native")
        assert d1 == d2
