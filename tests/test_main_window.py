"""主窗口生命周期的纯逻辑回归测试。"""

import os


def test_frame_update_shows_time_and_follows_playhead():
    from types import SimpleNamespace
    from app.main_window import MainWindow

    class FakeLabel:
        def setText(self, text):
            self.text = text

    class FakeTimeline:
        duration = 20.0
        playhead = 0.0

        def _time_to_x(self, seconds):
            return int(seconds * 30)

    class FakeScroll:
        def ensureVisible(self, x, y, xmargin, ymargin):
            self.args = (x, y, xmargin, ymargin)

    window = SimpleNamespace(
        _playback=SimpleNamespace(total_frames=600),
        _compositor=SimpleNamespace(fps=30),
        _frame_label=FakeLabel(),
        _time_label=FakeLabel(),
        _timeline=FakeTimeline(),
        _timeline_scroll=FakeScroll(),
    )

    MainWindow._update_frame_counter(window, 375)

    assert window._time_label.text == "00:12.500 / 00:20.000"
    assert window._timeline.playhead == 12.5
    assert window._timeline_scroll.args[0] == 375


def test_playback_receives_recorded_audio_and_video_edit_map(monkeypatch):
    from types import SimpleNamespace
    from core.project import Clip, Track
    from app.main_window import MainWindow
    import ui.preview_widget as preview_module

    captured = {}

    class FakePlayback:
        def __init__(self, widget, compositor, **kwargs):
            captured.update(kwargs)

        def set_on_frame_changed(self, callback):
            captured["callback"] = callback

    monkeypatch.setattr(preview_module, "PlaybackController", FakePlayback)
    audio = object()
    video_clip = Clip(type="video", start=0, end=2)
    window = SimpleNamespace(
        _preview=SimpleNamespace(set_fps=lambda fps: None),
            _compositor=SimpleNamespace(fps=30),
        _recorded_data={"audio": audio},
        _timeline=SimpleNamespace(tracks=[Track(type="video", clips=[video_clip])]),
        _update_frame_counter=lambda _idx: None,
    )

    MainWindow._create_playback_controller(window)

    assert captured["audio_result"] is audio
    assert captured["video_clips"] == [video_clip]


def test_recording_duration_prefers_capture_timestamps_over_frame_count():
    from types import SimpleNamespace
    from app.main_window import MainWindow

    window = SimpleNamespace(
        _compositor=SimpleNamespace(
            source_duration=10.0,
            _frames=list(range(300)),
            fps=60,
        )
    )

    assert MainWindow._get_recording_duration(window) == 10.0


def test_recording_start_error_restores_idle_state():
    import app.main_window as main_window_module
    from types import SimpleNamespace

    errors = []

    class FakeRecorder:
        def start_recording(self, project_dir=None):
            raise RuntimeError("microphone unavailable")

    class FakeWindow:
        _project_session = None
        _recording_controller = SimpleNamespace(
            start=lambda project_dir: (_ for _ in ()).throw(RuntimeError("microphone unavailable")),
        )
        _is_recording = True

        @property
        def _project_dir(self):
            return None

        def set_recording_state(self, value):
            self._is_recording = value

        def update_status(self, text):
            self.status = text

        def _show_notification(self, title, content, level):
            errors.append({"title": title, "content": content, "level": level})

        def _create_project_for_recording(self):
            pass

        def _cleanup_failed_recording(self):
            pass

    window = FakeWindow()

    main_window_module.MainWindow._on_recording_started(window)

    assert window._is_recording is False
    assert window.status == "● 录制启动失败"
    assert errors[0]["content"] == "microphone unavailable"


def test_timeline_signal_connection_is_idempotent():
    from app.main_window import MainWindow

    class FakeSignal:
        def __init__(self):
            self.slots = []

        def connect(self, slot):
            self.slots.append(slot)

        def disconnect(self, slot):
            if slot not in self.slots:
                raise TypeError
            self.slots.remove(slot)

    class FakeTimeline:
        playhead_changed = FakeSignal()
        zoom_double_clicked = FakeSignal()
        zoom_clip_selected = FakeSignal()
        clips_changed = FakeSignal()

    class FakeWindow:
        _timeline = FakeTimeline()

        def _on_timeline_seek(self):
            pass

        def _on_zoom_double_clicked(self):
            pass

        def _on_zoom_clip_selected(self):
            pass

        def _on_clips_changed(self):
            pass

    window = FakeWindow()
    MainWindow._connect_timeline_signals(window)
    MainWindow._connect_timeline_signals(window)

    assert len(window._timeline.playhead_changed.slots) == 1
    assert len(window._timeline.zoom_double_clicked.slots) == 1
    assert len(window._timeline.zoom_clip_selected.slots) == 1
    assert len(window._timeline.clips_changed.slots) == 1


def test_zoom_clip_selection_opens_that_clip_for_editing():
    from app.main_window import MainWindow
    from core.project import Clip

    clip = Clip(type="zoom", start=2.0, end=5.0,
                rect=[100, 100, 400, 200])

    class FakeWindow:
        def __init__(self):
            self.calls = []

        def _on_zoom_double_clicked(self, time_s, selected):
            self.calls.append((time_s, selected))

    window = FakeWindow()
    MainWindow._on_zoom_clip_selected(window, clip)

    assert window.calls == [(2.0, clip)]


def test_settings_cursor_style_choices_and_save(qapp, monkeypatch):
    from app.config import AppConfig
    from ui.settings_dialog import SettingsDialog

    config = AppConfig(cursor_style="ring")
    monkeypatch.setattr(config, "save", lambda: None)
    dialog = SettingsDialog(config)

    values = [dialog._cursor_style_combo.itemData(i)
              for i in range(dialog._cursor_style_combo.count())]
    assert values == ["dot", "ring", "spotlight", "arrow"]
    assert dialog._cursor_style_combo.currentData() == "ring"

    dialog._cursor_style_combo.setCurrentIndex(
        dialog._cursor_style_combo.findData("spotlight"))
    dialog._on_save()

    assert config.cursor_style == "spotlight"


def test_apply_cursor_config_updates_active_effect():
    from types import SimpleNamespace
    from app.main_window import MainWindow

    class FakeWindow:
        config = SimpleNamespace(
            cursor_size=48,
            cursor_theme="light",
            cursor_style="arrow",
            trail_enabled=False,
        )
        _cursor_effect = SimpleNamespace(
            cursor_size=0,
            cursor_theme="",
            cursor_style="",
            enabled={"trail": True},
        )

    window = FakeWindow()
    MainWindow._apply_cursor_config(window)

    assert window._cursor_effect.cursor_style == "arrow"
    assert window._cursor_effect.enabled["trail"] is False


def test_export_dialog_exposes_mp4_fps_and_bitrate(qapp, monkeypatch):
    import core.exporter
    from ui.export_dialog import ExportDialog

    monkeypatch.setattr(core.exporter, "is_gpu_available", lambda: False)
    dialog = ExportDialog(default_fps=60, default_bitrate="20M")

    assert dialog.mp4_fps_value == 60
    assert dialog.bitrate_value == "20M"

    dialog.mp4_fps.setValue(24)
    dialog.bitrate_mbps.setValue(8)

    assert dialog.mp4_fps_value == 24
    assert dialog.bitrate_value == "8M"


def test_main_window_forwards_mp4_fps_and_bitrate(monkeypatch):
    from types import SimpleNamespace
    import app.main_window as main_window_module
    from app.main_window import MainWindow

    class FakeSignal:
        def connect(self, _slot):
            pass

    class FakeDialog:
        Accepted = 1
        output_path = "/tmp/out.mp4"
        export_format = "mp4"
        is_custom_resolution = False
        resolution_max_height = 1080
        aspect_ratio = "native"
        quality = 1.0
        gif_fps_value = 15
        mp4_fps_value = 24
        bitrate_value = "8M"
        gif_loop_value = True
        use_gpu = False

        def __init__(self, _parent, _directory, default_fps,
                     default_bitrate):
            assert default_fps == 60
            assert default_bitrate == "20M"

        def exec_(self):
            return self.Accepted

    class FakeProgress:
        canceled = FakeSignal()

        def __init__(self, *_args):
            pass

        def setWindowTitle(self, _value):
            pass

        def setWindowModality(self, _value):
            pass

        def setAutoClose(self, _value):
            pass

        def setAutoReset(self, _value):
            pass

        def setValue(self, _value):
            pass

    captured = {}
    export_controller = SimpleNamespace(
        is_exporting=False,
        export_progress=FakeSignal(),
        start_export=lambda compositor, audio, settings: captured.update(
            compositor=compositor, audio=audio, settings=settings),
    )
    compositor = SimpleNamespace(
        frames=[object()], fps=60, crop_region=None)
    from functools import partial

    window = SimpleNamespace(
        _recorded_data=None,
        _compositor=compositor,
        _crop_active=False,
        _audio_regions=[],
        _btn_export=SimpleNamespace(setEnabled=lambda _value: None),
        _menu_export=SimpleNamespace(setEnabled=lambda _value: None),
        _export_controller=export_controller,
        config=SimpleNamespace(
            recordings_dir="/tmp", default_bitrate="20M"),
        _cancel_export=lambda: None,
        _show_notification=lambda *_args: None,
    )
    window._build_export_settings = partial(
        MainWindow._build_export_settings, window)
    window._start_export_progress = partial(
        MainWindow._start_export_progress, window)
    monkeypatch.setattr(main_window_module, "ExportDialog", FakeDialog)
    monkeypatch.setattr(main_window_module, "QProgressDialog", FakeProgress)

    MainWindow._on_export(window)

    assert captured["settings"].fps == 24
    assert captured["settings"].bitrate == "8M"


def test_export_entry_is_not_reentrant(monkeypatch):
    from types import SimpleNamespace
    from functools import partial
    import app.main_window as main_window_module
    from app.main_window import MainWindow

    progress_windows = []
    entry_states = []

    class FakeSignal:
        def connect(self, _slot):
            pass

    class FakeDialog:
        Accepted = 1
        output_path = "/tmp/out.mp4"
        export_format = "mp4"
        is_custom_resolution = False
        resolution_max_height = 1080
        aspect_ratio = "native"
        quality = 1.0
        gif_fps_value = 15
        mp4_fps_value = 30
        bitrate_value = "8M"
        gif_loop_value = True
        use_gpu = False

        def __init__(self, *_args):
            pass

        def exec_(self):
            return self.Accepted

    class FakeProgress:
        def __init__(self, *_args):
            progress_windows.append(self)
            self.canceled = FakeSignal()

        def setWindowTitle(self, _value):
            pass

        def setWindowModality(self, _value):
            pass

        def setAutoClose(self, _value):
            pass

        def setAutoReset(self, _value):
            pass

        def setValue(self, _value):
            pass

    class FakeController:
        def __init__(self):
            self.is_exporting = False
            self.start_calls = 0

        def start_export(self, *_args):
            self.start_calls += 1
            self.is_exporting = True

    controller = FakeController()
    window = SimpleNamespace(
        _recorded_data=None,
        _compositor=SimpleNamespace(
            frames=[object()], fps=30, crop_region=None),
        _crop_active=False,
        _audio_regions=[],
        _btn_export=SimpleNamespace(
            setEnabled=lambda value: entry_states.append(("button", value))),
        _menu_export=SimpleNamespace(
            setEnabled=lambda value: entry_states.append(("menu", value))),
        _export_controller=controller,
        config=SimpleNamespace(
            recordings_dir="/tmp", default_bitrate="8M"),
        _cancel_export=lambda: None,
        _show_notification=lambda *_args: None,
    )
    window._build_export_settings = partial(
        MainWindow._build_export_settings, window)
    window._start_export_progress = partial(
        MainWindow._start_export_progress, window)
    monkeypatch.setattr(main_window_module, "ExportDialog", FakeDialog)
    monkeypatch.setattr(main_window_module, "QProgressDialog", FakeProgress)

    MainWindow._on_export(window)
    MainWindow._on_export(window)

    assert controller.start_calls == 1
    assert len(progress_windows) == 1
    assert ("button", False) in entry_states
    assert ("menu", False) in entry_states


def test_normalize_project_path_converts_file_to_directory():
    from app.project_session import ProjectSession

    p = ProjectSession.normalize_path(
        os.path.join("home", "user", "Recordly", "projects", "test", "project.json"))
    expected = os.path.normpath(os.path.join("home", "user", "Recordly", "projects", "test"))
    assert p == expected

    p = ProjectSession.normalize_path(
        os.path.join("home", "user", "Recordly", "projects", "test"))
    expected = os.path.normpath(os.path.join("home", "user", "Recordly", "projects", "test"))
    assert p == expected

    p = ProjectSession.normalize_path(os.path.join("relative", "project.json"))
    expected = os.path.normpath("relative")
    assert p == expected
