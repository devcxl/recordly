"""光标特效 — 6 种光标效果，作为 Compositor 的 Effect 插件"""

import math
import os
import numpy as np
from PIL import Image, ImageDraw
from core.compositor import Effect, CompositorContext


class CursorEffect(Effect):
    """综合光标效果：平滑/波纹/拖尾/模糊/Sway/样式替换"""

    def __init__(self, cursor_size: int = 32, cursor_theme: str = "dark"):
        self.cursor_size = cursor_size
        self.cursor_theme = cursor_theme
        # 状态
        self._smooth_x: float | None = None
        self._smooth_y: float | None = None
        self._trail: list[tuple[int, int]] = []
        self._ripples: list[tuple[int, int, float]] = []  # (x, y, start_time)
        self._sway_time = 0.0

        # 配置参数
        self.smooth_alpha = 0.3
        self.trail_length = 8
        self.trail_opacity = 160
        self.ripple_duration = 0.5
        self.ripple_max_radius = 40
        self.sway_amplitude = 4
        self.sway_frequency = 2.0
        self.blur_strength = 4
        self.cursor_theme = "dark"
        self._preview_mode = False

        # 预载光标精灵图
        self._sprites: dict[str, Image.Image] = {}
        self._load_sprites()

        # 效果开关
        self.enabled = {
            "smooth": True,
            "trail": True,
            "ripple": True,
            "blur": False,
            "sway": False,
        }

    def _load_sprites(self):
        for theme in ("light", "dark"):
            path = os.path.join("resources", "cursors", theme, "arrow.png")
            if os.path.exists(path):
                try:
                    self._sprites[theme] = Image.open(path).convert("RGBA")
                except Exception:
                    pass

    def set_preview_mode(self, enabled: bool):
        """预览模式：降低特效精度"""
        self._preview_mode = enabled
        if enabled:
            self.enabled["blur"] = False
            self.trail_length = 4
        else:
            self.trail_length = 8

    # ── 各效果实现 ────────────────────────────────────────

    def _apply_smooth(self, cx: int, cy: int) -> tuple[int, int]:
        if self._smooth_x is None:
            self._smooth_x, self._smooth_y = float(cx), float(cy)
            return cx, cy
        self._smooth_x += (cx - self._smooth_x) * self.smooth_alpha
        self._smooth_y += (cy - self._smooth_y) * self.smooth_alpha
        return int(self._smooth_x), int(self._smooth_y)

    def _apply_sway(self, cx: int, cy: int, ts: float) -> tuple[int, int]:
        offset = self.sway_amplitude * math.sin(
            self.sway_frequency * ts * math.pi * 2)
        return cx + int(offset), cy

    def _draw_trail(self, draw: ImageDraw.ImageDraw,
                    raw_cx: int, raw_cy: int,
                    ctx: CompositorContext):
        self._trail.append((raw_cx, raw_cy))
        if len(self._trail) > self.trail_length:
            self._trail.pop(0)
        for i, (tx, ty) in enumerate(self._trail):
            if ctx.zoom_rect:
                zx, zy, zw, zh = ctx.zoom_rect
                tx = int((tx - zx) * ctx.width / max(zw, 1))
                ty = int((ty - zy) * ctx.height / max(zh, 1))
            alpha = int(self.trail_opacity * ((i + 1) / len(self._trail)))
            radius = max(2, int(self.cursor_size * 0.3
                                * ((i + 1) / len(self._trail))))
            draw.ellipse(
                [tx - radius, ty - radius, tx + radius, ty + radius],
                fill=(255, 255, 255, alpha),
            )

    def _draw_ripples(self, draw: ImageDraw.ImageDraw,
                      clicks: list[tuple[int, int, float]],
                      current_time: float):
        for cx, cy, click_ts in clicks:
            elapsed = current_time - click_ts
            if elapsed < 0 or elapsed > self.ripple_duration:
                continue
            progress = elapsed / self.ripple_duration
            radius = int(10 + self.ripple_max_radius * progress)
            alpha = int(180 * (1 - progress))
            bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
            draw.ellipse(bbox, outline=(255, 255, 255), width=2)
            draw.ellipse(bbox, outline=None,
                         fill=(255, 255, 255, alpha))

    def _draw_cursor(self, img: Image.Image, cx: int, cy: int):
        """绘制光标图形（支持缩放）"""
        sprite = self._sprites.get(self.cursor_theme)
        if sprite:
            s = self.cursor_size
            if sprite.size != (s, s):
                sprite = sprite.resize((s, s), Image.LANCZOS)
            img.paste(sprite, (cx - s // 8, cy - s // 8), sprite)
        else:
            draw = ImageDraw.Draw(img)
            s = self.cursor_size
            draw.polygon(
                [(cx, cy), (cx + s, cy + s // 2), (cx, cy + s)],
                fill=(255, 255, 255, 220),
            )

    # ── 主入口 ────────────────────────────────────────────

    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        img = frame.copy()
        cx, cy = ctx.cursor_x, ctx.cursor_y
        draw = ImageDraw.Draw(img)

        # 1. 平滑
        if self.enabled["smooth"]:
            cx, cy = self._apply_smooth(cx, cy)

        # 2. Sway
        if self.enabled["sway"]:
            cx, cy = self._apply_sway(cx, cy, ctx.timestamp)

        # 3. 拖尾
        if self.enabled["trail"]:
            self._draw_trail(draw, ctx.raw_cursor_x, ctx.raw_cursor_y, ctx)

        # 4. 点击波纹
        if self.enabled["ripple"]:
            self._draw_ripples(draw, ctx.click_events, ctx.timestamp)

        # 5. 绘制光标
        self._draw_cursor(img, cx, cy)

        return img
