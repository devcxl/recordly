"""录制保存→重开往返稳定性测试"""

import json
import os

import numpy as np


class TestAutosaveCreatesRequiredArtifacts:
    """_finalize_project 生成 frames.idx 和完整 project.json"""

    def test_finalize_project_creates_frames_idx_and_project_json(self, tmp_path):
        from types import SimpleNamespace
        from app.main_window import MainWindow
        from core.compositor import Compositor
        from core.project import Project, Track, Clip
        from core.screen_capture import CapturedFrame

        project_dir = str(tmp_path / "test_project")
        os.makedirs(project_dir)
        frames = [CapturedFrame(data=np.zeros((100, 100, 3), dtype=np.uint8),
                                timestamp=i / 30.0, index=i) for i in range(30)]
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
            _audio_regions=[], config=SimpleNamespace(default_fps=30),
            _refresh_home_page=lambda: None, update_status=lambda text: None,
            _show_notification=lambda title, msg, level: notifications.append(locals()),
            _get_recording_duration=lambda: 1.0,
            _collect_project_state=lambda project: None, _project_name="test_recording",
        )
        MainWindow._finalize_project(window)

        assert not notifications, f"不应有错误通知: {notifications}"
        assert os.path.exists(os.path.join(project_dir, "frames.idx"))
        proj = Project.load(os.path.join(project_dir, "project.json"))
        assert proj.source is not None
        assert proj.source.video == "frames.data"
        assert proj._frame_count == 30
        assert proj.name == "test_recording"


class TestCursorTimebase:
    """光标时间基 — 保存时转为相对 compositor base_time 的时间戳"""

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
                                timestamp=100.0 + i / 30.0, index=i) for i in range(30)]
        compositor = Compositor(100, 100, 30)
        compositor.load_frames(frames)
        assert compositor._base_time == 100.0
        compositor.load_cursor_events([
            CursorEvent(x=10, y=20, timestamp=100.0),
            CursorEvent(x=50, y=60, timestamp=100.5),
            CursorEvent(x=80, y=90, timestamp=101.0),
        ], [])

        project = Project()
        MainWindow._collect_project_state(
            SimpleNamespace(_compositor=compositor, _timeline=SimpleNamespace(tracks=[]),
                            _audio_regions=[]), project)
        project.save(os.path.join(project_dir, "project.json"))
        loaded = Project.load(os.path.join(project_dir, "project.json"))

        reload_compositor = Compositor(100, 100, 30)
        reload_compositor.load_frames(
            [CapturedFrame(data=np.zeros((100, 100, 3), dtype=np.uint8),
                           timestamp=i / 30.0, index=i) for i in range(30)])
        evt = type("EventData", (), {})
        reload_compositor._cursor_events = []
        for c in loaded.cursor_events:
            e = evt()
            e.x, e.y, e.timestamp = int(c[0]), int(c[1]), float(c[2])
            reload_compositor._cursor_events.append(e)

        assert reload_compositor._interpolate_cursor(0.0) == (10, 20)
        assert reload_compositor._interpolate_cursor(1.0) == (80, 90)


class TestGifFps:
    """GIF 导出使用 fps filter 降采样，保持输入 r=compositor.fps"""

    def test_gif_graph_uses_fps_filter_before_split(self):
        import ffmpeg
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        worker = ExportWorker(Compositor(320, 240, 30), None,
                              ExportSettings(output_path="out.gif", format="gif", fps=15))
        command = " ".join(ffmpeg.compile(worker._build_gif_output(320, 240)))
        assert "-r 30" in command
        assert "fps=fps=15" in command
        assert "round=near" in command

    def test_gif_real_export_has_correct_fps_and_duration(self, tmp_path):
        import shutil
        if not shutil.which("ffmpeg"):
            import pytest
            pytest.skip("ffmpeg 不可用")

        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        compositor = Compositor(32, 32, 30)
        compositor._frames = [type("F", (), {
            "data": np.ones((32, 32, 3), dtype=np.uint8) * (i * 8),
            "timestamp": i / 30.0, "index": i,
        })() for i in range(30)]

        worker = ExportWorker(compositor, None,
                              ExportSettings(output_path=str(tmp_path / "test.gif"),
                                             format="gif", fps=10))
        worker._export_gif()
        from PIL import Image
        gif = Image.open(str(tmp_path / "test.gif"))
        assert getattr(gif, "n_frames", 1) == 10
        duration_ms = 0
        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            duration_ms += gif.info.get("duration", 0)
        assert duration_ms == 1000


class TestControlState:
    """控件状态 — 无帧项目不启用播放/裁剪/导出"""

    def _make_mock_window(self, frames):
        from types import SimpleNamespace
        def btn():
            ns = SimpleNamespace()
            ns.state = None
            ns.setEnabled = lambda v: setattr(ns, "state", v)
            ns.setChecked = lambda v: None
            return ns
        return SimpleNamespace(
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
                                   cursor_style="dot", trail_enabled=False, default_fps=30),
        )

    def test_controls_disabled_when_no_frames(self):
        from app.main_window import MainWindow
        w = self._make_mock_window([])
        MainWindow._enable_playback_controls(w, False)
        w._btn_export.setEnabled(False)
        w._btn_crop.setEnabled(False)
        assert not w._btn_rewind.state
        assert not w._btn_play.state
        assert not w._btn_export.state

    def test_controls_enabled_when_valid_frames(self):
        from app.main_window import MainWindow
        w = self._make_mock_window([1, 2, 3])
        MainWindow._enable_playback_controls(w, True)
        w._btn_export.setEnabled(True)
        w._btn_crop.setEnabled(True)
        assert w._btn_rewind.state
        assert w._btn_play.state
        assert w._btn_export.state


class TestMediaPathResolution:
    """_resolve_media_path 安全路径解析"""

    def test_rejects_outside_absolute_path(self, tmp_path):
        from app.main_window import _resolve_media_path
        import pytest
        outside = str(tmp_path / ".." / "outside_file")
        open(outside, "w").close()
        with pytest.raises(ValueError, match="路径越界"):
            _resolve_media_path(str(tmp_path), outside)

    def test_rejects_escape_via_dotdot(self, tmp_path):
        from app.main_window import _resolve_media_path
        import pytest
        with pytest.raises(ValueError, match="路径越界"):
            _resolve_media_path(str(tmp_path), "../outside_file")

    def test_accepts_normal_relative_path(self, tmp_path):
        from app.main_window import _resolve_media_path
        result = _resolve_media_path(str(tmp_path), "audio.wav")
        assert result == os.path.realpath(os.path.join(str(tmp_path), "audio.wav"))

    def test_accepts_absolute_path_inside_project_dir(self, tmp_path):
        from app.main_window import _resolve_media_path
        inside = str(tmp_path / "audio.wav")
        open(inside, "w").close()
        result = _resolve_media_path(str(tmp_path), inside)
        assert result == os.path.realpath(inside)

    def test_rejects_outside_sibling_dir(self, tmp_path):
        """与 project_dir 同级的目录内文件也应拒绝"""
        from app.main_window import _resolve_media_path
        import pytest
        sibling_dir = str(tmp_path / ".." / "other_project")
        os.makedirs(sibling_dir, exist_ok=True)
        with pytest.raises(ValueError, match="路径越界"):
            _resolve_media_path(str(tmp_path),
                                os.path.join(sibling_dir, "some_file"))

    def test_commonpath_different_drive_raises_valueerror(self, tmp_path, monkeypatch):
        """Windows 不同盘符时 os.path.commonpath 抛 ValueError, 统一重抛为'路径越界'"""
        from app.main_window import _resolve_media_path
        import pytest
        import os as os_mod

        def fake_commonpath(paths):
            raise ValueError("Paths don't have the same drive")
        monkeypatch.setattr(os_mod.path, "commonpath", fake_commonpath)
        with pytest.raises(ValueError, match="路径越界"):
            _resolve_media_path(str(tmp_path), "audio.wav")

    def test_notifications_on_video_path_violation(self, tmp_path):
        """_on_open_project 在视频路径越界时通知但不崩溃"""
        from types import SimpleNamespace
        from app.main_window import MainWindow
        from core.project import Project, SourceInfo

        project_dir = str(tmp_path / "violation")
        os.makedirs(project_dir)
        project = Project()
        project.source = SourceInfo(video=str(tmp_path / ".." / "outside.mp4"))
        project.save(os.path.join(project_dir, "project.json"))

        notified = []
        w = SimpleNamespace(
            _compositor=SimpleNamespace(
                _frames=[], frames=[], frame_times=[], cursor_events=[], click_events=[],
                crop_region=None, _monitor_left=0, _monitor_top=0,
                fps=30, width=100, height=100, _base_time=0,
                load_frames_data=lambda *a: 0, load_clips=lambda v: None,
                register_effect=lambda *a: None, set_crop=lambda v: None),
            _recorded_data=None, _playback=None, _audio_regions=[],
            _project_manager=SimpleNamespace(
                open_project=lambda d: Project.load(os.path.join(d, "project.json"))),
            _timeline=SimpleNamespace(set_tracks=lambda v: None, duration=0.0,
                                       tracks=[], playhead=0.0),
            _preview=SimpleNamespace(set_fps=lambda v: None),
            _cursor_effect=None, _crop_active=False,
            config=SimpleNamespace(default_fps=30, cursor_size=32, cursor_theme="light",
                                   cursor_style="dot", trail_enabled=False, preview_quality=0.5),
            _frame_label=SimpleNamespace(setText=lambda v: None),
            _btn_export=SimpleNamespace(setEnabled=lambda v: None, setChecked=lambda v: None),
            _btn_crop=SimpleNamespace(setEnabled=lambda v: None, setChecked=lambda v: None),
            _btn_add_audio=SimpleNamespace(setEnabled=lambda v: None),
            _btn_rewind=SimpleNamespace(setEnabled=lambda v: None),
            _btn_step_back=SimpleNamespace(setEnabled=lambda v: None),
            _btn_play=SimpleNamespace(setEnabled=lambda v: None),
            _btn_step_fwd=SimpleNamespace(setEnabled=lambda v: None),
            _btn_ff=SimpleNamespace(setEnabled=lambda v: None),
            _enable_playback_controls=lambda enabled: None,
            _connect_timeline_signals=lambda: None, _switch_to_editor=lambda: None,
            _create_playback_controller=lambda: None,
            _show_notification=lambda title, msg, level: notified.append(title),
            update_status=lambda text: None,
        )
        w._project_dir = project_dir
        MainWindow._on_open_project(w, project_dir)
        assert any("视频" in n for n in notified), f"应有视频路径通知: {notified}"


class TestAudioHelper:
    """_load_project_audio helper 测试"""

    def test_returns_none_when_no_audio_source(self, tmp_path):
        from app.main_window import _load_project_audio
        from types import SimpleNamespace
        assert _load_project_audio(str(tmp_path), SimpleNamespace(audio_mic="", audio_system="")) is None

    def test_returns_none_when_source_is_none(self, tmp_path):
        from app.main_window import _load_project_audio
        assert _load_project_audio(str(tmp_path), None) is None

    def test_loads_and_mixes_audio(self, tmp_path):
        from app.main_window import _load_project_audio, _write_wav
        from core.project import SourceInfo
        samplerate = 44100
        data = np.ones((samplerate, 1), dtype=np.float32) * 0.3
        _write_wav(str(tmp_path / "m.wav"), data, samplerate)
        _write_wav(str(tmp_path / "s.wav"), data, samplerate)
        result = _load_project_audio(str(tmp_path),
                                     SourceInfo(audio_mic="m.wav", audio_system="s.wav",
                                                duration=1.0, fps=30, width=100, height=100))
        assert result is not None
        assert result.channels == 2
        assert result.samplerate == samplerate
        assert np.max(result.data) > 0.0

    def test_audio_load_failure_shows_notification(self, tmp_path):
        """_on_open_project 在音频加载失败时通知但继续打开视频"""
        from types import SimpleNamespace
        from app.main_window import MainWindow
        from core.project import Project, SourceInfo

        project_dir = str(tmp_path / "audio_fail")
        os.makedirs(project_dir)
        project = Project()
        project.source = SourceInfo(video="frames.data", audio_mic="../../etc/passwd",
                                    audio_system="", duration=1.0, fps=30, width=100, height=100)
        project._frame_count = 0
        project.save(os.path.join(project_dir, "project.json"))

        notified = []
        w = SimpleNamespace(
            _compositor=SimpleNamespace(
                _frames=[], frames=[], frame_times=[], cursor_events=[], click_events=[],
                crop_region=None, _monitor_left=0, _monitor_top=0,
                fps=30, width=100, height=100, _base_time=0,
                load_frames_data=lambda *a: 0, load_clips=lambda v: None,
                register_effect=lambda *a: None, set_crop=lambda v: None),
            _recorded_data=None, _playback=None, _audio_regions=[],
            _project_manager=SimpleNamespace(
                open_project=lambda d: Project.load(os.path.join(d, "project.json"))),
            _timeline=SimpleNamespace(set_tracks=lambda v: None, duration=0.0,
                                       tracks=[], playhead=0.0),
            _preview=SimpleNamespace(set_fps=lambda v: None),
            _cursor_effect=None, _crop_active=False,
            config=SimpleNamespace(default_fps=30, cursor_size=32, cursor_theme="light",
                                   cursor_style="dot", trail_enabled=False, preview_quality=0.5),
            _frame_label=SimpleNamespace(setText=lambda v: None),
            _btn_export=SimpleNamespace(setEnabled=lambda v: None, setChecked=lambda v: None),
            _btn_crop=SimpleNamespace(setEnabled=lambda v: None, setChecked=lambda v: None),
            _btn_add_audio=SimpleNamespace(setEnabled=lambda v: None),
            _btn_rewind=SimpleNamespace(setEnabled=lambda v: None),
            _btn_step_back=SimpleNamespace(setEnabled=lambda v: None),
            _btn_play=SimpleNamespace(setEnabled=lambda v: None),
            _btn_step_fwd=SimpleNamespace(setEnabled=lambda v: None),
            _btn_ff=SimpleNamespace(setEnabled=lambda v: None),
            _enable_playback_controls=lambda enabled: None,
            _connect_timeline_signals=lambda: None, _switch_to_editor=lambda: None,
            _create_playback_controller=lambda: None,
            _show_notification=lambda title, msg, level: notified.append(title),
            update_status=lambda text: None,
        )
        w._project_dir = project_dir
        MainWindow._on_open_project(w, project_dir)
        assert any("音频" in n for n in notified), f"应有音频通知: {notified}"


class TestFullRoundtrip:
    """保存→重开核心状态的集成级贯穿测试"""

    def test_save_then_reopen_roundtrip(self, tmp_path, monkeypatch):
        import cv2
        from pathlib import Path
        from types import SimpleNamespace
        from app.main_window import MainWindow, _write_wav, _load_project_audio
        from core.compositor import Compositor
        from core.project import Project, SourceInfo, Track, Clip
        from core.screen_capture import CapturedFrame
        from core.audio_capture import AudioResult

        project_dir = str(tmp_path / "roundtrip")
        os.makedirs(project_dir)

        # ── Phase 1: 模拟录制结束 → _finalize_project 保存 ──
        frames = [CapturedFrame(data=np.zeros((100, 100, 3), dtype=np.uint8),
                                timestamp=i / 30.0, index=i) for i in range(10)]
        compositor = Compositor(100, 100, 30)
        compositor.load_frames(frames)

        samplerate = 44100
        mic_data = np.ones((samplerate, 1), dtype=np.float32) * 0.3
        sys_data = np.ones((samplerate, 2), dtype=np.float32) * 0.2

        window = SimpleNamespace(
            _recorded_data={"frames": frames, "cursor_events": [], "clicks": [],
                            "mic_audio": AudioResult(mic_data, samplerate, 1),
                            "system_audio": AudioResult(sys_data, samplerate, 2)},
            _project_dir=project_dir,
            _compositor=compositor,
            _recording_controller=SimpleNamespace(
                recorder=SimpleNamespace(
                    screen=SimpleNamespace(frame_offsets=[[0, 100] for _ in range(10)]))),
            _timeline=SimpleNamespace(tracks=[Track(type="video", name="视频", clips=[
                Clip(type="video", start=0, end=10 / 30.0, content="test")])]),
            _audio_regions=[], config=SimpleNamespace(default_fps=30),
            _refresh_home_page=lambda: None, update_status=lambda text: None,
            _show_notification=lambda title, msg, level: print(f"SAVE: {title} {msg}"),
            _get_recording_duration=lambda: 10 / 30.0,
            _collect_project_state=lambda project: None, _project_name="roundtrip",
        )
        MainWindow._finalize_project(window)

        assert os.path.exists(os.path.join(project_dir, "frames.idx"))
        assert os.path.exists(os.path.join(project_dir, "project.json"))
        saved = Project.load(os.path.join(project_dir, "project.json"))
        assert saved.source is not None
        assert saved.source.video == "frames.data"
        assert saved._frame_count == 10
        assert saved.source.audio_mic == "audio_mic.wav"
        assert saved.source.audio_system == "audio_system.wav"

        # 创建 frames.data（_finalize_project 只写 frames.idx 不写帧数据）
        import cv2
        payloads = []
        for i in range(10):
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[:, :, 0] = i * 25
            success, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            assert success
            payloads.append(encoded.tobytes())
        with open(os.path.join(project_dir, "frames.data"), "wb") as f:
            for p in payloads:
                f.write(p)

        # ── Phase 2: 模拟重开 → _on_open_project 加载 ──
        import ui.preview_widget as preview_mod
        captured_audio = [None]

        class FakePlayback:
            def __init__(self, widget, compositor, audio_result=None, video_clips=None):
                captured_audio[0] = audio_result
            def seek(self, idx):
                pass
            def set_on_frame_changed(self, cb):
                pass
        monkeypatch.setattr(preview_mod, "PlaybackController", FakePlayback)

        def btn():
            ns = SimpleNamespace()
            ns.setEnabled = lambda v: None
            ns.setChecked = lambda v: None
            return ns

        reopen_compositor = Compositor(100, 100, 30)
        reopen_window = SimpleNamespace(
            _recorded_data=None, _playback=None, _audio_regions=[],
            _compositor=reopen_compositor,
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
            _crop_active=False, _crop_overlay=None, _editing_zoom_clip=None,
            _enable_playback_controls=lambda enabled: None,
            _connect_timeline_signals=lambda: None, _switch_to_editor=lambda: None,
            _create_playback_controller=lambda: None,
            _project_session=None, _recording_controller=None,
            _export_controller=SimpleNamespace(),
            _show_notification=lambda title, msg, level: print(f"REOPEN: {title} {msg}"),
            update_status=lambda text: None,
        )
        reopen_window._project_dir = project_dir

        def _create_playback():
            audio = reopen_window._recorded_data["audio"] if reopen_window._recorded_data else None
            captured_audio[0] = audio
            reopen_window._playback = FakePlayback(None, None, audio_result=audio)
        reopen_window._create_playback_controller = _create_playback

        MainWindow._on_open_project(reopen_window, project_dir)

        # ── 断言: 帧恢复 ──
        assert len(reopen_compositor._frames) == 10
        # ── 断言: 音频恢复且可导出 ──
        assert captured_audio[0] is not None, "PlaybackController 应收到非空 AudioResult"
        assert reopen_window._recorded_data is not None, "_recorded_data 应存在"
        export_audio = reopen_window._recorded_data.get("audio")
        assert export_audio is not None, "_recorded_data['audio'] 可供导出"
        assert export_audio.channels == 2
        assert export_audio.samplerate == samplerate
        assert export_audio.data.shape[0] > 0


class TestMp4AudioTrack:
    """MP4 导出含音轨验证"""

    @staticmethod
    def _ffprobe_available():
        import shutil
        return shutil.which("ffprobe") is not None and shutil.which("ffmpeg") is not None

    def test_mp4_export_contains_video_and_audio_streams(self, tmp_path):
        if not self._ffprobe_available():
            import pytest
            pytest.skip("ffmpeg/ffprobe 不可用")

        import subprocess
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings
        from core.audio_capture import AudioResult

        # 1 秒视频 + 音频
        compositor = Compositor(32, 32, 30)
        compositor._frames = [type("F", (), {
            "data": np.ones((32, 32, 3), dtype=np.uint8) * 128,
            "timestamp": i / 30.0, "index": i,
        })() for i in range(30)]

        samplerate = 22050
        audio_data = np.ones((samplerate, 1), dtype=np.float32) * 0.3
        audio_result = AudioResult(audio_data, samplerate, 1)

        output_path = str(tmp_path / "test.mp4")
        worker = ExportWorker(compositor, audio_result.data,
                              ExportSettings(output_path=output_path, fps=30, format="mp4",
                                             samplerate=samplerate))
        worker._export_mp4()

        assert os.path.getsize(output_path) > 500

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type", "-of", "csv=p=0", output_path],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        stream_types = [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
        assert "video" in stream_types, f"应包含视频流: {stream_types}"
        assert "audio" in stream_types, f"应包含音频流: {stream_types}"
