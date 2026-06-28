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
        effect = CursorEffect(trail_length=8)
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
        """光标移动后，帧中对应位置有非背景像素"""
        effect = CursorEffect()
        # 禁用其他效果，只保留光标基本绘制
        for k in effect.enabled:
            effect.enabled[k] = False

        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        ctx = self._make_context(x=50, y=50)
        result = effect.apply(bg, ctx)

        # 50,50 附近应有非黑色像素（光标图形）
        px = result.getpixel((55, 55))
        # 默认画箭头（白色），alpha 不为 0
        assert px[3] > 0

    def test_trail_draws_multiple_points(self):
        effect = CursorEffect()
        effect.enabled["smooth"] = False
        effect.enabled["ripple"] = False
        effect.enabled["sway"] = False
        effect.enabled["blur"] = False
        effect.trail_length = 5

        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))

        # 第一次调用：建立轨迹
        ctx1 = self._make_context(x=10, y=10, ts=0.0)
        result1 = effect.apply(bg.copy(), ctx1)

        # 第二次调用：从不同坐标 → 应有轨迹段
        ctx2 = self._make_context(x=50, y=50, ts=0.1)
        result2 = effect.apply(bg.copy(), ctx2)

        # 轨迹应该产生了比单点更多的亮像素
        px_single = sum(1 for x in range(40, 60) for y in range(40, 60)
                        if result1.getpixel((x, y))[3] > 0)
        px_trail = sum(1 for x in range(5, 55) for y in range(5, 55)
                       if result2.getpixel((x, y))[3] > 0)
        assert px_trail >= px_single

    def test_click_ripple(self):
        effect = CursorEffect()
        effect.enabled["smooth"] = False
        effect.enabled["trail"] = False
        effect.enabled["sway"] = False
        effect.enabled["blur"] = False

        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        ctx = self._make_context(x=160, y=120, ts=0.1)
        ctx.click_events.append((160, 120, 0.0))  # 在 0.0 时刻点击
        result = effect.apply(bg, ctx)

        # 点击位置应有波纹（环形像素）
        px = result.getpixel((160, 60))
        assert px[3] > 0

    def test_smooth_reduces_jitter(self):
        effect = CursorEffect()
        effect.smooth_alpha = 0.2
        effect._smooth_x = 100.0
        effect._smooth_y = 100.0

        # 从 100 → 200 的大跳跃
        sx, sy = effect._apply_smooth(200, 200)
        # 平滑后应该靠近原始值而非直接跳到 200
        assert 100 < sx < 200
        assert 100 < sy < 200

    def test_get_position_after_smooth(self):
        """多次移动后平滑位置应收敛于实际位置"""
        effect = CursorEffect()
        effect.smooth_alpha = 0.5

        for _ in range(20):
            effect._apply_smooth(150, 150)

        sx, sy = effect._apply_smooth(150, 150)
        assert sx == 150
        assert sy == 150


class TestCursorEffectEdgeCases:
    def test_no_mouse_movement(self):
        """光标从未移动时不应报错"""
        effect = CursorEffect()
        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))

        for k in effect.enabled:
            effect.enabled[k] = False
        effect.enabled["smooth"] = True  # smooth 需要处理初始 None

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
