"""文字标注 — Compositor 效果插件（当前未接入 UI）"""

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from core.compositor import Effect, CompositorContext


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
