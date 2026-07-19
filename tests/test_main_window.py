"""主窗口生命周期的纯逻辑回归测试。"""

import os

import pytest


class _FakeSignal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot=None):
        if slot is None:
            self.slots.clear()
        elif slot in self.slots:
            self.slots.remove(slot)
        else:
            raise TypeError

    def emit(self, *args):
        for slot in self.slots:
            slot(*args)


def _native_shortcut_text(*portable_texts):
    from PyQt5.QtGui import QKeySequence

    return " / ".join(
        QKeySequence(portable_text, QKeySequence.PortableText).toString(
            QKeySequence.NativeText)
        for portable_text in portable_texts
    )


def _make_shortcut_window(bindings):
    from app.main_window import MainWindow
    from core.shortcuts import ShortcutRegistry
    from PyQt5.QtWidgets import QMainWindow

    class ShortcutWindow(QMainWindow):
        _rebind_window_shortcuts = MainWindow._rebind_window_shortcuts
        _dispatch_window_shortcut = MainWindow._dispatch_window_shortcut
        _is_editor_active_and_safe = MainWindow._is_editor_active_and_safe

        def __init__(self):
            super().__init__()
            self.calls = []
            self._shortcut_registry = ShortcutRegistry(bindings)
            self._editor_interface = object()
            self._stacked_widget = type(
                "Stack", (), {"currentWidget": lambda stack: self._editor_interface}
            )()

        def _on_play_toggle(self):
            self.calls.append("play_pause")

        def _on_undo(self):
            self.calls.append("undo")

        def _on_redo(self):
            self.calls.append("redo")

    return ShortcutWindow()


def _allow_editor_shortcuts(monkeypatch, window):
    import app.main_window as main_window_module

    monkeypatch.setattr(main_window_module.QApplication, "activeWindow", lambda: window)
    monkeypatch.setattr(main_window_module.QApplication, "activeModalWidget", lambda: None)
    monkeypatch.setattr(main_window_module.QApplication, "activePopupWidget", lambda: None)
    monkeypatch.setattr(main_window_module.QApplication, "focusWidget", lambda: None)


def test_window_shortcuts_group_bindings_with_context_without_auto_repeat(qapp):
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QKeySequence
    from core.shortcuts import ShortcutRegistry

    bindings = ShortcutRegistry().bindings()
    bindings.update({
        "play_pause": "Ctrl+K",
        "undo": "Ctrl+K",
        "redo": "Ctrl+Shift+K",
        "redo_alt": "Ctrl+Shift+K",
    })
    window = _make_shortcut_window(bindings)

    window._rebind_window_shortcuts()

    assert len(window._window_shortcuts) == 2
    assert {
        shortcut.key().toString(QKeySequence.PortableText)
        for shortcut in window._window_shortcuts
    } == {"Ctrl+K", "Ctrl+Shift+K"}
    assert all(shortcut.context() == Qt.WindowShortcut
               for shortcut in window._window_shortcuts)
    assert all(shortcut.autoRepeat() is False
               for shortcut in window._window_shortcuts)


def test_window_shortcuts_dispatch_grouped_actions_in_catalog_order(qapp, monkeypatch):
    from core.shortcuts import ShortcutRegistry

    bindings = ShortcutRegistry().bindings()
    for action_id in ("play_pause", "undo", "redo", "redo_alt"):
        bindings[action_id] = "Ctrl+K"
    window = _make_shortcut_window(bindings)
    _allow_editor_shortcuts(monkeypatch, window)

    window._rebind_window_shortcuts()
    window._window_shortcuts[0].activated.emit()

    assert window.calls == ["play_pause", "undo", "redo", "redo"]


def test_rebind_disables_old_shortcuts_and_activates_new_binding(qapp, monkeypatch):
    from PyQt5.QtGui import QKeySequence
    from core.shortcuts import ShortcutRegistry

    window = _make_shortcut_window(ShortcutRegistry().bindings())
    _allow_editor_shortcuts(monkeypatch, window)
    window._rebind_window_shortcuts()
    old_shortcut = next(
        shortcut for shortcut in window._window_shortcuts
        if shortcut.key().toString(QKeySequence.PortableText) == "Space"
    )
    bindings = window._shortcut_registry.bindings()
    bindings["play_pause"] = "Ctrl+K"
    assert window._shortcut_registry.replace_bindings(bindings).ok

    window._rebind_window_shortcuts()
    new_shortcut = next(
        shortcut for shortcut in window._window_shortcuts
        if shortcut.key().toString(QKeySequence.PortableText) == "Ctrl+K"
    )
    old_shortcut.activated.emit()
    new_shortcut.activated.emit()

    assert old_shortcut.isEnabled() is False
    assert window.calls == ["play_pause"]


def test_settings_acceptance_updates_shared_registry_and_rebinds(monkeypatch):
    from types import SimpleNamespace
    from app.main_window import MainWindow
    from core.shortcuts import ShortcutRegistry
    import ui.settings_dialog as settings_dialog_module

    updated_bindings = ShortcutRegistry().bindings()
    updated_bindings["undo"] = "Ctrl+K"
    calls = []

    class AcceptedDialog:
        Accepted = 1

        def __init__(self, config, _parent):
            config.shortcuts = updated_bindings

        def exec_(self):
            return self.Accepted

    registry = ShortcutRegistry()
    window = SimpleNamespace(
        config=SimpleNamespace(
            shortcuts=registry.bindings(),
            default_fps=60,
            preview_quality=0.75,
        ),
        _shortcut_registry=registry,
        _rebind_window_shortcuts=lambda: calls.append("rebind"),
        _refresh_undo_redo_state=lambda: calls.append("refresh"),
        _compositor=SimpleNamespace(
            fps=0,
            set_preview_quality=lambda value: calls.append(("quality", value)),
        ),
        _is_recording=False,
        _recording_controller=SimpleNamespace(
            recorder=SimpleNamespace(set_target_fps=lambda value: calls.append(("fps", value))),
        ),
        _apply_cursor_config=lambda: calls.append("cursor"),
    )
    monkeypatch.setattr(settings_dialog_module, "SettingsDialog", AcceptedDialog)

    MainWindow._on_open_settings(window)

    assert window._shortcut_registry.binding("undo") == "Ctrl+K"
    assert window.config.shortcuts == updated_bindings
    assert calls[:2] == ["rebind", "refresh"]


@pytest.mark.parametrize("blocked_by", ["home", "inactive", "modal", "popup"])
def test_space_shortcut_ignores_non_editor_contexts(qapp, monkeypatch, blocked_by):
    from types import SimpleNamespace, MethodType
    import app.main_window as main_window_module
    from app.main_window import MainWindow

    editor = object()
    window = SimpleNamespace(
        _editor_interface=editor,
        _on_play_toggle=lambda: pytest.fail("不应触发播放"),
    )
    window._is_editor_active_and_safe = MethodType(
        MainWindow._is_editor_active_and_safe, window)
    current_widget = object() if blocked_by == "home" else editor
    window._stacked_widget = SimpleNamespace(
        currentWidget=lambda: current_widget
    )
    active_window = object() if blocked_by == "inactive" else window
    modal = object() if blocked_by == "modal" else None
    popup = object() if blocked_by == "popup" else None
    monkeypatch.setattr(
        main_window_module.QApplication, "activeWindow", lambda: active_window
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activeModalWidget", lambda: modal
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activePopupWidget", lambda: popup
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "focusWidget", lambda: None
    )

    MainWindow._dispatch_window_shortcut(window, [window._on_play_toggle])


@pytest.mark.parametrize(
    "widget_type",
    ["QLineEdit", "QTextEdit", "QPlainTextEdit", "QSpinBox", "QComboBox"],
)
def test_space_shortcut_ignores_input_focus(qapp, monkeypatch, widget_type):
    from types import SimpleNamespace, MethodType
    import app.main_window as main_window_module
    from app.main_window import MainWindow
    from PyQt5 import QtWidgets

    editor = object()
    window = SimpleNamespace(
        _editor_interface=editor,
        _stacked_widget=SimpleNamespace(currentWidget=lambda: editor),
        _on_play_toggle=lambda: pytest.fail("不应触发播放"),
    )
    window._is_editor_active_and_safe = MethodType(
        MainWindow._is_editor_active_and_safe, window)
    focus_widget = getattr(QtWidgets, widget_type)()
    monkeypatch.setattr(
        main_window_module.QApplication, "activeWindow", lambda: window
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activeModalWidget", lambda: None
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activePopupWidget", lambda: None
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "focusWidget", lambda: focus_widget
    )

    MainWindow._dispatch_window_shortcut(window, [window._on_play_toggle])


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

    class FakeTimeline:
        playhead_changed = _FakeSignal()
        zoom_double_clicked = _FakeSignal()
        zoom_add_requested = _FakeSignal()
        zoom_clip_selected = _FakeSignal()
        clips_changed = _FakeSignal()
        status_message = _FakeSignal()
        playhead_seek_play = _FakeSignal()

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

        def _on_playhead_seek_play(self):
            pass

        def _refresh_undo_redo_state(self):
            pass

        def update_status(self, _message):
            pass

    window = FakeWindow()
    MainWindow._connect_timeline_signals(window)
    MainWindow._connect_timeline_signals(window)

    assert len(window._timeline.playhead_changed.slots) == 1
    assert len(window._timeline.zoom_double_clicked.slots) == 1
    assert window._timeline.zoom_add_requested.slots == [
        window._on_zoom_double_clicked
    ]
    assert len(window._timeline.zoom_clip_selected.slots) == 1
    assert len(window._timeline.clips_changed.slots) == 2
    assert window._timeline.status_message.slots == [window.update_status]


@pytest.mark.parametrize(
    ("start", "expected_end"),
    [(3.25, 5.25), (9.25, 10.0)],
)
def test_zoom_blank_creation_uses_add_clip_defaults_and_returned_object(
        start, expected_end):
    from dataclasses import asdict
    from types import SimpleNamespace
    from app.main_window import MainWindow
    from core.project import Clip, Track

    class FakeTimeline:
        duration = 10.0

        def __init__(self):
            self.tracks = [Track(type="video"), Track(type="zoom")]
            self.add_calls = []

        def add_clip(self, track_index, requested):
            actual = Clip(**asdict(requested))
            self.tracks[track_index].clips.append(actual)
            self.add_calls.append((track_index, requested, actual))
            return actual

        def update(self):
            pass

    timeline = FakeTimeline()
    loaded = []
    shown = []
    seeks = []
    preview = SimpleNamespace(
        overlay=SimpleNamespace(rect_changed=_FakeSignal()),
        show_zoom_rect=lambda *args: shown.append(args),
    )
    window = SimpleNamespace(
        config=SimpleNamespace(zoom_rect_ratio=0.4),
        _timeline=timeline,
        _compositor=SimpleNamespace(
            width=1600,
            height=900,
            load_manual_zoom_clips=lambda clips: loaded.append(clips),
        ),
        _playback=SimpleNamespace(
            current_frame=17,
            seek=lambda frame: seeks.append(frame),
        ),
        _preview=preview,
        _editing_zoom_clip=None,
        _on_zoom_rect_changed=lambda *_args: None,
    )

    MainWindow._on_zoom_double_clicked(window, start)

    track_index, requested, actual = timeline.add_calls[0]
    assert track_index == 1
    assert (requested.start, requested.end) == (start, expected_end)
    assert requested.content == "手动缩放"
    assert requested.transition_duration == 0.4
    assert requested.rect == [480, 270, 640, 360]
    assert window._editing_zoom_clip is actual
    assert actual is not requested
    assert loaded[-1] == [actual]
    assert shown == [(actual.rect, 1600, 900)]
    assert seeks == [17]


def test_existing_zoom_clip_only_fills_empty_rect_without_add_command():
    from types import SimpleNamespace
    from app.main_window import MainWindow
    from core.project import Clip, Track

    clip = Clip(type="zoom", start=1.0, end=3.0)
    timeline = SimpleNamespace(
        tracks=[Track(type="zoom", clips=[clip])],
        add_clip=lambda *_args: pytest.fail("已有 Clip 不应创建命令"),
        update=lambda: None,
    )
    window = SimpleNamespace(
        config=SimpleNamespace(zoom_rect_ratio=0.5),
        _timeline=timeline,
        _compositor=SimpleNamespace(
            width=1920,
            height=1080,
            load_manual_zoom_clips=lambda _clips: None,
        ),
        _playback=None,
        _preview=SimpleNamespace(
            overlay=SimpleNamespace(rect_changed=_FakeSignal()),
            show_zoom_rect=lambda *_args: None,
        ),
        _editing_zoom_clip=None,
        _on_zoom_rect_changed=lambda *_args: None,
    )

    MainWindow._on_zoom_double_clicked(window, clip.start, clip)

    assert clip.rect == [480, 270, 960, 540]
    assert window._editing_zoom_clip is clip


def test_zoom_add_undo_hides_overlay_and_redo_restores_full_clip(qapp):
    from dataclasses import asdict
    from types import SimpleNamespace
    from app.main_window import MainWindow
    from core.project import Clip, Track
    from ui.timeline import TimelineWidget

    class FakeCompositor:
        width = 1280
        height = 720

        def load_manual_zoom_clips(self, clips):
            self.zoom_clips = clips

        def load_clips(self, clips):
            self.video_clips = clips

    class FakePreview:
        def __init__(self):
            self.overlay = SimpleNamespace(rect_changed=_FakeSignal())
            self.hidden = 0

        def show_zoom_rect(self, *_args):
            pass

        def hide_zoom_rect(self):
            self.hidden += 1

    timeline = TimelineWidget()
    timeline.set_tracks([
        Track(type="video", clips=[Clip(type="video", start=0, end=10)]),
        Track(type="zoom"),
    ])
    timeline.duration = 10.0
    preview = FakePreview()
    window = SimpleNamespace(
        config=SimpleNamespace(zoom_rect_ratio=0.5),
        _timeline=timeline,
        _compositor=FakeCompositor(),
        _playback=None,
        _preview=preview,
        _editing_zoom_clip=None,
        _audio_regions=[],
        _on_zoom_rect_changed=lambda *_args: None,
    )

    MainWindow._on_zoom_double_clicked(window, 2.0)
    created = window._editing_zoom_clip
    assert timeline.can_undo is True
    assert created is timeline.tracks[1].clips[0]

    created.rect = [20, 30, 800, 450]
    created.transition_duration = 0.8
    expected = asdict(created)
    timeline.clips_changed.connect(
        lambda: MainWindow._on_clips_changed(window))

    timeline.undo()
    assert timeline.tracks[1].clips == []
    assert window._editing_zoom_clip is None
    assert preview.hidden == 1

    timeline.redo()
    restored = timeline.tracks[1].clips[0]
    assert asdict(restored) == expected
    assert window._compositor.zoom_clips == [restored]


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


# ── playhead_seek_play 集成测试 ──────────────────────────


def test_playhead_seek_play_ignores_empty_frames(monkeypatch):
    """无帧时 playhead_seek_play 静默忽略，不触发 QTimer"""
    import app.main_window as main_window_module
    from app.main_window import MainWindow
    from types import SimpleNamespace

    timer_calls = []
    monkeypatch.setattr(main_window_module.QTimer, "singleShot",
                        lambda ms, cb: timer_calls.append((ms, cb)))

    window = SimpleNamespace(
        _compositor=SimpleNamespace(frames=[]),
    )

    MainWindow._on_playhead_seek_play(window, 2.5)

    assert len(timer_calls) == 0


def test_playhead_seek_play_ignores_input_focus(monkeypatch):
    """焦点在输入控件时 playhead_seek_play 静默忽略"""
    import app.main_window as main_window_module
    from app.main_window import MainWindow
    from types import SimpleNamespace
    from PyQt5 import QtWidgets

    timer_calls = []
    monkeypatch.setattr(main_window_module.QTimer, "singleShot",
                        lambda ms, cb: timer_calls.append((ms, cb)))
    monkeypatch.setattr(
        main_window_module.QApplication, "activeModalWidget", lambda: None)
    monkeypatch.setattr(
        main_window_module.QApplication, "activePopupWidget", lambda: None)
    monkeypatch.setattr(
        main_window_module.QApplication, "focusWidget",
        lambda: QtWidgets.QLineEdit())

    editor = object()
    window = SimpleNamespace(
        _compositor=SimpleNamespace(frames=[object()]),
        _stacked_widget=SimpleNamespace(currentWidget=lambda: editor),
        _editor_interface=editor,
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activeWindow", lambda: window)

    MainWindow._on_playhead_seek_play(window, 2.5)

    assert len(timer_calls) == 0


def test_playhead_seek_play_schedules_delayed_playback(monkeypatch):
    """正常路径：播放头位置已设，QTimer.singleShot(0, ...) 被调度"""
    import app.main_window as main_window_module
    from app.main_window import MainWindow
    from types import SimpleNamespace

    timer_calls = []
    monkeypatch.setattr(main_window_module.QTimer, "singleShot",
                        lambda ms, cb: timer_calls.append((ms, cb)))
    monkeypatch.setattr(
        main_window_module.QApplication, "activeModalWidget", lambda: None)
    monkeypatch.setattr(
        main_window_module.QApplication, "activePopupWidget", lambda: None)
    monkeypatch.setattr(
        main_window_module.QApplication, "focusWidget", lambda: None)

    class FakeTimeline:
        def __init__(self):
            self.playhead = 0.0

    timeline = FakeTimeline()
    editor = object()

    window = SimpleNamespace(
        _compositor=SimpleNamespace(frames=[object()], fps=30),
        _timeline=timeline,
        _playback=SimpleNamespace(is_paused=True),
        _btn_play=SimpleNamespace(setText=lambda t: None,
                                   setToolTip=lambda t: None),
        _stacked_widget=SimpleNamespace(currentWidget=lambda: editor),
        _editor_interface=editor,
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activeWindow", lambda: window)

    MainWindow._on_playhead_seek_play(window, 2.5)

    assert len(timer_calls) == 1
    assert timer_calls[0][0] == 0
    assert callable(timer_calls[0][1])
    assert timeline.playhead == 2.5


def test_start_playback_at_initiates_playback(monkeypatch):
    """_start_playback_at：停止当前播放 → 从指定秒数开始播放"""
    import app.main_window as main_window_module
    from app.main_window import MainWindow
    from types import SimpleNamespace

    play_calls = []
    pause_calls = []
    btn_texts = []

    class FakePlayback:
        is_paused = False

        def play(self, frame):
            play_calls.append(frame)

        def pause(self):
            pause_calls.append(True)

    playback = FakePlayback()

    window = SimpleNamespace(
        _compositor=SimpleNamespace(frames=[object()], fps=30),
        _playback=playback,
        _btn_play=SimpleNamespace(
            setText=lambda t: btn_texts.append(t),
            setToolTip=lambda t: None),
    )

    MainWindow._start_playback_at(window, 2.5)

    assert pause_calls == [True]          # 先停止当前播放
    assert play_calls == [75]             # 2.5 * 30
    assert "⏸" in btn_texts
# ── undo/redo 快捷键、编辑菜单、工具栏按钮测试 ──────────


class _FakeUndoCmd:
    """用于测试 undo/redo description 的假命令对象"""
    def __init__(self, desc="测试撤销"):
        self._desc = desc

    def description(self) -> str:
        return self._desc


def test_timeline_undo_redo_descriptions(qapp):
    """TimelineWidget 的 undo_description / redo_description 属性返回栈顶命令描述"""
    from ui.timeline import TimelineWidget
    from core.project import Clip, Track

    timeline = TimelineWidget()
    timeline.set_tracks([
        Track(type="video", clips=[Clip(type="video", start=0, end=10)]),
    ])
    timeline.duration = 10.0

    # 初始状态：无操作历史
    assert timeline.can_undo is False
    assert timeline.undo_description == ""
    assert timeline.can_redo is False
    assert timeline.redo_description == ""

    # 将假命令推入栈中（直接操作私有栈模拟撤销场景）
    timeline._undo_stack.append(_FakeUndoCmd("添加片段"))
    assert timeline.can_undo is True
    assert timeline.undo_description == "添加片段"
    assert timeline.can_redo is False
    assert timeline.redo_description == ""

    # 模拟撤销后再推入 redo 栈
    cmd = timeline._undo_stack.pop()
    timeline._redo_stack.append(cmd)
    assert timeline.can_undo is False
    assert timeline.undo_description == ""
    assert timeline.can_redo is True
    assert timeline.redo_description == "添加片段"


@pytest.mark.parametrize("blocked_by", ["home", "inactive", "modal", "popup"])
def test_is_editor_active_and_safe_rejects_blocked_contexts(
        qapp, monkeypatch, blocked_by):
    """守卫方法在非编辑器语境下返回 False"""
    from types import SimpleNamespace
    import app.main_window as main_window_module
    from app.main_window import MainWindow

    editor = SimpleNamespace()
    window = SimpleNamespace(
        _editor_interface=editor,
        _stacked_widget=SimpleNamespace(
            currentWidget=lambda: (
                editor if blocked_by != "home" else SimpleNamespace()
            ),
        ),
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activeWindow",
        lambda: window if blocked_by != "inactive" else SimpleNamespace(),
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activeModalWidget",
        lambda: SimpleNamespace() if blocked_by == "modal" else None,
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activePopupWidget",
        lambda: SimpleNamespace() if blocked_by == "popup" else None,
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "focusWidget", lambda: None,
    )

    assert MainWindow._is_editor_active_and_safe(window) is False


@pytest.mark.parametrize("widget_type", [
    "QLineEdit", "QTextEdit", "QPlainTextEdit", "QSpinBox", "QComboBox",
])
def test_is_editor_active_and_safe_rejects_input_focus(qapp, monkeypatch, widget_type):
    """焦点在输入控件上时守卫返回 False"""
    from types import SimpleNamespace
    import app.main_window as main_window_module
    from app.main_window import MainWindow
    from PyQt5 import QtWidgets

    editor = SimpleNamespace()
    window = SimpleNamespace(
        _editor_interface=editor,
        _stacked_widget=SimpleNamespace(currentWidget=lambda: editor),
    )
    focus_widget = getattr(QtWidgets, widget_type)()
    monkeypatch.setattr(
        main_window_module.QApplication, "activeWindow", lambda: window,
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activeModalWidget", lambda: None,
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activePopupWidget", lambda: None,
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "focusWidget", lambda: focus_widget,
    )

    assert MainWindow._is_editor_active_and_safe(window) is False


def test_is_editor_active_and_safe_allows_safe_editor(qapp, monkeypatch):
    """编辑器在前台且无输入焦点时返回 True"""
    from types import SimpleNamespace
    import app.main_window as main_window_module
    from app.main_window import MainWindow

    editor = SimpleNamespace()
    window = SimpleNamespace(
        _editor_interface=editor,
        _stacked_widget=SimpleNamespace(currentWidget=lambda: editor),
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activeWindow", lambda: window,
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activeModalWidget", lambda: None,
    )
    monkeypatch.setattr(
        main_window_module.QApplication, "activePopupWidget", lambda: None,
    )
    # focusWidget 返回 None（或一个不排除的控件比如 QLabel）→ 安全
    monkeypatch.setattr(
        main_window_module.QApplication, "focusWidget", lambda: None,
    )

    assert MainWindow._is_editor_active_and_safe(window) is True


def test_undo_redo_menu_items_show_shortcuts_and_descriptions():
    """编辑菜单包含 undo/redo action，支持快捷键和动态文本更新"""
    from types import MethodType, SimpleNamespace
    from app.main_window import MainWindow
    from core.shortcuts import ShortcutRegistry
    from PyQt5.QtWidgets import QMenuBar, QWidget, QToolButton

    menubar = QMenuBar()
    test_window = QWidget()
    bindings = ShortcutRegistry().bindings()
    bindings.update({"undo": "Ctrl+K", "redo": "Ctrl+L", "redo_alt": "Ctrl+M"})
    test_window._shortcut_registry = ShortcutRegistry(bindings)
    test_window._shortcut_text = MethodType(MainWindow._shortcut_text, test_window)
    test_window._undo_action = None
    test_window._redo_action = None
    test_window._on_undo = lambda: None
    test_window._on_redo = lambda: None
    test_window._timeline = SimpleNamespace(
        can_undo=True,
        can_redo=True,
        undo_description="添加片段",
        redo_description="删除片段",
    )
    # 创建假的按钮避免 _refresh_undo_redo_state 报错
    test_window._btn_undo = QToolButton()
    test_window._btn_redo = QToolButton()

    # 创建编辑菜单
    MainWindow._setup_edit_menu(test_window, menubar)

    # 验证菜单位置和 action 属性
    edit_menu = None
    for action in menubar.actions():
        if action.text() == "编辑":
            edit_menu = action.menu()
            break
    assert edit_menu is not None

    actions = edit_menu.actions()
    assert len(actions) >= 2

    undo_act = test_window._undo_action
    redo_act = test_window._redo_action
    assert undo_act is not None
    assert redo_act is not None

    # 初始文本使用注册表中的当前键位
    assert undo_act.text() == f"撤销\t{_native_shortcut_text('Ctrl+K')}"
    assert redo_act.text() == (
        f"重做\t{_native_shortcut_text('Ctrl+L', 'Ctrl+M')}")

    # 调用 _refresh_undo_redo_state 验证动态文本更新（含 \t 快捷键提示）
    MainWindow._refresh_undo_redo_state(test_window)

    assert undo_act.isEnabled() is True
    assert "添加片段" in undo_act.text()
    assert "撤销" in undo_act.text()
    assert f"\t{_native_shortcut_text('Ctrl+K')}" in undo_act.text()
    assert redo_act.isEnabled() is True
    assert "删除片段" in redo_act.text()
    assert "重做" in redo_act.text()
    assert f"\t{_native_shortcut_text('Ctrl+L', 'Ctrl+M')}" in redo_act.text()


def test_refresh_undo_redo_state_updates_menu_and_toolbar():
    """_refresh_undo_redo_state 根据 can_undo/can_redo 更新所有 UI 元素"""
    from types import MethodType, SimpleNamespace
    from app.main_window import MainWindow
    from core.shortcuts import ShortcutRegistry

    logs = {}

    class FakeAction:
        def __init__(self, name):
            self._name = name
            self._enabled = False
            self._text = ""

        def setEnabled(self, v):
            self._enabled = v
            logs[f"{self._name}.enabled"] = v

        def setText(self, t):
            self._text = t
            logs[f"{self._name}.text"] = t

        def isEnabled(self):
            return self._enabled

        def text(self):
            return self._text

    class FakeButton:
        def __init__(self, name):
            self._name = name
            self._enabled = False
            self._tip = ""

        def setEnabled(self, v):
            self._enabled = v
            logs[f"{self._name}.enabled"] = v

        def setToolTip(self, t):
            self._tip = t
            logs[f"{self._name}.tip"] = t

    bindings = ShortcutRegistry().bindings()
    bindings.update({"undo": "Ctrl+K", "redo": "Ctrl+L", "redo_alt": "Ctrl+M"})
    window = SimpleNamespace(
        _timeline=SimpleNamespace(
            can_undo=True,
            can_redo=False,
            undo_description="移动片段",
            redo_description="",
        ),
        _undo_action=FakeAction("undo"),
        _redo_action=FakeAction("redo"),
        _btn_undo=FakeButton("btn_undo"),
        _btn_redo=FakeButton("btn_redo"),
        _shortcut_registry=ShortcutRegistry(bindings),
    )
    window._shortcut_text = MethodType(MainWindow._shortcut_text, window)

    MainWindow._refresh_undo_redo_state(window)

    assert logs["undo.enabled"] is True
    assert "移动片段" in logs["undo.text"]
    assert "撤销" in logs["undo.text"]
    assert logs["redo.enabled"] is False
    assert logs["redo.text"] == (
        f"重做\t{_native_shortcut_text('Ctrl+L', 'Ctrl+M')}")
    assert logs["btn_undo.enabled"] is True
    assert "移动片段" in logs["btn_undo.tip"]
    assert _native_shortcut_text("Ctrl+K") in logs["btn_undo.tip"]
    assert logs["btn_redo.enabled"] is False
    assert logs["btn_redo.tip"] == (
        f"重做 ({_native_shortcut_text('Ctrl+L', 'Ctrl+M')})")


def test_undo_redo_toolbar_buttons_exist_and_positioned_before_playback():
    """验证工具栏包含 undo/redo 按钮，且在播放控制按钮之前"""
    from types import MethodType, SimpleNamespace
    from app.main_window import MainWindow
    from core.shortcuts import ShortcutRegistry
    from PyQt5.QtWidgets import QToolBar, QWidget, QToolButton

    # 使用真实 QToolBar 来追踪添加的控件
    toolbar = QToolBar()
    parent = QWidget()

    # 创建 self 对象，让 _add_undo_redo_toolbar_buttons 创建真实按钮
    class FakeWindow:
        pass

    window = FakeWindow()
    window._toolbar = toolbar
    window._btn_undo = None
    window._btn_redo = None
    window._on_undo = lambda: None
    window._on_redo = lambda: None
    window._shortcut_registry = ShortcutRegistry()
    window._shortcut_text = MethodType(MainWindow._shortcut_text, window)

    MainWindow._add_undo_redo_toolbar_buttons(window)

    # 验证按钮被创建
    assert isinstance(window._btn_undo, QToolButton)
    assert isinstance(window._btn_redo, QToolButton)
    assert window._btn_undo.text() == "↩"
    assert window._btn_redo.text() == "↪"
    assert window._btn_undo.isEnabled() is False
    assert window._btn_redo.isEnabled() is False
    assert _native_shortcut_text("Ctrl+Z") in window._btn_undo.toolTip()
    assert _native_shortcut_text(
        "Ctrl+Shift+Z", "Ctrl+Y") in window._btn_redo.toolTip()

    # 验证按钮被添加到 toolbar
    actions = toolbar.actions()
    assert len(actions) == 3  # undo button, redo button, separator
    # 分隔线在最后
    assert actions[-1].isSeparator() is True
