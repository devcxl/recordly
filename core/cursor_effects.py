"""光标特效 — 6 种光标效果，作为 Compositor 的 Effect 插件"""

import math
import os
import numpy as np
from PIL import Image, ImageDraw
from core.compositor import Effect, CompositorContext


class CursorEffect(Effect):
    """综合光标效果：平滑/波纹/拖尾/模糊/Sway/样式替换"""

    CURSOR_STYLES = ("dot", "ring", "spotlight", "arrow")

    def __init__(self, cursor_size: int = 32, cursor_theme: str = "dark",
                 cursor_style: str = "dot"):
        self.cursor_size = cursor_size
        self.cursor_theme = cursor_theme
        self.cursor_style = (
            cursor_style if cursor_style in self.CURSOR_STYLES else "dot")
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
        self.ripple_duration = 0.55
        self.ripple_max_radius = 40
        self.sway_amplitude = 4
        self.sway_frequency = 2.0
        self.blur_strength = 4
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
                    cursor_x: int, cursor_y: int,
                    ctx: CompositorContext):
        self._trail.append((cursor_x, cursor_y))
        if len(self._trail) > self.trail_length:
            self._trail.pop(0)
        for i, (tx, ty) in enumerate(self._trail):
            alpha = int(self.trail_opacity * ((i + 1) / len(self._trail)))
            radius = max(1, int(self.cursor_size * 0.12
                                * ((i + 1) / len(self._trail))))
            color = ((255, 255, 255, alpha)
                     if self.cursor_theme == "dark"
                     else (25, 25, 25, alpha))
            draw.ellipse(
                [tx - radius, ty - radius, tx + radius, ty + radius],
                fill=color,
            )

    def _draw_ripples(self, draw: ImageDraw.ImageDraw,
                      clicks: list[tuple[int, int, float]],
                      current_time: float):
        for cx, cy, click_ts in clicks:
            elapsed = current_time - click_ts
            if elapsed < 0 or elapsed > self.ripple_duration:
                continue
            progress = elapsed / self.ripple_duration
            eased = 1 - (1 - progress) ** 3
            alpha = int(210 * (1 - progress) ** 1.5)
            accent = (66, 170, 255)
            outer_radius = round(7 + self.ripple_max_radius * eased)
            inner_radius = round(4 + self.ripple_max_radius * 0.58 * eased)
            width = max(2, round(self.cursor_size / 14))
            draw.ellipse(
                [cx - outer_radius, cy - outer_radius,
                 cx + outer_radius, cy + outer_radius],
                outline=(*accent, alpha), width=width,
            )
            draw.ellipse(
                [cx - inner_radius, cy - inner_radius,
                 cx + inner_radius, cy + inner_radius],
                outline=(*accent, int(alpha * 0.65)),
                width=max(1, width - 1),
            )

    def _draw_cursor(self, img: Image.Image, cx: int, cy: int):
        """绘制当前光标样式。"""
        sprite = (self._sprites.get(self.cursor_theme)
                  if self.cursor_style == "arrow" else None)
        if sprite is not None:
            s = self.cursor_size
            if sprite.size != (s, s):
                sprite = sprite.resize((s, s), Image.LANCZOS)
            img.paste(sprite, (cx - s // 8, cy - s // 8), sprite)
            return

        padding = self.cursor_size + 6
        overlay_size = padding * 2 + 1
        overlay = Image.new(
            "RGBA", (overlay_size, overlay_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        destination = (cx - padding, cy - padding)
        cx = cy = padding
        size = self.cursor_size
        primary = ((255, 255, 255, 255)
                   if self.cursor_theme == "dark"
                   else (24, 24, 24, 255))
        contrast = ((12, 12, 12, 220)
                    if self.cursor_theme == "dark"
                    else (255, 255, 255, 230))
        accent = (66, 170, 255)

        if self.cursor_style == "ring":
            radius = max(5, round(size * 0.32))
            draw.ellipse(
                [cx - radius + 1, cy - radius + 2,
                 cx + radius + 1, cy + radius + 2],
                outline=(0, 0, 0, 100), width=max(3, size // 10),
            )
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                outline=primary, width=max(2, size // 12),
            )
            draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=primary)
        elif self.cursor_style == "spotlight":
            halo = max(9, round(size * 0.58))
            core = max(3, round(size * 0.11))
            draw.ellipse(
                [cx - halo, cy - halo, cx + halo, cy + halo],
                fill=(*accent, 42), outline=(*accent, 115), width=2,
            )
            draw.ellipse(
                [cx - core, cy - core, cx + core, cy + core],
                fill=primary, outline=contrast, width=1,
            )
        elif self.cursor_style == "arrow":
            points = [
                (cx, cy),
                (cx, cy + round(size * 0.78)),
                (cx + round(size * 0.20), cy + round(size * 0.59)),
                (cx + round(size * 0.39), cy + round(size * 0.91)),
                (cx + round(size * 0.53), cy + round(size * 0.82)),
                (cx + round(size * 0.34), cy + round(size * 0.52)),
                (cx + round(size * 0.64), cy + round(size * 0.50)),
            ]
            shadow = [(x + 2, y + 2) for x, y in points]
            draw.polygon(shadow, fill=(0, 0, 0, 120))
            draw.polygon(points, fill=primary, outline=contrast)
        else:
            halo = max(6, round(size * 0.30))
            core = max(3, round(size * 0.13))
            draw.ellipse(
                [cx - halo + 2, cy - halo + 2,
                 cx + halo + 2, cy + halo + 2],
                fill=(0, 0, 0, 75),
            )
            draw.ellipse(
                [cx - halo, cy - halo, cx + halo, cy + halo],
                fill=(*accent, 68), outline=(*accent, 135), width=1,
            )
            draw.ellipse(
                [cx - core, cy - core, cx + core, cy + core],
                fill=primary, outline=contrast, width=1,
            )

        img.alpha_composite(overlay, dest=destination)

    def _record_trail(self, cursor_x: int, cursor_y: int):
        self._trail.append((cursor_x, cursor_y))
        if len(self._trail) > self.trail_length:
            self._trail.pop(0)

    def _draw_local_effects(self, img: Image.Image,
                            clicks: list[tuple[int, int, float]],
                            current_time: float):
        if self.enabled["trail"] and self._trail:
            for i, (tx, ty) in enumerate(self._trail):
                alpha = int(self.trail_opacity * ((i + 1) / len(self._trail)))
                radius = max(1, int(self.cursor_size * 0.12
                                    * ((i + 1) / len(self._trail))))
                patch = Image.new(
                    "RGBA", (radius * 2 + 3, radius * 2 + 3),
                    (0, 0, 0, 0),
                )
                color = ((255, 255, 255, alpha)
                         if self.cursor_theme == "dark"
                         else (25, 25, 25, alpha))
                ImageDraw.Draw(patch).ellipse(
                    [1, 1, radius * 2 + 1, radius * 2 + 1], fill=color)
                img.alpha_composite(patch, dest=(tx - radius - 1,
                                                  ty - radius - 1))

        ripple_padding = self.ripple_max_radius + 10
        for click_x, click_y, click_ts in clicks:
            elapsed = current_time - click_ts
            if elapsed < 0 or elapsed > self.ripple_duration:
                continue
            size = ripple_padding * 2 + 1
            patch = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            self._draw_ripples(
                ImageDraw.Draw(patch),
                [(ripple_padding, ripple_padding, click_ts)],
                current_time,
            )
            img.alpha_composite(
                patch,
                dest=(click_x - ripple_padding, click_y - ripple_padding),
            )

    # ── 主入口 ────────────────────────────────────────────

    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        img = frame.copy()
        cx, cy = ctx.cursor_x, ctx.cursor_y

        # 1. 平滑
        if self.enabled["smooth"]:
            cx, cy = self._apply_smooth(cx, cy)

        # 2. Sway
        if self.enabled["sway"]:
            cx, cy = self._apply_sway(cx, cy, ctx.timestamp)

        # 3. 拖尾
        if self.enabled["trail"]:
            self._record_trail(cx, cy)

        # 4. 拖尾和点击波纹只创建局部图层，避免每帧分配全屏透明图。
        clicks = ctx.click_events if self.enabled["ripple"] else []
        self._draw_local_effects(img, clicks, ctx.timestamp)

        # 5. 绘制光标
        self._draw_cursor(img, cx, cy)

        return img
