"""测试缩放系统 — core/camera.py（恢复为 CameraSynthesizer）"""
from core.camera import CameraSynthesizer, build_camera, minimum_jerk


class TestMinimumJerk:
    def test_range(self):
        assert minimum_jerk(0) == 0
        assert minimum_jerk(1) == 1
        assert minimum_jerk(-1) == 0
        assert minimum_jerk(2) == 1

    def test_mid(self):
        v = minimum_jerk(0.5)
        assert 0 < v < 1

    def test_monotonic(self):
        prev = -1
        for x in range(0, 101):
            v = minimum_jerk(x / 100)
            assert v >= prev
            prev = v


class TestCameraSynthesizer:
    def test_empty(self):
        cam = CameraSynthesizer([], [], 1920, 1080, 30, 10)
        s = cam.sample(5000)
        assert s[2] == CameraSynthesizer.ZOOM_SCALE

    def test_segments_empty(self):
        cam = CameraSynthesizer([], [], 1920, 1080, 30, 0)
        assert cam.zoomed_segments == []

    def test_segments_default(self):
        cam = CameraSynthesizer([], [], 1920, 1080, 30, 10)
        assert cam.zoomed_segments == []

    def test_sampling_is_independent_of_seek_order(self):
        events = [
            (0.0, 100, 100),
            (1.0, 100, 100),
            (1.2, 1000, 700),
            (2.0, 1000, 700),
            (4.0, 400, 300),
        ]
        sequential = CameraSynthesizer([], events, 1920, 1080, 30, 5)
        state_from_playback = None
        for frame in range(151):
            state_from_playback = sequential.sample(frame / 30 * 1000)

        direct = CameraSynthesizer([], events, 1920, 1080, 30, 5)
        state_from_seek = direct.sample(5000)

        assert state_from_seek == state_from_playback

    def test_repeated_sample_is_stable_after_backward_seek(self):
        events = [(0.0, 100, 100), (1.0, 900, 600), (3.0, 300, 200)]
        cam = CameraSynthesizer([], events, 1920, 1080, 30, 4)

        first = cam.sample(2500)
        cam.sample(500)
        second = cam.sample(2500)

        assert second == first


class TestBuildCamera:
    def test_no_offset_default(self):
        cam = build_camera([], 30, 1920, 1080, 10)
        assert isinstance(cam, CameraSynthesizer)

    def test_monitor_offset(self):
        from core.pointer_tracker import CursorEvent
        events = [CursorEvent(timestamp=0, x=1960, y=500)]
        cam = build_camera([], 30, 1920, 1080, 10,
                          cursor_events=events, base_time=0,
                          monitor_left=1920, monitor_top=0)
        # x should be 1960-1920=40 relative to frame
        assert isinstance(cam, CameraSynthesizer)
        assert len(cam.events) == 1
        assert cam.events[0][1] == 40
        assert cam.events[0][2] == 500


class TestAutomaticZoomClips:
    def test_no_clicks_produce_no_zoom_clips(self):
        cam = CameraSynthesizer([], [(0.0, 100, 100)], 1920, 1080, 30, 10)

        assert cam.build_zoom_clips() == []

    def test_nearby_clicks_merge_into_one_stable_clip(self):
        clicks = [(1.0, 400, 300), (2.0, 430, 320)]
        cam = CameraSynthesizer(clicks, [], 1920, 1080, 30, 10)

        clips = cam.build_zoom_clips()

        assert len(clips) == 1
        assert clips[0].start == 0.8
        assert clips[0].end == 4.5
        assert clips[0].rect is not None

    def test_far_clicks_in_same_activity_chain_pan_without_full_gap(self):
        clicks = [(1.0, 300, 250), (3.0, 1500, 750)]
        cam = CameraSynthesizer(clicks, [], 1920, 1080, 30, 10)

        clips = cam.build_zoom_clips()

        assert len(clips) == 2
        assert clips[0].end == clips[1].start
        assert clips[0].rect != clips[1].rect

    def test_large_fast_cursor_travel_creates_full_frame_gap(self):
        clicks = [(1.0, 200, 150), (3.0, 1700, 900)]
        events = [
            (1.0, 200, 150),
            (1.5, 200, 150),
            (2.0, 950, 525),
            (2.5, 1700, 900),
            (3.0, 1700, 900),
        ]
        cam = CameraSynthesizer(clicks, events, 1920, 1080, 30, 6)

        clips = cam.build_zoom_clips()

        assert clips[0].end <= 1.5
        assert clips[1].start >= 2.5
        assert all(not (clip.start < 2.0 < clip.end) for clip in clips)

    def test_long_click_gap_returns_to_full_frame(self):
        clicks = [(1.0, 300, 250), (7.0, 1500, 750)]
        cam = CameraSynthesizer(clicks, [], 1920, 1080, 30, 10)

        clips = cam.build_zoom_clips()

        assert len(clips) == 2
        assert clips[1].start - clips[0].end > 1.0

    def test_generated_rect_keeps_video_aspect_ratio(self):
        cam = CameraSynthesizer([(1.0, 20, 20)], [], 1920, 1080, 30, 5)

        rect = cam.build_zoom_clips()[0].rect

        assert rect[2] / rect[3] == 1920 / 1080
        assert rect[0] >= 0
        assert rect[1] >= 0

    def test_auto_zoom_uses_longer_transition_for_smooth_motion(self):
        clicks = [(1.0, 300, 250), (3.0, 1500, 750)]
        cam = CameraSynthesizer(clicks, [], 1920, 1080, 60, 8)

        first, second = cam.build_zoom_clips()

        assert first.transition_duration >= 0.55
        assert second.transition_duration > first.transition_duration
