"""测试文字标注 — core/effects.py"""

from PIL import Image
from core.compositor import CompositorContext
from core.effects import TextAnnotationEffect, Annotation


class TestTextAnnotationEffect:
    def _make_context(self, ts=0.0):
        return CompositorContext(
            frame=Image.new("RGBA", (320, 240), (0, 0, 0, 255)),
            cursor_x=0, cursor_y=0, cursor_state="idle",
            click_events=[], frame_index=0, timestamp=ts,
            zoom_rect=None, width=320, height=240,
        )

    def test_initial_empty(self):
        effect = TextAnnotationEffect()
        assert effect.annotations == []

    def test_add_annotation(self):
        effect = TextAnnotationEffect()
        ann = Annotation(text="Hello", x=10, y=10, start=0, end=5)
        effect.add(ann)
        assert len(effect.annotations) == 1

    def test_annotation_applied_in_time_range(self):
        effect = TextAnnotationEffect()
        ann = Annotation(text="Hello", x=50, y=100, start=0, end=5)
        effect.add(ann)

        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        ctx = self._make_context(ts=2.0)
        result = effect.apply(bg, ctx)

        # 文字应产生变化：结果图不全部等于背景
        assert result.tobytes() != bg.tobytes(), "标注应修改帧内容"

        # 标注位置的某个像素应有文字颜色
        found = False
        for x in range(45, 100):
            for y in range(95, 130):
                px = result.getpixel((x, y))
                if px[:3] == (255, 255, 255):
                    found = True
                    break
            if found:
                break
        assert found, "标注区域应渲染白色文字"

    def test_annotation_not_applied_outside_range(self):
        """超出时间范围应返回原始帧"""
        effect = TextAnnotationEffect()
        ann = Annotation(text="Hello", x=10, y=10, start=0, end=5)
        effect.add(ann)

        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        ctx = self._make_context(ts=10.0)
        result = effect.apply(bg, ctx)

        # 原始帧是全黑 (0,0,0,255)
        px = result.getpixel((10, 10))
        assert px == (0, 0, 0, 255)

    def test_remove_annotation(self):
        effect = TextAnnotationEffect()
        ann = Annotation(text="A", x=0, y=0, start=0, end=1)
        effect.add(ann)
        effect.remove(0)
        assert effect.annotations == []

    def test_clear_all(self):
        effect = TextAnnotationEffect()
        effect.add(Annotation(text="A", x=0, y=0, start=0, end=1))
        effect.add(Annotation(text="B", x=0, y=0, start=0, end=1))
        effect.clear()
        assert effect.annotations == []

    def test_no_annotation_returns_original(self):
        effect = TextAnnotationEffect()
        bg = Image.new("RGBA", (320, 240), (0, 0, 0, 255))
        ctx = self._make_context(ts=1.0)
        result = effect.apply(bg, ctx)
        assert result.tobytes() == bg.tobytes()


class TestAnnotationDefaults:
    def test_default_values(self):
        ann = Annotation(text="test", x=0, y=0, start=0, end=1)
        assert ann.font_size == 24
        assert ann.color == (255, 255, 255)
        assert ann.font_path is None

    def test_custom_values(self):
        ann = Annotation(text="custom", x=50, y=100,
                         start=2, end=8, font_size=48,
                         color=(0, 255, 0))
        assert ann.font_size == 48
        assert ann.color == (0, 255, 0)
