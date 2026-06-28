"""视频帧样式效果 — Compositor 效果插件"""

import os
from PIL import Image, ImageDraw, ImageFilter
from dataclasses import dataclass
from core.compositor import Effect, CompositorContext


@dataclass
class FrameStyle:
    """帧样式配置"""
    background: str = "solid"                 # solid / gradient / wallpaper
    bg_color: tuple = (26, 26, 26)           # 纯色背景色
    bg_gradient: tuple = None                # (c1, c2, dir) 或 None
    bg_wallpaper: str | None = None          # 图片路径
    padding: int = 40
    corner_radius: int = 16
    shadow: bool = True
    shadow_offset: int = 8
    shadow_blur: int = 16
    shadow_opacity: int = 100


class FrameStyleEffect(Effect):
    """帧样式：背景填充 / 间距 / 圆角 / 阴影"""

    def __init__(self, style: FrameStyle | None = None):
        self.style = style or FrameStyle()
        self._wallpaper_cache: Image.Image | None = None

    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        w, h = frame.size
        p = self.style.padding
        soff = self.style.shadow_offset
        sw = (soff if self.style.shadow else 0)

        # 最终画布尺寸
        canvas_w = w + 2 * p + sw
        canvas_h = h + 2 * p + sw

        # 创建背景
        canvas = self._create_background(canvas_w, canvas_h)

        # 圆角遮罩
        if self.style.corner_radius > 0:
            mask = Image.new("L", (w, h), 0)
            md = ImageDraw.Draw(mask)
            md.rounded_rectangle(
                [(0, 0), (w - 1, h - 1)],
                self.style.corner_radius, fill=255,
            )
            f = frame.convert("RGBA")
            f.putalpha(mask)
        else:
            f = frame.convert("RGBA")

        # 阴影
        if self.style.shadow:
            shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sm = Image.new("L", (w, h), 0)
            sd = ImageDraw.Draw(sm)
            sd.rounded_rectangle(
                [(0, 0), (w - 1, h - 1)],
                self.style.corner_radius, fill=self.style.shadow_opacity,
            )
            shadow.putalpha(sm)
            shadow = shadow.filter(
                ImageFilter.GaussianBlur(self.style.shadow_blur))
            canvas.paste(shadow, (p + soff, p + soff), shadow)

        # 粘贴视频帧
        canvas.paste(f, (p, p), f)

        return canvas

    def _create_background(self, w: int, h: int) -> Image.Image:
        if self.style.background == "solid":
            return Image.new("RGB", (w, h), self.style.bg_color)
        elif self.style.background == "gradient":
            return self._make_gradient(w, h)
        elif self.style.background == "wallpaper":
            return self._make_wallpaper(w, h)
        else:
            return Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def _make_gradient(self, w: int, h: int) -> Image.Image:
        params = self.style.bg_gradient
        if params:
            from ._gradient import create_gradient
            return create_gradient(w, h, *params)
        # 默认渐变: 深紫→深蓝
        img = Image.new("RGB", (w, h))
        c1, c2 = (30, 30, 50), (20, 20, 60)
        for y in range(h):
            ratio = y / h
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            for x in range(w):
                img.putpixel((x, y), (r, g, b))
        return img

    def _make_wallpaper(self, w: int, h: int) -> Image.Image:
        if self._wallpaper_cache and self._wallpaper_cache.size == (w, h):
            return self._wallpaper_cache
        if self.style.bg_wallpaper and os.path.exists(self.style.bg_wallpaper):
            wp = Image.open(self.style.bg_wallpaper).convert("RGB")
            # 高斯模糊
            try:
                wp = wp.filter(ImageFilter.GaussianBlur(20))
            except Exception:
                pass
            wp = wp.resize((w, h), Image.LANCZOS)
            self._wallpaper_cache = wp
            return wp
        return Image.new("RGB", (w, h), (40, 40, 40))
