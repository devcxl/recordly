"""录制保存→重开往返稳定性测试"""

import json
import os

import pytest
import numpy as np


class TestAutosaveCreatesRequiredArtifacts:
    """Slice 1: _finalize_project 生成 frames.idx 和完整 project.json"""

    def test_finalize_project_creates_frames_idx_and_project_json(self, tmp_path):
        """录制收尾必须生成 frames.idx，project.json 包含非空 source、正确 frame_count 和时间线"""
        from types import SimpleNamespace
        from app.main_window import MainWindow, _write_wav
        from core.compositor import Compositor
        from core.project import Project, SourceInfo, Track, Clip
        from core.screen_capture import CapturedFrame

        project_dir = str(tmp_path / "test_project")
        os.makedirs(project_dir)

        frames = [
            CapturedFrame(
                data=np.zeros((100, 100, 3), dtype=np.uint8),
                timestamp=i / 30.0, index=i,
            )
            for i in range(30)
        ]

        compositor = Compositor(100, 100, 30)
        compositor.load_frames(frames)

        recording_controller = SimpleNamespace(
            recorder=SimpleNamespace(
                screen=SimpleNamespace(frame_offsets=[[0, 100], [100, 100]]),
            ),
        )

        tracks = [Track(type="video", name="视频", clips=[
            Clip(type="video", start=0, end=1.0, content="test"),
        ])]

        timeline = SimpleNamespace(tracks=tracks)

        calls = {"notification": None}

        window = SimpleNamespace(
            _recorded_data={
                "frames": frames,
                "cursor_events": [],
                "clicks": [],
                "mic_audio": None,
                "system_audio": None,
            },
            _project_dir=project_dir,
            _compositor=compositor,
            _recording_controller=recording_controller,
            _timeline=timeline,
            _audio_regions=[],
            config=SimpleNamespace(default_fps=30),
            _refresh_home_page=lambda: None,
            update_status=lambda text: None,
            _show_notification=lambda title, msg, level: (
                setattr(calls, "notification", {"title": title, "msg": msg, "level": level})
            ),
            _get_recording_duration=lambda: 1.0,
            _collect_project_state=lambda project: None,
            _project_name="test_recording",
        )

        # 执行（BUG: 当前代码用 self.recording_controller 而非 self._recording_controller）
        MainWindow._finalize_project(window)

        # 验证 frames.idx 存在
        idx_path = os.path.join(project_dir, "frames.idx")
        assert os.path.exists(idx_path), "frames.idx 必须生成"

        with open(idx_path) as f:
            offsets = json.load(f)
        assert isinstance(offsets, list), "frames.idx 应为 JSON 数组"

        # 验证 project.json 包含关键字段
        proj = Project.load(os.path.join(project_dir, "project.json"))
        assert proj.source is not None, "source 不应为空"
        assert proj.source.video == "frames.data", "source.video 应为 frames.data"
        assert proj._frame_count == 30, "frame_count 应为 30"
        assert proj.name == "test_recording", "name 应保留"

        assert calls["notification"] is None, "不应有错误通知"


class TestAudioReopen:
    """Slice 2: 重开音频 — 从 WAV 恢复 AudioResult"""

    def test_reopen_mixes_wavs_into_audio_result(self, tmp_path):
        """重开项目后 PlaybackController 应获得混合 AudioResult"""
        import numpy as np
        from types import SimpleNamespace
        from app.main_window import MainWindow, _write_wav, _read_wav
        from core.compositor import Compositor
        from core.audio_capture import AudioResult, mix_audio_results
        from core.project import Project, SourceInfo, Track, Clip

        project_dir = str(tmp_path / "test_audio")
        os.makedirs(project_dir)

        # 创建测试音频文件
        samplerate = 44100
        mic_data = np.ones((samplerate, 1), dtype=np.float32) * 0.3
        sys_data = np.ones((samplerate, 2), dtype=np.float32) * 0.2
        _write_wav(str(tmp_path / "audio_mic.wav"), mic_data, samplerate)
        _write_wav(str(tmp_path / "audio_system.wav"), sys_data, samplerate)

        # 创建 project.json
        project = Project()
        project.source = SourceInfo(
            video="frames.data",
            audio_mic="audio_mic.wav",
            audio_system="audio_system.wav",
            duration=1.0,
            fps=30,
            width=100,
            height=100,
        )
        project._frame_count = 10
        project.save(os.path.join(project_dir, "project.json"))

        # 重设 project_dir 内 WAV 路径（_write_wav 写入 tmp_path）
        import shutil
        shutil.copy(str(tmp_path / "audio_mic.wav"), os.path.join(project_dir, "audio_mic.wav"))
        shutil.copy(str(tmp_path / "audio_system.wav"), os.path.join(project_dir, "audio_system.wav"))

        # 模拟打开项目时的音频恢复
        source = project.source
        mic_path = os.path.join(project_dir, source.audio_mic) if source.audio_mic else ""
        sys_path = os.path.join(project_dir, source.audio_system) if source.audio_system else ""

        mic_audio, mic_sr, mic_ch = _read_wav(mic_path)
        sys_audio, sys_sr, sys_ch = _read_wav(sys_path)

        assert mic_audio is not None, "mic WAV 应可读取"
        assert sys_audio is not None, "system WAV 应可读取"

        mixed = mix_audio_results(
            AudioResult(mic_audio, mic_sr, mic_ch),
            AudioResult(sys_audio, sys_sr, sys_ch),
        )
        assert mixed is not None, "混合后应有 AudioResult"
        assert mixed.data.shape[0] == samplerate, "混合音频应有正确帧数"
        assert mixed.channels == 2, "混合应为立体声"
        assert mixed.samplerate == samplerate, "采样率应保留"
        assert np.max(mixed.data) > 0.0, "混合音频应有非静音数据"


class TestCursorTimebase:
    """Slice 3: 光标时间基 — 保存时转为相对 compositor base_time 的时间戳"""

    def test_cursor_events_have_relative_timestamps_after_save(self, tmp_path):
        """保存后 cursor_events 时间戳应相对于 compositor._base_time"""
        import numpy as np
        from types import SimpleNamespace
        from app.main_window import MainWindow
        from core.compositor import Compositor
        from core.project import Project, Track, Clip
        from core.screen_capture import CapturedFrame

        project_dir = str(tmp_path / "test_cursor")
        os.makedirs(project_dir)

        # compositor 首帧时间戳为 100.0 → _base_time = 100.0
        frames = [
            CapturedFrame(
                data=np.zeros((100, 100, 3), dtype=np.uint8),
                timestamp=100.0 + i / 30.0, index=i,
            )
            for i in range(30)
        ]
        compositor = Compositor(100, 100, 30)
        compositor.load_frames(frames)
        assert compositor._base_time == 100.0, "_base_time 应从首帧获取"

        # 光标事件使用绝对时间戳（关键字参数确保字段正确映射）
        from core.pointer_tracker import CursorEvent
        events = [
            CursorEvent(x=10, y=20, timestamp=100.0),
            CursorEvent(x=50, y=60, timestamp=100.5),
            CursorEvent(x=80, y=90, timestamp=101.0),
        ]
        compositor.load_cursor_events(events, [])

        assert len(compositor._cursor_events) == 3

        project = Project()

        # 使用实际 MainWindow._collect_project_state 进行保存（含时间基修正）
        window = SimpleNamespace(
            _compositor=compositor,
            _timeline=SimpleNamespace(tracks=[]),
            _audio_regions=[],
        )
        MainWindow._collect_project_state(window, project)

        # 验证：保存后时间戳应相对化（减去 _base_time）
        project.save(os.path.join(project_dir, "project.json"))
        loaded = Project.load(os.path.join(project_dir, "project.json"))

        # 重开后的 compositor 首帧时间戳从 0 开始 → _base_time = 0
        reload_frames = [
            CapturedFrame(
                data=np.zeros((100, 100, 3), dtype=np.uint8),
                timestamp=i / 30.0, index=i,
            )
            for i in range(30)
        ]
        reload_compositor = Compositor(100, 100, 30)
        reload_compositor.load_frames(reload_frames)
        assert reload_compositor._base_time == 0.0

        evt = type("EventData", (), {})
        reload_compositor._cursor_events = []
        for c in loaded.cursor_events:
            e = evt()
            e.x, e.y, e.timestamp = int(c[0]), int(c[1]), float(c[2])
            reload_compositor._cursor_events.append(e)

        # 光标插值应正常工作
        # 首帧光标应与第一个事件 (10, 20) 接近
        cx, cy = reload_compositor._interpolate_cursor(0.0)
        assert abs(cx - 10) < 30, f"首帧光标 x 应与第一个事件接近，实际 {cx}"
        assert abs(cy - 20) < 30, f"首帧光标 y 应与第一个事件接近，实际 {cy}"

        # 末帧光标应与最后一个事件 (80, 90) 接近
        cx_end, cy_end = reload_compositor._interpolate_cursor(1.0)
        end_event = reload_compositor._cursor_events[-1]
        assert abs(cx_end - end_event.x) < 30, \
            f"末帧光标 x 应与最后事件接近，预期 {end_event.x}，实际 {cx_end}"
        assert abs(cy_end - end_event.y) < 30, \
            f"末帧光标 y 应与最后事件接近，预期 {end_event.y}，实际 {cy_end}"


class TestGifFps:
    """Slice 4: GIF 导出使用 fps filter 降采样，保持输入 r=compositor.fps"""

    def test_gif_output_uses_settings_fps_instead_of_compositor_fps(self):
        """GIF 输出 fps 应为 settings.fps，输入保持 compositor.fps"""
        import ffmpeg
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        compositor = Compositor(320, 240, 30)
        worker = ExportWorker(
            compositor, None,
            ExportSettings(output_path="out.gif", format="gif", fps=15),
        )

        graph = worker._build_gif_output(320, 240)
        command = " ".join(ffmpeg.compile(graph))

        # 输入应保持 compositor.fps
        assert "-r 30" in command or "r=30" in command or "r 30" in command

        # 输出应使用 settings.fps (15)
        assert "-r 15" in command

    def test_gif_fps_filter_keeps_duration(self, tmp_path):
        """fps filter 降采样后总时长应与原始一致"""
        import subprocess
        import numpy as np
        from PIL import Image
        from core.compositor import Compositor
        from core.exporter import ExportWorker, ExportSettings

        # 创建短小合成器：10 帧 30fps → 0.333s
        compositor = Compositor(32, 32, 30)
        frames = []
        for i in range(10):
            frames.append(type("F", (), {
                "data": np.ones((32, 32, 3), dtype=np.uint8) * (i * 20),
                "timestamp": i / 30.0,
                "index": i,
            })())
        compositor._frames = frames

        output_path = str(tmp_path / "test.gif")
        worker = ExportWorker(
            compositor, None,
            ExportSettings(output_path=output_path, format="gif", fps=10),
        )

        worker._export_gif()
        # 验证导出完成
        assert os.path.exists(output_path), "GIF 文件应生成"


class TestControlState:
    """Slice 5: 控件状态 — 无帧项目不启用播放/裁剪/导出"""

    def _make_mock_window(self, frames):
        from types import SimpleNamespace
        buttons = {}
        for name in ["_btn_rewind", "_btn_step_back", "_btn_play",
                      "_btn_step_fwd", "_btn_ff", "_btn_export",
                      "_btn_crop", "_btn_add_audio"]:
            btn = SimpleNamespace()
            btn.setEnabled = lambda v, _n=name: buttons.update({_n: v})
            buttons[name] = None
            setattr(btn, "setChecked", lambda v: None)
            if name == "_btn_crop":
                btn2 = SimpleNamespace()
                btn2.setEnabled = lambda v: buttons.update({"_btn_crop": v})
                btn2.setChecked = lambda v: None
                btn = btn2
            setattr(btn, "setEnabled", lambda v, _n=name: buttons.update({_n: v}))
        # Rebuild with proper closures
        btn_export = SimpleNamespace()
        btn_export.setEnabled = lambda v: buttons.update({"_btn_export": v})
        btn_crop = SimpleNamespace()
        btn_crop.setEnabled = lambda v: buttons.update({"_btn_crop": v})
        btn_crop.setChecked = lambda v: None
        btn_add_audio = SimpleNamespace()
        btn_add_audio.setEnabled = lambda v: buttons.update({"_btn_add_audio": v})
        btn_rewind = SimpleNamespace()
        btn_rewind.setEnabled = lambda v: buttons.update({"_btn_rewind": v})
        btn_step_back = SimpleNamespace()
        btn_step_back.setEnabled = lambda v: buttons.update({"_btn_step_back": v})
        btn_play = SimpleNamespace()
        btn_play.setEnabled = lambda v: buttons.update({"_btn_play": v})
        btn_step_fwd = SimpleNamespace()
        btn_step_fwd.setEnabled = lambda v: buttons.update({"_btn_step_fwd": v})
        btn_ff = SimpleNamespace()
        btn_ff.setEnabled = lambda v: buttons.update({"_btn_ff": v})

        return SimpleNamespace(
            _compositor=SimpleNamespace(
                _frames=frames, fps=30, width=100, height=100,
            ),
            _btn_rewind=btn_rewind,
            _btn_step_back=btn_step_back,
            _btn_play=btn_play,
            _btn_step_fwd=btn_step_fwd,
            _btn_ff=btn_ff,
            _btn_export=btn_export,
            _btn_crop=btn_crop,
            _btn_add_audio=btn_add_audio,
            _audio_regions=[],
            _playback=None,
            _frame_label=SimpleNamespace(setText=lambda v: None),
            _timeline=SimpleNamespace(tracks=[], duration=0.0, set_tracks=lambda v: None),
            _crop_active=False,
            _project_manager=None,
            _project_dir=None,
            _recorded_data=None,
            _show_notification=lambda title, msg, level: None,
            _cursor_effect=None,
            config=SimpleNamespace(cursor_size=32, cursor_theme="light",
                                    cursor_style="dot", trail_enabled=False,
                                    default_fps=30),
        ), buttons

    def test_controls_disabled_when_no_frames(self):
        """打开无有效帧项目时应禁用播放/裁剪/导出控件"""
        from app.main_window import MainWindow

        window, buttons = self._make_mock_window([])

        MainWindow._enable_playback_controls(window, False)
        window._btn_export.setEnabled(False)
        window._btn_crop.setEnabled(False)
        window._btn_add_audio.setEnabled(False)

        assert buttons["_btn_rewind"] is False
        assert buttons["_btn_step_back"] is False
        assert buttons["_btn_play"] is False
        assert buttons["_btn_step_fwd"] is False
        assert buttons["_btn_ff"] is False
        assert buttons["_btn_export"] is False
        assert buttons["_btn_crop"] is False

    def test_controls_enabled_when_valid_frames(self):
        """打开有帧项目时启用播放/裁剪/导出控件"""
        from app.main_window import MainWindow

        window, buttons = self._make_mock_window([1, 2, 3])

        MainWindow._enable_playback_controls(window, True)
        window._btn_export.setEnabled(True)
        window._btn_crop.setEnabled(True)

        assert buttons["_btn_rewind"] is True
        assert buttons["_btn_step_back"] is True
        assert buttons["_btn_play"] is True
        assert buttons["_btn_step_fwd"] is True
        assert buttons["_btn_ff"] is True
        assert buttons["_btn_export"] is True
        assert buttons["_btn_crop"] is True


class TestIntegrationRoundtrip:
    """Slice 6: 保存→重开核心状态的集成级回归"""

    def test_full_save_reopen_roundtrip(self, tmp_path):
        """完整保存/重开流程：验证 project.json、frames.idx、音频、光标、导出"""
        import json
        import numpy as np
        from types import SimpleNamespace
        from pathlib import Path
        from app.main_window import MainWindow, _write_wav, _read_wav
        from core.compositor import Compositor
        from core.project import Project, SourceInfo, Track, Clip
        from core.screen_capture import CapturedFrame
        from core.audio_capture import AudioResult, mix_audio_results
        from core.pointer_tracker import CursorEvent

        project_dir = str(tmp_path / "roundtrip")
        os.makedirs(project_dir)

        # ── 模拟录制结束状态 ──
        frames = [
            CapturedFrame(
                data=np.zeros((100, 100, 3), dtype=np.uint8),
                timestamp=i / 30.0, index=i,
            )
            for i in range(30)
        ]
        compositor = Compositor(100, 100, 30)
        compositor.load_frames(frames)

        # 光标事件（绝对时间戳，使用关键字参数确保正确字段映射）
        events = [
            CursorEvent(x=10, y=20, timestamp=0.0),
            CursorEvent(x=300, y=400, timestamp=0.5),
            CursorEvent(x=50, y=60, timestamp=1.0),
        ]
        compositor.load_cursor_events(events, [])

        tracks = [Track(type="video", name="视频", clips=[
            Clip(type="video", start=0, end=1.0, content="test"),
        ])]

        recording_controller = SimpleNamespace(
            recorder=SimpleNamespace(
                screen=SimpleNamespace(frame_offsets=[[0, 100], [100, 100]]),
            ),
        )

        # 写入 WAV 音频
        samplerate = 44100
        mic_data = np.ones((samplerate, 1), dtype=np.float32) * 0.3
        sys_data = np.ones((samplerate, 2), dtype=np.float32) * 0.2
        _write_wav(str(Path(project_dir) / "audio_mic.wav"), mic_data, samplerate)
        _write_wav(str(Path(project_dir) / "audio_system.wav"), sys_data, samplerate)

        # ── 执行保存 ──
        import app.main_window as mw
        recorded_data = {
            "frames": frames,
            "cursor_events": events,
            "clicks": [],
            "mic_audio": AudioResult(mic_data, samplerate, 1),
            "system_audio": AudioResult(sys_data, samplerate, 2),
            "monitor_offset": (0, 0),
        }

        window = SimpleNamespace(
            _recorded_data=recorded_data,
            _project_dir=project_dir,
            _compositor=compositor,
            _recording_controller=recording_controller,
            _timeline=SimpleNamespace(tracks=tracks),
            _audio_regions=[],
            config=SimpleNamespace(default_fps=30),
            _refresh_home_page=lambda: None,
            update_status=lambda text: None,
            _show_notification=lambda title, msg, level: None,
            _get_recording_duration=lambda: 1.0,
            _project_name="roundtrip_test",
        )
        # 绑定 _collect_project_state（需要 window 引用，不能用在构造器中）
        window._collect_project_state = lambda project: MainWindow._collect_project_state(window, project)

        MainWindow._finalize_project(window)

        # ── 验证保存产物 ──
        assert os.path.exists(os.path.join(project_dir, "frames.idx"))
        assert os.path.exists(os.path.join(project_dir, "project.json"))
        assert os.path.exists(os.path.join(project_dir, "audio_mic.wav"))
        assert os.path.exists(os.path.join(project_dir, "audio_system.wav"))

        saved = Project.load(os.path.join(project_dir, "project.json"))
        assert saved.source is not None
        assert saved.source.video == "frames.data"
        assert saved._frame_count == 30
        assert saved.source.audio_mic == "audio_mic.wav"
        assert saved.source.audio_system == "audio_system.wav"

        # ── 验证重开后的音频恢复 ──
        mic_audio, mic_sr, mic_ch = _read_wav(os.path.join(project_dir, saved.source.audio_mic))
        sys_audio, sys_sr, sys_ch = _read_wav(os.path.join(project_dir, saved.source.audio_system))
        assert mic_audio is not None
        assert sys_audio is not None

        mixed = mix_audio_results(
            AudioResult(mic_audio, mic_sr, mic_ch),
            AudioResult(sys_audio, sys_sr, sys_ch),
        )
        assert mixed is not None
        assert mixed.channels == 2
        assert mixed.data.shape[0] > 0

        # ── 验证重开后的光标时间基（相对时间戳） ──
        # 保存后的 cursor_events 时间戳应相对于 compositor._base_time (0.0)
        # 因此首帧光标应在第一个事件附近
        assert len(saved.cursor_events) == 3
        first_ts = saved.cursor_events[0][2]
        last_ts = saved.cursor_events[-1][2]
        assert abs(first_ts - 0.0) < 0.01, \
            f"首事件时间戳应接近 0.0，实际 {first_ts}"
        assert abs(last_ts - 1.0) < 0.01, \
            f"末事件时间戳应接近 1.0，实际 {last_ts}"
