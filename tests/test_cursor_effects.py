"""测试光标特效 — core/cursor_effects.py"""

import pytest
from PIL import Image, ImageDraw
from core.compositor import Effect, CompositorContext
from core.cursor_effects import CursorEffect


class TestCursorEffectConfig:
    def test_default_config(self):
        effect = CursorEffect()
        assert effect.cursor_size == 32
        assert effect.smooth_alpha == 0.3
        assert effect.trail_length == 8
        assert effect.enabled["smooth"] is True
        assert effect.enabled["trail"] is True
        assert effect.enabled["ripple"] is True
        assert effect.enabled["blur"] is False
        assert effect.enabled["sway"] is False
        assert effect.cursor_style == "dot"

    def test_constructor_preserves_theme_and_style(self):
        effect = CursorEffect(cursor_theme="light", cursor_style="ring")

        assert effect.cursor_theme == "light"
        assert effect.cursor_style == "ring"

    def test_supported_cursor_styles(self):
        assert CursorEffect.CURSOR_STYLES == (
            "dot", "ring", "spotlight", "arrow",
        )

    def test_preview_mode_reduces_trail(self):
        effect = CursorEffect(cursor_size=24)
        effect.set_preview_mode(True)
        assert effect.trail_length == 4
        assert effect.enabled["blur"] is False

    def test_preview_mode_disabled(self):
        effect = CursorEffect()
        effect.set_preview_mode(False)
        assert effect.trail_length == 8


class TestCursorEffectApply:
    def _make_context(self, x=100, y=100, ts=0.0,
                      render_ts=None, reference_fps=60):
        frame = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        return CompositorContext(
            frame=frame, cursor_x=x, cursor_y=y,
            cursor_state="idle", click_events=[],
            frame_index=0, timestamp=ts,
            zoom_rect=None, width=320, height=240,
            render_timestamp=render_ts,
            reference_fps=reference_fps,
        )

    def test_apply_returns_pil_image(self):
        effect = CursorEffect()
        ctx = self._make_context()
        result = effect.apply(Image.new("RGBA", (320, 240), (0, 0, 0, 255)), ctx)
        assert isinstance(result, Image.Image)
        assert result.size == (320, 240)

    def test_apply_does_not_allocate_full_frame_effect_overlays(self, monkeypatch):
        import core.cursor_effects as cursor_module

        effect = CursorEffect(cursor_size=32)
        frame = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        ctx = self._make_context(x=160, y=120)
        original_new = cursor_module.Image.new
        full_frame_allocations = []

        def tracked_new(mode, size, *args, **kwargs):
            if size == frame.size:
                full_frame_allocations.append(size)
            return original_new(mode, size, *args, **kwargs)

        monkeypatch.setattr(cursor_module.Image, "new", tracked_new)

        effect.apply(frame, ctx)

        assert full_frame_allocations == []

    def test_mouse_movement_draws_cursor(self):
        effect = CursorEffect()
        for k in effect.enabled:
            effect.enabled[k] = False

        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        ctx = self._make_context(x=50, y=50)
        result = effect.apply(bg, ctx)

        px = result.getpixel((55, 55))
        assert px[3] > 0

    def test_trail_draws_multiple_points(self):
        effect = CursorEffect()
        effect.enabled["smooth"] = False
        effect.enabled["ripple"] = False
        effect.enabled["sway"] = False
        effect.enabled["blur"] = False
        effect.trail_length = 5

        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        ctx1 = self._make_context(x=10, y=10, ts=0.0)
        effect.apply(bg.copy(), ctx1)

        ctx2 = self._make_context(x=50, y=50, ts=0.1)
        result2 = effect.apply(bg.copy(), ctx2)

        # 轨迹区域应有更多非透明像素
        px_single = sum(1 for x in range(40, 60) for y in range(40, 60)
                        if result2.getpixel((x, y))[3] > 0)
        assert px_single > 0

    def test_trail_stores_transformed_cursor_coordinates(self):
        effect = CursorEffect()
        effect.enabled["smooth"] = False
        effect.enabled["ripple"] = False
        effect.enabled["sway"] = False
        ctx = self._make_context(x=80, y=60)
        ctx.raw_cursor_x = 10
        ctx.raw_cursor_y = 20
        ctx.zoom_rect = (0, 0, 50, 50)

        effect.apply(Image.new("RGBA", (320, 240)), ctx)

        assert effect._trail[-1][:2] == (80, 60)

    def test_click_ripple(self):
        effect = CursorEffect()
        effect.enabled["smooth"] = False
        effect.enabled["trail"] = False
        effect.enabled["sway"] = False
        effect.enabled["blur"] = False

        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        ctx = self._make_context(x=160, y=120, ts=0.1)
        ctx.click_events.append((160, 120, 0.0))
        result = effect.apply(bg, ctx)

        px = result.getpixel((160, 60))
        assert px[3] > 0

    @pytest.mark.parametrize("style", CursorEffect.CURSOR_STYLES)
    def test_each_cursor_style_renders(self, style):
        effect = CursorEffect(cursor_size=40, cursor_style=style)
        image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))

        effect._draw_cursor(image, 50, 50)

        assert image.getbbox() is not None

    def test_cursor_styles_have_distinct_shapes(self):
        rendered = []
        for style in CursorEffect.CURSOR_STYLES:
            effect = CursorEffect(cursor_size=40, cursor_style=style)
            image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            effect._draw_cursor(image, 50, 50)
            rendered.append(image.tobytes())

        assert len(set(rendered)) == len(CursorEffect.CURSOR_STYLES)

    def test_click_draws_two_ripple_rings(self):
        effect = CursorEffect()
        effect.ripple_duration = 0.5
        overlay = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        effect._draw_ripples(draw, [(60, 60, 0.0)], 0.25)

        horizontal_alpha = [overlay.getpixel((x, 60))[3]
                            for x in range(60, 110)]
        ring_runs = 0
        inside_ring = False
        for alpha in horizontal_alpha:
            if alpha and not inside_ring:
                ring_runs += 1
                inside_ring = True
            elif not alpha:
                inside_ring = False
        assert ring_runs >= 2

    def test_ripple_fades_over_time(self):
        effect = CursorEffect()

        def max_alpha(timestamp):
            overlay = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
            effect._draw_ripples(
                ImageDraw.Draw(overlay), [(60, 60, 0.0)], timestamp)
            return max(pixel[3] for pixel in overlay.getdata())

        assert max_alpha(0.1) > max_alpha(0.45)

    def test_smooth_reduces_jitter(self):
        effect = CursorEffect()
        effect.smooth_alpha = 0.2
        effect._smooth_x = 100.0
        effect._smooth_y = 100.0

        sx, sy = effect._apply_smooth(200, 200)
        assert 100 < sx < 200
        assert 100 < sy < 200

    def test_get_position_after_smooth(self):
        effect = CursorEffect()
        effect.smooth_alpha = 0.5

        for _ in range(20):
            effect._apply_smooth(150, 150)

        sx, sy = effect._apply_smooth(150, 150)
        assert sx == 150
        assert sy == 150

    def test_smoothing_is_consistent_across_render_fps(self):
        def smooth_position(render_fps):
            effect = CursorEffect()
            effect.enabled["trail"] = False
            effect.enabled["ripple"] = False
            frame = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
            effect.apply(frame, self._make_context(
                x=0, y=0, ts=0, render_ts=0, reference_fps=60))
            for index in range(1, round(render_fps * 0.2) + 1):
                timestamp = index / render_fps
                effect.apply(frame, self._make_context(
                    x=100, y=100, ts=timestamp,
                    render_ts=timestamp, reference_fps=60))
            return effect._smooth_x

        assert smooth_position(15) == pytest.approx(
            smooth_position(60), abs=0.01)

    def test_trail_uses_time_window_instead_of_frame_count(self):
        effect = CursorEffect()
        effect.enabled["smooth"] = False
        effect.enabled["ripple"] = False
        frame = Image.new("RGBA", (320, 240), (0, 0, 0, 255))

        for index, timestamp in enumerate((0.0, 0.05, 0.10, 0.15, 0.20)):
            effect.apply(frame, self._make_context(
                x=index * 10, y=50, ts=timestamp,
                render_ts=timestamp, reference_fps=60))

        assert [point[2] for point in effect._trail] == [0.10, 0.15, 0.20]

    def test_seek_backward_resets_temporal_cursor_state(self):
        effect = CursorEffect()
        effect.enabled["ripple"] = False
        frame = Image.new("RGBA", (320, 240), (0, 0, 0, 255))

        effect.apply(frame, self._make_context(
            x=0, y=50, ts=0.0, render_ts=0.0, reference_fps=60))
        effect.apply(frame, self._make_context(
            x=100, y=50, ts=0.2, render_ts=0.2, reference_fps=60))
        effect.apply(frame, self._make_context(
            x=25, y=50, ts=0.1, render_ts=0.1, reference_fps=60))

        assert effect._smooth_x == 25
        assert effect._trail == [(25, 50, 0.1)]


class TestCursorEffectEdgeCases:
    def test_no_mouse_movement(self):
        effect = CursorEffect()
        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))

        for k in effect.enabled:
            effect.enabled[k] = False
        effect.enabled["smooth"] = True

        ctx = CompositorContext(
            frame=bg, cursor_x=160, cursor_y=120,
            cursor_state="idle", click_events=[],
            frame_index=0, timestamp=0.0,
            zoom_rect=None, width=320, height=240,
        )
        result = effect.apply(bg, ctx)
        assert result.size == (320, 240)

    def test_cursor_off_screen(self):
        effect = CursorEffect()
        bg = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
        ctx = CompositorContext(
            frame=bg, cursor_x=9999, cursor_y=9999,
            cursor_state="idle", click_events=[],
            frame_index=0, timestamp=0.0,
            zoom_rect=None, width=100, height=100,
        )
        result = effect.apply(bg, ctx)
        assert result.size == (100, 100)
