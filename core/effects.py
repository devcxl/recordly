"""文字标注与摄像头画中画 — Compositor 效果插件"""

from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass
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
