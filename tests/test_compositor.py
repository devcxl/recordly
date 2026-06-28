"""测试合成器 — core/compositor.py"""

import numpy as np
from PIL import Image
from core.compositor import Compositor, Effect, CompositorContext, CapturedFrame
from core.screen_capture import CapturedFrame


class TestCompositorInit:
    def test_default_dimensions(self):
        c = Compositor(1920, 1080, 30)
        assert c.width == 1920
        assert c.height == 1080
        assert c.fps == 30


class TestCompositorLoadFrames:
    def test_load_frames_sets_dimensions(self):
        c = Compositor(320, 240, 30)
        frames = [
            CapturedFrame(data=np.zeros((240, 320, 3), dtype=np.uint8),
                          timestamp=0.0, index=0),
            CapturedFrame(data=np.zeros((240, 320, 3), dtype=np.uint8),
                          timestamp=0.033, index=1),
        ]
        c.load_frames(frames)
        assert c.width == 320
        assert c.height == 240
        assert len(c._frames) == 2

    def test_load_empty_frames(self):
        c = Compositor(640, 480, 30)
        c.load_frames([])
        assert c._frames == []


class TestCompositorCompose:
    def test_compose_returns_pil_image(self):
        c = Compositor(320, 240, 30)
        frames = [CapturedFrame(
            data=np.full((240, 320, 3), 80, dtype=np.uint8),
            timestamp=0.0, index=0,
        )]
        c.load_frames(frames)
        result = c.compose(frames[0])
        assert isinstance(result, Image.Image)
        assert result.size == (320, 240)

    def test_compose_keeps_rgb_content(self):
        c = Compositor(320, 240, 30)
        r, g, b = 100, 150, 200
        arr = np.zeros((240, 320, 3), dtype=np.uint8)
        arr[:, :, 0] = r
        arr[:, :, 1] = g
        arr[:, :, 2] = b
        frames = [CapturedFrame(data=arr, timestamp=0.0, index=0)]
        c.load_frames(frames)
        result = c.compose(frames[0])
        px = result.convert("RGB").getpixel((0, 0))
        assert px == (r, g, b)


class TestCompositorZoom:
    def test_zoom_rect_applied(self):
        c = Compositor(160, 120, 30)
        arr = np.full((240, 320, 3), 80, dtype=np.uint8)
        # 在左上角画一个红点
        arr[0, 0] = [255, 0, 0]
        frames = [CapturedFrame(data=arr, timestamp=0.0, index=0)]
        c.load_frames(frames)
        # 缩放：取中心区域，放大到 160x120
        c.set_zoom((80, 60, 160, 120))
        result = c.compose(frames[0])
        assert result.size == (160, 120)


class TestCompositorEffects:
    def test_register_effect(self):
        c = Compositor(320, 240, 30)

        class DummyEffect(Effect):
            def apply(self, frame, ctx):
                return frame

        effect = DummyEffect()
        c.register_effect("dummy", effect)
        assert "dummy" in c._effects

    def test_unregister_effect(self):
        c = Compositor(320, 240, 30)

        class DummyEffect(Effect):
            def apply(self, frame, ctx):
                return frame

        c.register_effect("dummy", DummyEffect())
        c.unregister_effect("dummy")
        assert "dummy" not in c._effects

    def test_effect_actually_applied(self):
        c = Compositor(100, 100, 30)
        arr = np.zeros((100, 100, 3), dtype=np.uint8)
        frames = [CapturedFrame(data=arr, timestamp=0.0, index=0)]
        c.load_frames(frames)

        class InvertEffect(Effect):
            def apply(self, frame, ctx):
                from PIL import ImageOps
                return ImageOps.invert(frame.convert("RGB")).convert("RGBA")

        c.register_effect("invert", InvertEffect())
        result = c.compose(frames[0])
        # 原色(0,0,0) 反转为 (255,255,255)
        px = result.convert("RGB").getpixel((0, 0))
        assert px == (255, 255, 255)


class TestCompositorRenderAll:
    def test_render_all_yields_frames(self):
        c = Compositor(100, 100, 30)
        frames = [
            CapturedFrame(data=np.zeros((100, 100, 3), dtype=np.uint8),
                          timestamp=i * 0.033, index=i)
            for i in range(5)
        ]
        c.load_frames(frames)
        results = list(c.render_all())
        assert len(results) == 5
        assert all(isinstance(f, Image.Image) for f in results)

    def test_render_all_range(self):
        c = Compositor(100, 100, 30)
        frames = [
            CapturedFrame(data=np.zeros((100, 100, 3), dtype=np.uint8),
                          timestamp=i * 0.033, index=i)
            for i in range(10)
        ]
        c.load_frames(frames)
        results = list(c.render_all(start=2, end=7))
        assert len(results) == 5


class TestCompositorPreviewQuality:
    def test_set_get_quality(self):
        c = Compositor(320, 240, 30)
        c.set_preview_quality(0.3)
        assert c.get_preview_quality() == 0.3

    def test_quality_clamped(self):
        c = Compositor(320, 240, 30)
        c.set_preview_quality(0.0)
        assert c.get_preview_quality() == 0.1
        c.set_preview_quality(2.0)
        assert c.get_preview_quality() == 1.0


class TestCapturedFrameDataclass:
    def test_default_creation(self):
        data = np.zeros((10, 10, 3), dtype=np.uint8)
        cf = CapturedFrame(data=data, timestamp=1.0, index=5)
        assert cf.data is data
        assert cf.timestamp == 1.0
        assert cf.index == 5
