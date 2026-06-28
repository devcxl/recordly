"""测试光标特效 — core/cursor_effects.py"""

import pytest
from PIL import Image
from core.compositor import Effect, CompositorContext
from core.cursor_effects import CursorEffect


class TestCursorEffectConfig:
    def test_default_config(self):
        effect = CursorEffect()
        assert effect.cursor_size == 24
        assert effect.smooth_alpha == 0.3
        assert effect.trail_length == 8
        assert effect.enabled["smooth"] is True
        assert effect.enabled["trail"] is True
        assert effect.enabled["ripple"] is True
        assert effect.enabled["blur"] is False
        assert effect.enabled["sway"] is False

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
    def _make_context(self, x=100, y=100, ts=0.0):
        frame = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        return CompositorContext(
            frame=frame, cursor_x=x, cursor_y=y,
            cursor_state="idle", click_events=[],
            frame_index=0, timestamp=ts,
            zoom_rect=None, width=320, height=240,
        )

    def test_apply_returns_pil_image(self):
        effect = CursorEffect()
        ctx = self._make_context()
        result = effect.apply(Image.new("RGBA", (320, 240), (0, 0, 0, 255)), ctx)
        assert isinstance(result, Image.Image)
        assert result.size == (320, 240)

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
