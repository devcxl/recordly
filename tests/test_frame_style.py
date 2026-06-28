"""测试帧样式 — core/frame_style.py"""

import pytest
from PIL import Image
from core.compositor import CompositorContext
from core.frame_style import FrameStyle, FrameStyleEffect


class TestFrameStyleDefaults:
    def test_default_config(self):
        style = FrameStyle()
        assert style.background == "solid"
        assert style.bg_color == (26, 26, 26)
        assert style.padding == 40
        assert style.corner_radius == 16
        assert style.shadow is True

    def test_custom_config(self):
        style = FrameStyle(
            background="gradient",
            padding=80,
            corner_radius=0,
            shadow=False,
        )
        assert style.background == "gradient"
        assert style.shadow is False


class TestFrameStyleEffect:
    def _make_context(self, ts=0.0):
        return CompositorContext(
            frame=Image.new("RGBA", (320, 240), (80, 80, 80, 255)),
            cursor_x=0, cursor_y=0, cursor_state="idle",
            click_events=[], frame_index=0, timestamp=ts,
            zoom_rect=None, width=320, height=240,
        )

    def test_apply_solid_background(self):
        """纯色背景：画布 = frame + 2*padding + shadow_offset"""
        style = FrameStyle(padding=40, shadow=True, shadow_offset=8)
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (320, 240), (80, 80, 80))
        ctx = self._make_context()
        result = effect.apply(frame, ctx)

        expected_w = 320 + 2 * 40 + 8  # shadow_offset
        expected_h = 240 + 2 * 40 + 8
        assert result.size == (expected_w, expected_h)

    def test_no_shadow_smaller_canvas(self):
        """关闭阴影时画布 = frame + 2*padding"""
        style = FrameStyle(padding=20, shadow=False)
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (100, 100), (80, 80, 80))
        ctx = self._make_context()
        result = effect.apply(frame, ctx)
        assert result.size == (140, 140)

    def test_shadow_adds_offset(self):
        """阴影偏移量计入画布尺寸"""
        style = FrameStyle(padding=20, shadow=True, shadow_offset=8)
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (100, 100), (80, 80, 80))
        ctx = self._make_context()
        result = effect.apply(frame, ctx)
        assert result.size == (148, 148)

    def test_corner_radius_zero(self):
        """corner_radius=0 时角部完全不透明"""
        style = FrameStyle(padding=10, corner_radius=0, shadow=False)
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (100, 100), (200, 100, 50))
        ctx = self._make_context()
        result = effect.apply(frame, ctx)

        # 角部 (10,10) 应在视频帧区域内，完全不透明
        px = result.getpixel((10, 10))
        assert px[:3] == (200, 100, 50)

    def test_corner_radius_positive(self):
        """corner_radius=16 时角部被圆角遮罩影响"""
        style = FrameStyle(padding=10, corner_radius=16, shadow=False)
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (100, 100), (200, 100, 50))
        ctx = self._make_context()
        result = effect.apply(frame, ctx)

        # 帧内部远离边角的位置不受影响
        px = result.getpixel((80, 80))
        assert px[:3] == (200, 100, 50)

    def test_gradient_background(self):
        style = FrameStyle(background="gradient", padding=0, shadow=False)
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (50, 50), (100, 100, 100))
        ctx = self._make_context()
        result = effect.apply(frame, ctx)
        assert result.size == (50, 50)

    def test_padding_zero(self):
        """padding=0 且 shadow=False 时画布=原始尺寸"""
        style = FrameStyle(padding=0, shadow=False)
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (200, 150), (80, 80, 80))
        ctx = self._make_context()
        result = effect.apply(frame, ctx)
        assert result.size == (200, 150)

    def test_content_preserved(self):
        """帧内部内容应保持不变"""
        style = FrameStyle(padding=10, corner_radius=0, shadow=False)
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (100, 100), (200, 100, 50))
        ctx = self._make_context()
        result = effect.apply(frame, ctx)

        px = result.getpixel((10, 10))
        assert px[:3] == (200, 100, 50)

    def test_background_color(self):
        """背景区域应为指定的 bg_color"""
        style = FrameStyle(padding=10, shadow=False,
                           bg_color=(40, 50, 60))
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (100, 100), (200, 100, 50))
        ctx = self._make_context()
        result = effect.apply(frame, ctx)

        # 左边缘背景区域（padding 内）
        px = result.getpixel((0, 50))
        assert px[:3] == (40, 50, 60)


class TestWallpaperCache:
    def test_wallpaper_fallback(self):
        """壁纸文件不存在时应 fallback 到纯色"""
        style = FrameStyle(
            background="wallpaper",
            bg_wallpaper="/nonexistent/image.jpg",
            padding=0, shadow=False,
        )
        effect = FrameStyleEffect(style)
        frame = Image.new("RGB", (100, 100), (100, 100, 100))
        result = effect.apply(frame, CompositorContext(
            frame=frame, cursor_x=0, cursor_y=0,
            cursor_state="idle", click_events=[],
            frame_index=0, timestamp=0.0,
            zoom_rect=None, width=100, height=100,
        ))
        assert result.size == (100, 100)
