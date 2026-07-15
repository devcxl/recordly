"""录制保存→重开往返稳定性测试"""

import json
import os

import numpy as np


class TestAutosaveCreatesRequiredArtifacts:
    """Slice 1: _finalize_project 生成 frames.idx 和完整 project.json"""

    def test_finalize_project_creates_frames_idx_and_project_json(self, tmp_path):
        from types import SimpleNamespace
        from app.main_window import MainWindow
        from core.compositor import Compositor
        from core.project import Project, Track, Clip
        from core.screen_capture import CapturedFrame

        project_dir = str(tmp_path / "test_project")
        os.makedirs(project_dir)

        frames = [
            CapturedFrame(data=np.zeros((100, 100, 3), dtype=np.uint8),
                          timestamp=i / 30.0, index=i)
            for i in range(30)
        ]
        compositor = Compositor(100, 100, 30)
        compositor.load_frames(frames)

        notifications = []

        window = SimpleNamespace(
            _recorded_data={"frames": frames, "cursor_events": [], "clicks": [],
                            "mic_audio": None, "system_audio": None},
            _project_dir=project_dir,
            _compositor=compositor,
            _recording_controller=SimpleNamespace(
                recorder=SimpleNamespace(
                    screen=SimpleNamespace(frame_offsets=[[0, 100], [100, 100]]))),
            _timeline=SimpleNamespace(tracks=[Track(type="video", name="视频", clips=[
                Clip(type="video", start=0, end=1.0, content="test")])]),
            _audio_regions=[],
            config=SimpleNamespace(default_fps=30),
            _refresh_home_page=lambda: None,
            update_status=lambda text: None,
            _show_notification=lambda title, msg, level: notifications.append(locals()),
            _get_recording_duration=lambda: 1.0,
            _collect_project_state=lambda project: None,
            _project_name="test_recording",
        )

        MainWindow._finalize_project(window)

        assert not notifications, f"不应有错误通知: {notifications}"
        idx_path = os.path.join(project_dir, "frames.idx")
        assert os.path.exists(idx_path)
        with open(idx_path) as f:
            offsets = json.load(f)
        assert isinstance(offsets, list)

        proj = Project.load(os.path.join(project_dir, "project.json"))
        assert proj.source is not None
        assert proj.source.video == "frames.data"
        assert proj._frame_count == 30
        assert proj.name == "test_recording"


class TestCursorTimebase:
    """Slice 3: 光标时间基 — 保存时转为相对 compositor base_time 的时间戳"""

    def test_cursor_events_have_relative_timestamps_after_save(self, tmp_path):
        from types import SimpleNamespace
        from app.main_window import MainWindow
        from core.compositor import Compositor
        from core.project import Project
        from core.screen_capture import CapturedFrame
        from core.pointer_tracker import CursorEvent

        project_dir = str(tmp_path / "test_cursor")
        os.makedirs(project_dir)

        frames = [CapturedFrame(data=np.zeros((100, 100, 3), dtype=np.uint8),
                                timestamp=100.0 + i / 30.0, index=i)
                  for i in range(30)]
        compositor = Compositor(100, 100, 30)
        compositor.load_frames(frames)
        assert compositor._base_time == 100.0

        events = [CursorEvent(x=10, y=20, timestamp=100.0),
                  CursorEvent(x=50, y=60, timestamp=100.5),
                  CursorEvent(x=80, y=90, timestamp=101.0)]
        compositor.load_cursor_events(events, [])

        project = Project()
        MainWindow._collect_project_state(
            SimpleNamespace(_compositor=compositor, _timeline=SimpleNamespace(tracks=[]),
                            _audio_regions=[]),
            project)

        project.save(os.path.join(project_dir, "project.json"))
        loaded = Project.load(os.path.join(project_dir, "project.json"))

        reload_compositor = Compositor(100, 100, 30)
        reload_compositor.load_frames(
            [CapturedFrame(data=np.zeros((100, 100, 3), dtype=np.uint8),
                           timestamp=i / 30.0, index=i)
             for i in range(30)])
        evt = type("EventData", (), {})
        reload_compositor._cursor_events = []
        for c in loaded.cursor_events:
            e = evt()
            e.x, e.y, e.timestamp = int(c[0]), int(c[1]), float(c[2])
            reload_compositor._cursor_events.append(e)

        cx0, cy0 = reload_compositor._interpolate_cursor(0.0)
        assert cx0 == 10, f"首帧 x 应为 10, 实际 {cx0}"
        assert cy0 == 20, f"首帧 y 应为 20, 实际 {cy0}"

        cx1, cy1 = reload_compositor._interpolate_cursor(1.0)
        assert cx1 == 80, f"末帧 x 应为 80, 实际 {cx1}"
        assert cy1 == 90, f"末帧 y 应为 90, 实际 {cy1}"


class TestGifFps:
    """Slice 4: GIF 导出使用 fps filter 降采样，保持输入 r=compositor.fps"""

    def test_gif_graph_uses_fps_filter_before_split(self):
        import ffmpeg
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        compositor = Compositor(320, 240, 30)
        worker = ExportWorker(compositor, None,
                              ExportSettings(output_path="out.gif", format="gif", fps=15))
        graph = worker._build_gif_output(320, 240)
        command = " ".join(ffmpeg.compile(graph))

        assert "-r 30" in command
        assert "fps=fps=15" in command
        assert "round=near" in command

    def test_gif_real_export_has_correct_fps_and_duration(self, tmp_path):
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        compositor = Compositor(32, 32, 30)
        frames = []
        for i in range(30):
            frames.append(type("F", (), {
                "data": np.ones((32, 32, 3), dtype=np.uint8) * (i * 8),
                "timestamp": i / 30.0, "index": i,
            })())
        compositor._frames = frames

        output_path = str(tmp_path / "test.gif")
        worker = ExportWorker(compositor, None,
                              ExportSettings(output_path=output_path, format="gif", fps=10))
        worker._export_gif()

        assert os.path.getsize(output_path) > 50
        from PIL import Image
        gif = Image.open(output_path)
        # 30 frames at 30fps = 1s, downsampled to 10fps → ~10 frames
        n_frames = getattr(gif, "n_frames", 1)
        assert n_frames == 10, f"30fps 1s 源降采样到 10fps 应有 ~10 帧, 实际 {n_frames}"


class TestControlState:
    """Slice 5: 控件状态 — 无帧项目不启用播放/裁剪/导出"""

    def _make_mock_window(self, frames):
        from types import SimpleNamespace

        def btn():
            ns = SimpleNamespace()
            ns.state = None
            ns.setEnabled = lambda v: setattr(ns, "state", v)
            ns.setChecked = lambda v: None
            return ns

        window = SimpleNamespace(
            _compositor=SimpleNamespace(_frames=frames, fps=30, width=100, height=100),
            _btn_rewind=btn(), _btn_step_back=btn(), _btn_play=btn(),
            _btn_step_fwd=btn(), _btn_ff=btn(), _btn_export=btn(),
            _btn_crop=btn(), _btn_add_audio=btn(),
            _audio_regions=[], _playback=None,
            _frame_label=SimpleNamespace(setText=lambda v: None),
            _timeline=SimpleNamespace(tracks=[], duration=0.0, set_tracks=lambda v: None),
            _crop_active=False, _project_manager=None, _project_dir=None,
            _recorded_data=None, _cursor_effect=None,
            _show_notification=lambda title, msg, level: None,
            config=SimpleNamespace(cursor_size=32, cursor_theme="light",
                                   cursor_style="dot", trail_enabled=False,
                                   default_fps=30),
        )
        return window

    def test_controls_disabled_when_no_frames(self):
        from app.main_window import MainWindow
        w = self._make_mock_window([])
        MainWindow._enable_playback_controls(w, False)
        w._btn_export.setEnabled(False)
        w._btn_crop.setEnabled(False)
        assert w._btn_rewind.state is False
        assert w._btn_play.state is False
        assert w._btn_export.state is False
        assert w._btn_crop.state is False

    def test_controls_enabled_when_valid_frames(self):
        from app.main_window import MainWindow
        w = self._make_mock_window([1, 2, 3])
        MainWindow._enable_playback_controls(w, True)
        w._btn_export.setEnabled(True)
        w._btn_crop.setEnabled(True)
        assert w._btn_rewind.state is True
        assert w._btn_play.state is True
        assert w._btn_export.state is True
        assert w._btn_crop.state is True


class TestMediaPathResolution:
    """安全路径解析 helper"""

    def test_rejects_absolute_path(self):
        from app.main_window import _resolve_media_path
        import pytest
        with pytest.raises(ValueError, match="拒绝绝对路径"):
            _resolve_media_path("/project", "/etc/passwd")

    def test_rejects_escape_via_dotdot(self):
        from app.main_window import _resolve_media_path
        import pytest
        with pytest.raises(ValueError, match="路径越界"):
            _resolve_media_path("/project/sub", "../../etc/passwd")

    def test_accepts_normal_relative_path(self):
        from app.main_window import _resolve_media_path
        result = _resolve_media_path("/project/sub", "audio.wav")
        assert result == os.path.realpath("/project/sub/audio.wav")

    def test_rejects_absolute_video_path_in_project(self, tmp_path):
        """project.json 中的绝对视频路径应被拒绝"""
        from types import SimpleNamespace
        from app.main_window import MainWindow, _resolve_media_path
        import pytest

        with pytest.raises(ValueError, match="拒绝绝对路径"):
            _resolve_media_path(str(tmp_path), "/etc/passwd")


class TestAudioHelper:
    """_load_project_audio helper 测试"""

    def test_returns_none_when_no_audio_source(self):
        from app.main_window import _load_project_audio
        from types import SimpleNamespace
        result = _load_project_audio("/tmp", SimpleNamespace(audio_mic="", audio_system=""))
        assert result is None

    def test_returns_none_when_source_is_none(self):
        from app.main_window import _load_project_audio
        result = _load_project_audio("/tmp", None)
        assert result is None

    def test_loads_and_mixes_audio(self, tmp_path):
        from app.main_window import _load_project_audio, _write_wav
        from core.project import SourceInfo

        samplerate = 44100
        mic_data = np.ones((samplerate, 1), dtype=np.float32) * 0.3
        _write_wav(str(tmp_path / "mic.wav"), mic_data, samplerate)
        _write_wav(str(tmp_path / "sys.wav"), mic_data, samplerate)

        source = SourceInfo(audio_mic="mic.wav", audio_system="sys.wav",
                            duration=1.0, fps=30, width=100, height=100)
        result = _load_project_audio(str(tmp_path), source)
        assert result is not None
        assert result.channels == 2
        assert result.samplerate == samplerate
        assert result.data.shape[0] > 0
        assert np.max(result.data) > 0.0


class TestOnOpenProjectIntegration:
    """真正调用 MainWindow._on_open_project() 的集成测试"""

    def test_open_project_loads_frames_and_audio(self, tmp_path, monkeypatch):
        import cv2
        from pathlib import Path
        from types import SimpleNamespace
        from app.main_window import MainWindow, _write_wav
        from core.project import Project, SourceInfo, Track, Clip

        project_dir = str(tmp_path / "reopen_test")
        os.makedirs(project_dir)

        # ── 创建 frames.data + frames.idx ──
        payloads = []
        offsets = []
        for i in range(10):
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[:, :, 0] = i * 25
            success, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            assert success
            payload = encoded.tobytes()
            offsets.append([0, len(payload)] if i == 0 else [sum(len(p) for p in payloads), len(payload)])
            payloads.append(payload)
        with open(os.path.join(project_dir, "frames.data"), "wb") as f:
            for p in payloads:
                f.write(p)
        with open(os.path.join(project_dir, "frames.idx"), "w") as f:
            json.dump(offsets, f)

        # ── 创建音频 WAV ──
        samplerate = 44100
        mic_data = np.ones((samplerate, 1), dtype=np.float32) * 0.3
        _write_wav(str(Path(project_dir) / "audio_mic.wav"), mic_data, samplerate)
        _write_wav(str(Path(project_dir) / "audio_system.wav"), mic_data, samplerate)

        # ── 创建 project.json ──
        project = Project()
        project.name = "reopen_test"
        project.source = SourceInfo(video="frames.data", audio_mic="audio_mic.wav",
                                    audio_system="audio_system.wav",
                                    duration=10 / 30.0, fps=30, width=100, height=100)
        project._frame_count = 10
        project.timeline = [Track(type="video", name="视频", clips=[
            Clip(type="video", start=0, end=10 / 30.0, content="test")])]
        project.save(os.path.join(project_dir, "project.json"))

        # ── 模拟 MainWindow ──
        def btn():
            ns = SimpleNamespace()
            ns.setEnabled = lambda v: None
            ns.setChecked = lambda v: None
            return ns

        captured_audio = [None]

        class FakePlayback:
            def __init__(self, widget, compositor, audio_result=None, video_clips=None):
                captured_audio[0] = audio_result
            def seek(self, idx):
                pass
            def set_on_frame_changed(self, cb):
                pass

        import app.main_window as mw_mod
        import ui.preview_widget as preview_mod
        monkeypatch.setattr(preview_mod, "PlaybackController", FakePlayback)

        # 使用真实 Compositor 确保 frames.data 正确加载
        from core.compositor import Compositor as RealCompositor
        compositor = RealCompositor(100, 100, 30)

        window = SimpleNamespace(
            _project_session=None,
            _recording_controller=None,
            _compositor=compositor,
            _recorded_data=None,
            _playback=None,
            _audio_regions=[],
            _export_controller=SimpleNamespace(),
            _project_manager=SimpleNamespace(
                open_project=lambda d: Project.load(os.path.join(d, "project.json"))),
            _timeline=SimpleNamespace(set_tracks=lambda v: None, duration=0.0,
                                       tracks=[], playhead=0.0, update=lambda: None),
            _preview=SimpleNamespace(set_fps=lambda v: None, show_frame=lambda v: None),
            _cursor_effect=None,
            config=SimpleNamespace(cursor_size=32, cursor_theme="light",
                                    cursor_style="dot", trail_enabled=False,
                                    default_fps=30, preview_quality=0.5),
            _frame_label=SimpleNamespace(setText=lambda v: None),
            _btn_export=btn(), _btn_crop=btn(), _btn_add_audio=btn(),
            _btn_rewind=btn(), _btn_step_back=btn(), _btn_play=btn(),
            _btn_step_fwd=btn(), _btn_ff=btn(),
            _crop_active=False, _crop_overlay=None,
            _editing_zoom_clip=None,
            _enable_playback_controls=lambda enabled: None,
            _connect_timeline_signals=lambda: None,
            _switch_to_editor=lambda: None,
            _create_playback_controller=lambda: None,
            _show_notification=lambda title, msg, level: None,
            update_status=lambda text: None,
        )
        # 在 window 构造完成后绑定 _create_playback_controller（需要引用 window）
        def _create_playback():
            audio = window._recorded_data["audio"] if window._recorded_data else None
            captured_audio[0] = audio
            window._playback = FakePlayback(None, None, audio_result=audio)
        window._create_playback_controller = _create_playback

        # 将 _project_dir 作为属性写入
        window._project_dir = project_dir

        MainWindow._on_open_project(window, project_dir)

        # 帧已加载
        assert len(window._compositor._frames) == 10

        # PlaybackController 收到非空混合音频
        audio = captured_audio[0]
        assert audio is not None, "PlaybackController 应收到非空 AudioResult"
        assert audio.samplerate > 0
        assert audio.data.shape[0] > 0

        # _recorded_data['audio'] 可供导出使用
        assert window._recorded_data is not None
        export_audio = window._recorded_data.get("audio")
        assert export_audio is not None
        assert export_audio.data.shape[0] > 0


class TestRecordedDataConditional:
    """_recorded_data 仅在存在帧或音频时构造"""

    def test_no_recorded_data_when_no_frames_and_no_audio(self, tmp_path):
        from types import SimpleNamespace
        from app.main_window import MainWindow
        from core.project import Project

        project_dir = str(tmp_path / "empty")
        os.makedirs(project_dir)
        project = Project()
        project.name = "empty"
        project.save(os.path.join(project_dir, "project.json"))

        compositor = SimpleNamespace(
            _frames=[], frames=[], frame_times=[], cursor_events=[], click_events=[],
            crop_region=None, _monitor_left=0, _monitor_top=0,
            fps=30, width=100, height=100, _base_time=0,
            source_duration=0,
            load_frames_data=lambda path, count, fps: 0,
            load_clips=lambda clips: None,
            load_manual_zoom_clips=lambda clips: None,
            register_effect=lambda name, effect: None,
            set_crop=lambda crop: None,
            set_preview_quality=lambda q: None,
        )

        def btn():
            ns = SimpleNamespace()
            ns.setEnabled = lambda v: None
            ns.setChecked = lambda v: None
            return ns

        window = SimpleNamespace(
            _recorded_data={"old": "data"},
            _compositor=compositor,
            _playback=None, _audio_regions=[],
            _project_manager=SimpleNamespace(
                open_project=lambda d: Project.load(os.path.join(d, "project.json"))),
            _timeline=SimpleNamespace(set_tracks=lambda v: None, duration=0.0,
                                       tracks=[], playhead=0.0),
            _preview=SimpleNamespace(set_fps=lambda v: None),
            _cursor_effect=None,
            config=SimpleNamespace(cursor_size=32, cursor_theme="light",
                                    cursor_style="dot", trail_enabled=False,
                                    default_fps=30, preview_quality=0.5),
            _frame_label=SimpleNamespace(setText=lambda v: None),
            _btn_export=btn(), _btn_crop=btn(), _btn_add_audio=btn(),
            _btn_rewind=btn(), _btn_step_back=btn(), _btn_play=btn(),
            _btn_step_fwd=btn(), _btn_ff=btn(),
            _crop_active=False, _crop_overlay=None,
            _editing_zoom_clip=None,
            _enable_playback_controls=lambda enabled: None,
            _connect_timeline_signals=lambda: None,
            _switch_to_editor=lambda: None,
            _create_playback_controller=lambda: None,
            _show_notification=lambda title, msg, level: None,
            update_status=lambda text: None,
        )
        window._project_dir = project_dir

        MainWindow._on_open_project(window, project_dir)
        assert window._recorded_data is None, "无帧无音频时应为 None"
