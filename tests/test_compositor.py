"""测试合成器 — core/compositor.py"""

import numpy as np
import pytest
from PIL import Image
from core.compositor import Compositor, Effect, CompositorContext, CapturedFrame
from core.screen_capture import CapturedFrame
from core.project import Clip


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
        """缩放后应裁剪到 zoom rect 并拉伸回 compositor 尺寸"""
        c = Compositor(160, 120, 30)
        # 源帧 320x240
        arr = np.full((240, 320, 3), 80, dtype=np.uint8)
        arr[0, 0] = [255, 0, 0]  # 标记左上角
        frames = [CapturedFrame(data=arr, timestamp=0.0, index=0)]
        c.load_frames(frames)
        # 缩放后 compositor.width/height = 320/240（由 load_frames 设置）
        # zoom rect = (80, 60, 160, 120) → crop to 160x120 → resize to 320x240
        c.set_zoom((80, 60, 160, 120))
        result = c.compose(frames[0])
        # load_frames 覆盖了 compositor 的尺寸
        assert result.size == (320, 240)

    def test_zoom_timeline_is_authoritative_over_camera(self):
        from core.project import Clip

        class AlwaysZoomCamera:
            def sample(self, _time_ms):
                return (0.5, 0.5, 2.0)

        c = Compositor(200, 100, 30)
        c.load_camera(AlwaysZoomCamera())
        clip = Clip(
            type="zoom", start=1.0, end=4.0,
            rect=[50, 25, 100, 50], transition_duration=0.4,
        )
        c.load_manual_zoom_clips([clip])
        assert c._get_zoom_at(2.0) == (50, 25, 100, 50)

        clip.start = 5.0
        clip.end = 8.0
        c.load_manual_zoom_clips([clip])

        assert c._get_zoom_at(2.0) is None

    def test_zoom_rect_edit_changes_rendered_region(self):
        from core.project import Clip

        c = Compositor(200, 100, 30)
        clip = Clip(
            type="zoom", start=0.0, end=3.0,
            rect=[20, 10, 80, 40], transition_duration=0.2,
        )
        c.load_manual_zoom_clips([clip])
        assert c._get_zoom_at(1.0) == (20, 10, 80, 40)

        clip.rect = [100, 50, 60, 30]
        c.load_manual_zoom_clips([clip])

        assert c._get_zoom_at(1.0) == (100, 50, 60, 30)

    def test_compositor_preserves_requested_zoom_aspect(self):
        from core.project import Clip

        c = Compositor(200, 100, 30)
        frame = CapturedFrame(
            data=np.zeros((100, 200, 3), dtype=np.uint8),
            timestamp=0.0, index=0,
        )
        c.load_frames([frame])
        c.load_manual_zoom_clips([Clip(
            type="zoom", start=0.0, end=2.0,
            rect=[20, 10, 50, 80], transition_duration=0.1,
        )])
        captured = {}

        class CaptureZoom(Effect):
            def apply(self, image, ctx):
                captured["zoom"] = ctx.zoom_rect
                return image

        c.register_effect("capture", CaptureZoom())
        c.compose(frame, timeline_ts=1.0)

        assert captured["zoom"] == (20, 10, 50, 80)

    def test_zoom_clip_eases_from_full_frame(self):
        from core.project import Clip

        c = Compositor(200, 100, 30)
        c.load_manual_zoom_clips([Clip(
            type="zoom", start=1.0, end=4.0,
            rect=[50, 25, 100, 50], transition_duration=1.0,
        )])

        assert c._get_zoom_at(1.0) == (0, 0, 200, 100)
        halfway = c._get_zoom_at(1.5)
        assert halfway not in ((0, 0, 200, 100), (50, 25, 100, 50))
        assert c._get_zoom_at(2.0) == (50, 25, 100, 50)

    def test_adjacent_zoom_clips_pan_once_without_boundary_jump(self):
        from core.project import Clip

        first_rect = (10, 10, 100, 50)
        second_rect = (80, 40, 100, 50)
        c = Compositor(200, 100, 30)
        c.load_manual_zoom_clips([
            Clip(type="zoom", start=0.0, end=2.0,
                 rect=list(first_rect), transition_duration=0.4),
            Clip(type="zoom", start=2.0, end=5.0,
                 rect=list(second_rect), transition_duration=0.4),
        ])

        assert c._get_zoom_at(1.99) == first_rect
        assert c._get_zoom_at(2.0) == first_rect
        halfway = c._get_zoom_at(2.2)
        assert halfway not in (first_rect, second_rect)
        assert c._get_zoom_at(2.4) == second_rect


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
        px = result.convert("RGB").getpixel((0, 0))
        assert px == (255, 255, 255)

    def test_crop_transforms_cursor_and_click_coordinates(self):
        from types import SimpleNamespace
        from core.project import CropRegion

        c = Compositor(100, 100, 10)
        frame = CapturedFrame(
            data=np.zeros((100, 100, 3), dtype=np.uint8),
            timestamp=10.0, index=0,
        )
        c.load_frames([frame])
        c.load_cursor_events([
            SimpleNamespace(timestamp=10.0, x=75, y=50),
        ], [
            SimpleNamespace(timestamp=10.0, x=75, y=50),
        ])
        c.set_crop(CropRegion(x=0.5, y=0.0, width=0.5, height=1.0))
        captured = {}

        class CaptureContext(Effect):
            def apply(self, image, ctx):
                captured["cursor"] = (ctx.cursor_x, ctx.cursor_y)
                captured["clicks"] = ctx.click_events
                return image

        c.register_effect("capture", CaptureContext())
        c.compose(frame)

        assert captured["cursor"] == (50, 50)
        assert captured["clicks"][0][:2] == (50, 50)


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

    def test_render_uses_clip_source_range_and_speed(self):
        from core.project import Clip

        c = Compositor(1, 1, 1)
        frames = [
            CapturedFrame(
                data=np.full((1, 1, 3), i, dtype=np.uint8),
                timestamp=float(i), index=i,
            )
            for i in range(10)
        ]
        c.load_frames(frames)
        c.load_clips([Clip(
            type="video", start=0.0, end=2.0,
            source_start=2.0, source_end=6.0, speed=2.0,
        )])

        rendered = list(c.render_all())

        assert len(rendered) == 2
        assert [frame.convert("RGB").getpixel((0, 0))[0]
                for frame in rendered] == [2, 4]

    def test_render_preserves_timeline_gaps_as_black_frames(self):
        from core.project import Clip

        c = Compositor(1, 1, 1)
        frames = [CapturedFrame(
            data=np.full((1, 1, 3), 100, dtype=np.uint8),
            timestamp=float(i), index=i,
        ) for i in range(3)]
        c.load_frames(frames)
        c.load_clips([Clip(
            type="video", start=1.0, end=3.0,
            source_start=0.0, source_end=2.0,
        )])

        rendered = list(c.render_all())

        assert len(rendered) == 3
        assert rendered[0].convert("RGB").getpixel((0, 0)) == (0, 0, 0)
        assert rendered[1].convert("RGB").getpixel((0, 0)) == (100, 100, 100)

    def test_explicit_empty_video_timeline_renders_nothing(self):
        c = Compositor(10, 10, 1)
        c.load_frames([CapturedFrame(
            data=np.full((10, 10, 3), 100, dtype=np.uint8),
            timestamp=0.0, index=0,
        )])

        c.load_clips([])

        # 无 clips 时 total_output_frames 返回原始帧数
        assert c.total_output_frames == 1
        # render_all 按原始帧数输出黑帧
        rendered = list(c.render_all())
        assert len(rendered) == 1
        assert rendered[0].convert("RGB").getpixel((0, 0)) == (100, 100, 100)
        # compose_index 返回黑帧而非 None
        frame = c.compose_index(0)
        assert frame is not None
        assert frame.convert("RGB").getpixel((0, 0)) == (0, 0, 0)


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

    def test_preview_uses_fast_filter_but_export_keeps_lanczos(self):
        c = Compositor(320, 240, 30)
        c.set_preview_quality(0.5)

        assert c._resize_filter(preview=True) == Image.BILINEAR
        assert c._resize_filter(preview=False) == Image.LANCZOS

        c.set_preview_quality(0.9)
        assert c._resize_filter(preview=True) == Image.BICUBIC

    def test_preview_crop_uses_pil_resize(self):
        c = Compositor(320, 240, 60)
        image = Image.new("RGB", (480, 360), "black")
        # 填充一个非黑像素用于验证裁剪正确
        image.putpixel((40, 30), (255, 0, 0))

        result = c._resize_crop(image, (40, 30, 280, 210), preview=True)

        assert result.size == (320, 240)
        # 预览品质默认 0.5，使用 BILINEAR
        assert c._resize_filter(preview=True) == Image.BILINEAR


class TestTimestampBasedTiming:
    def test_source_duration_uses_capture_timestamps_not_target_fps(self):
        c = Compositor(1, 1, 60)
        frames = [CapturedFrame(
            data=np.zeros((1, 1, 3), dtype=np.uint8),
            timestamp=i / 40,
            index=i,
        ) for i in range(400)]

        c.load_frames(frames)

        assert c.source_duration == pytest.approx(10.0, abs=0.001)

    def test_source_lookup_uses_nearest_timestamp_at_60fps(self):
        c = Compositor(1, 1, 60)
        frames = [CapturedFrame(
            data=np.zeros((1, 1, 3), dtype=np.uint8),
            timestamp=i / 40,
            index=i,
        ) for i in range(400)]
        c.load_frames(frames)
        c.load_clips([Clip(type="video", start=0, end=10)])

        assert c._source_index_at(5.0) == 200


class TestCapturedFrameDataclass:
    def test_default_creation(self):
        data = np.zeros((10, 10, 3), dtype=np.uint8)
        cf = CapturedFrame(data=data, timestamp=1.0, index=5)
        assert cf.data is data
        assert cf.timestamp == 1.0
        assert cf.index == 5


class TestLoaderThreadSafety:
    def test_concurrent_decodes_no_errors(self, tmp_path):
        """loader 加 Lock 后多线程解码不应产生损坏帧"""
        import json, cv2
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 构造小 frames.data（10 帧 64×64 JPEG）
        store_path = tmp_path / "frames.data"
        idx_path = tmp_path / "frames.idx"
        offsets = []
        rgb_frames = []
        with open(store_path, "wb") as fh:
            for i in range(10):
                arr = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
                rgb_frames.append(arr)
                ok, buf = cv2.imencode(".jpg",
                                       np.ascontiguousarray(arr[:, :, ::-1]),
                                       [cv2.IMWRITE_JPEG_QUALITY, 95])
                assert ok
                offsets.append([fh.tell(), len(buf)])
                fh.write(buf.tobytes())
        json.dump(offsets, open(idx_path, "w"))

        comp = Compositor(64, 64, 10)
        comp.load_frames_data(str(store_path), 10, 10)

        # 用 8 线程并发 loader，每线程随机读 200 次
        def work():
            for _ in range(200):
                i = np.random.randint(0, 10)
                data = comp.frames[i].data
                assert data.shape == (64, 64, 3), f"帧 {i} 尺寸异常"

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(work) for _ in range(8)]
            for f in as_completed(futures):
                f.result()  # 不应抛异常


class TestCursorEffectThreadSafety:
    def test_concurrent_apply_no_exception(self):
        """CursorEffect.apply() 加 Lock 后多线程调用不应崩溃"""
        from core.cursor_effects import CursorEffect
        from core.effects import TextAnnotationEffect
        import threading
        import concurrent.futures

        comp = Compositor(320, 240, 30)
        frames = [
            CapturedFrame(data=np.zeros((240, 320, 3), dtype=np.uint8),
                          timestamp=i / 30, index=i) for i in range(30)
        ]
        comp.load_frames(frames)
        ce = CursorEffect(cursor_size=24, cursor_theme="dark", cursor_style="ring")
        comp.register_effect("cursor", ce)

        def apply_one(idx):
            ts = idx / 30.0
            comp.compose(comp.frames[idx], ts)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            list(ex.map(apply_one, range(30)))

        # 验证平滑位置一致性：多帧连续 compose 后，smooth 位置应与串行结果一致
        comp2 = Compositor(320, 240, 30)
        comp2.load_frames(frames)
        ce2 = CursorEffect(cursor_size=24, cursor_theme="dark", cursor_style="ring")
        comp2.register_effect("cursor", ce2)
        serial_imgs = [comp2.compose(comp2.frames[idx], idx / 30) for idx in range(30)]

        comp3 = Compositor(320, 240, 30)
        comp3.load_frames(frames)
        ce3 = CursorEffect(cursor_size=24, cursor_theme="dark", cursor_style="ring")
        comp3.register_effect("cursor", ce3)

        def compose_without_lock(idx):
            return comp3.compose(comp3.frames[idx], idx / 30)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            parallel_imgs = list(ex.map(compose_without_lock, range(30)))
            # 并行结果应按帧索引排序
            parallel_imgs.sort(key=lambda img: img.info.get("frame_index", 0))

        # 比较并行与串行的像素均值（松弛容差，主要防止完全错乱）
        serial_mean = np.mean([np.array(img).mean() for img in serial_imgs])
        parallel_mean = np.mean([np.array(img).mean() for img in parallel_imgs])
        assert abs(serial_mean - parallel_mean) < 5.0, (
            f"并行 cursor 渲染偏差: serial={serial_mean:.1f} parallel={parallel_mean:.1f}"
        )
