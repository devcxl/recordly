"""文字标注与摄像头画中画 — Compositor 效果插件"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from dataclasses import dataclass
from io import BytesIO
import base64
import math
from core.compositor import Effect, CompositorContext


# ═══════════════════════════════════════════════════════════
# 文字标注
# ═══════════════════════════════════════════════════════════

@dataclass
class Annotation:
    text: str
    x: int
    y: int
    start: float
    end: float
    font_size: int = 24
    color: tuple = (255, 255, 255)
    font_path: str | None = None


class TextAnnotationEffect(Effect):
    """文字标注效果 — 按时段显示"""

    def __init__(self):
        self.annotations: list[Annotation] = []

    def add(self, ann: Annotation):
        self.annotations.append(ann)

    def remove(self, index: int):
        if 0 <= index < len(self.annotations):
            self.annotations.pop(index)

    def clear(self):
        self.annotations.clear()

    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        active = [a for a in self.annotations
                  if a.start <= ctx.timestamp <= a.end]
        if not active:
            return frame

        img = frame.copy()
        draw = ImageDraw.Draw(img)
        for ann in active:
            font = None
            if ann.font_path:
                try:
                    font = ImageFont.truetype(ann.font_path, ann.font_size)
                except Exception:
                    pass
            draw.text((ann.x, ann.y), ann.text, fill=ann.color, font=font)
        return img


# ═══════════════════════════════════════════════════════════
# 摄像头画中画
# ═══════════════════════════════════════════════════════════

class WebcamOverlay(Effect):
    """摄像头画中画效果"""

    def __init__(self, device_id: int = 0):
        self._cap = None
        self._device_id = device_id
        self._x = 50
        self._y = 50
        self._width = 240
        self._height = 160
        self._corner_radius = 8
        self._enabled = False

    def open(self):
        try:
            import cv2
            self._cap = cv2.VideoCapture(self._device_id)
            self._enabled = True
        except ImportError:
            print("[webcam] opencv-python-headless 未安装", flush=True)
            self._enabled = False

    def close(self):
        if self._cap:
            self._cap.release()
            self._cap = None
        self._enabled = False

    def set_position(self, x: int, y: int):
        self._x, self._y = x, y

    def set_size(self, w: int, h: int):
        self._width, self._height = w, h

    @property
    def enabled(self) -> bool:
        return self._enabled and self._cap is not None

    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        if not self.enabled:
            return frame

        import cv2
        ret, cv_frame = self._cap.read()
        if not ret:
            return frame

        # BGR → RGB → PIL
        rgb = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        cam = Image.fromarray(rgb)
        cam = cam.resize((self._width, self._height))

        # 圆角遮罩
        if self._corner_radius > 0:
            mask = Image.new("L", cam.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle(
                [(0, 0), cam.size], self._corner_radius, fill=255)
            if cam.mode != "RGBA":
                cam = cam.convert("RGBA")
            cam.putalpha(mask)

        img = frame.copy()
        img.paste(cam, (self._x, self._y), cam)
        return img


# ═══════════════════════════════════════════════════════════
# 图片标注
# ═══════════════════════════════════════════════════════════

class ImageAnnotationEffect(Effect):
    """图片标注效果 — 在帧上叠加上传的图片"""

    def __init__(self):
        self._regions: list = []  # list[AnnotationRegion]

    def set_regions(self, regions: list):
        self._regions = regions

    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        ts_ms = ctx.timestamp * 1000
        active = [r for r in self._regions
                  if r.type == "image" and r.start_ms <= ts_ms <= r.end_ms]
        if not active:
            return frame

        img = frame.copy()
        w, h = img.size
        for region in active:
            if not region.content:
                continue
            try:
                if region.content.startswith("data:"):
                    header, b64 = region.content.split(",", 1)
                    data = base64.b64decode(b64)
                else:
                    data = base64.b64decode(region.content)
                overlay = Image.open(BytesIO(data)).convert("RGBA")
            except Exception:
                continue

            rw = max(1, int(w * region.width / 100))
            rh = max(1, int(h * region.height / 100))
            overlay = overlay.resize((rw, rh), Image.LANCZOS)
            px = int(w * region.x / 100 - rw / 2)
            py = int(h * region.y / 100 - rh / 2)
            img.paste(overlay, (max(0, px), max(0, py)), overlay)
        return img


# ═══════════════════════════════════════════════════════════
# 图形标注（箭头）
# ═══════════════════════════════════════════════════════════

_ARROW_ANGLES = {
    "right": 0, "up-right": 315, "up": 270, "up-left": 225,
    "left": 180, "down-left": 135, "down": 90, "down-right": 45,
}


class FigureAnnotationEffect(Effect):
    """箭头图形标注效果"""

    def __init__(self):
        self._regions: list = []  # list[AnnotationRegion]

    def set_regions(self, regions: list):
        self._regions = regions

    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        ts_ms = ctx.timestamp * 1000
        active = [r for r in self._regions
                  if r.type == "figure" and r.start_ms <= ts_ms <= r.end_ms]
        if not active:
            return frame

        img = frame.copy()
        draw = ImageDraw.Draw(img)
        w, h = img.size
        for region in active:
            fd = region.figure_data
            if not fd:
                continue
            angle = _ARROW_ANGLES.get(fd.arrow_direction, 0)
            rad = math.radians(angle)
            lw = max(1, min(fd.stroke_width, 20))

            cx = int(w * region.x / 100)
            cy = int(h * region.y / 100)
            size = min(w, h) * region.width / 100 * 0.5
            size = max(20, size)

            pts = self._arrow_points(cx, cy, size, rad, lw)
            color = fd.color
            try:
                color_rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            except Exception:
                color_rgb = (255, 0, 0)
            draw.polygon(pts, fill=color_rgb)
        return img

    @staticmethod
    def _arrow_points(cx, cy, size, rad, lw):
        tip_x = cx + size * math.cos(rad)
        tip_y = cy - size * math.sin(rad)
        perp_rad = rad + math.pi / 2
        base_x = cx
        base_y = cy
        half = lw * 3
        shaft_w = lw * 0.8
        head_len = size * 0.4

        head_base_x = tip_x - head_len * math.cos(rad)
        head_base_y = tip_y + head_len * math.sin(rad)

        p1 = (int(tip_x), int(tip_y))
        p2 = (int(head_base_x + half * math.cos(perp_rad)),
              int(head_base_y - half * math.sin(perp_rad)))
        p3 = (int(base_x + shaft_w * math.cos(perp_rad)),
              int(base_y - shaft_w * math.sin(perp_rad)))
        p4 = (int(base_x - shaft_w * math.cos(perp_rad)),
              int(base_y + shaft_w * math.sin(perp_rad)))
        p5 = (int(head_base_x - half * math.cos(perp_rad)),
              int(head_base_y + half * math.sin(perp_rad)))
        return [p1, p2, p3, p4, p5]


# ═══════════════════════════════════════════════════════════
# 模糊标注
# ═══════════════════════════════════════════════════════════

class BlurAnnotationEffect(Effect):
    """模糊标注效果 — 对帧的指定区域应用高斯模糊"""

    def __init__(self):
        self._regions: list = []

    def set_regions(self, regions: list):
        self._regions = regions

    def apply(self, frame: Image.Image,
              ctx: CompositorContext) -> Image.Image:
        ts_ms = ctx.timestamp * 1000
        active = [r for r in self._regions
                  if r.type == "blur" and r.start_ms <= ts_ms <= r.end_ms]
        if not active:
            return frame

        img = frame.copy()
        w, h = img.size
        for region in active:
            rw = max(2, int(w * region.width / 100))
            rh = max(2, int(h * region.height / 100))
            rx = max(0, int(w * region.x / 100 - rw / 2))
            ry = max(0, int(h * region.y / 100 - rh / 2))
            if rw < 2 or rh < 2:
                continue

            crop = img.crop((rx, ry, rx + rw, ry + rh))
            radius = max(1, region.blur_intensity / 5)
            blurred = crop.filter(ImageFilter.GaussianBlur(radius=radius))

            if region.blur_color and region.blur_color != "transparent":
                try:
                    c = region.blur_color.lstrip('#')
                    overlay_color = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
                    overlay = Image.new("RGBA", (rw, rh), overlay_color + (128,))
                    blurred = Image.alpha_composite(blurred.convert("RGBA"), overlay)
                except Exception:
                    pass

            if blurred.mode == "RGBA":
                img.paste(blurred, (rx, ry), blurred)
            else:
                img.paste(blurred, (rx, ry))
        return img
