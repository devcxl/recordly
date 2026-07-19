"""编辑器快捷键组合根的 offscreen 集成回归。"""

from pathlib import Path


class _MemorySettings:
    values = {}

    def __init__(self, *_args):
        pass

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def sync(self):
        pass


def _make_window(monkeypatch, config=None):
    from app.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_setup_navigation", lambda _window: None)
    monkeypatch.setattr(MainWindow, "_setup_tray", lambda _window: None)
    monkeypatch.setattr(MainWindow, "_check_deps", lambda _window: None)
    monkeypatch.setattr(MainWindow, "_update_ui_state", lambda _window: None)

    from app.config import AppConfig

    return MainWindow(config or AppConfig(projects_dir=str(Path.cwd())))


def _set_split_target(timeline):
    from core.project import Clip, Track

    timeline.set_tracks([Track(type="video", clips=[
        Clip(type="video", start=1.0, end=5.0),
    ])])
    timeline.playhead = 3.0


def test_settings_shortcut_save_rebinds_shared_timeline_and_persists(
        qapp, monkeypatch):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QDialog
    from app.config import AppConfig
    import app.config as config_module
    import ui.settings_dialog as settings_dialog_module

    _MemorySettings.values = {}
    monkeypatch.setattr(config_module, "QSettings", _MemorySettings)
    window = _make_window(monkeypatch)
    assert window._timeline._shortcut_registry is window._shortcut_registry

    class AcceptedSettingsDialog:
        Accepted = QDialog.Accepted

        def __init__(self, config, _parent):
            bindings = config.shortcuts.copy()
            bindings["split_at_playhead"] = "K"
            config.shortcuts = bindings
            config.save()

        def exec_(self):
            return self.Accepted

    monkeypatch.setattr(
        settings_dialog_module, "SettingsDialog", AcceptedSettingsDialog)
    window._on_open_settings()

    assert window._timeline._shortcut_registry is window._shortcut_registry
    assert window._shortcut_registry.binding("split_at_playhead") == "K"
    _set_split_target(window._timeline)
    QTest.keyClick(window._timeline, Qt.Key_X)
    assert len(window._timeline.tracks[0].clips) == 1
    QTest.keyClick(window._timeline, Qt.Key_K)
    assert len(window._timeline.tracks[0].clips) == 2

    restarted_config = AppConfig.load()
    assert restarted_config.shortcuts["split_at_playhead"] == "K"
    restarted_window = _make_window(monkeypatch, restarted_config)
    assert restarted_window._timeline._shortcut_registry is restarted_window._shortcut_registry
    _set_split_target(restarted_window._timeline)
    QTest.keyClick(restarted_window._timeline, Qt.Key_X)
    assert len(restarted_window._timeline.tracks[0].clips) == 1
    QTest.keyClick(restarted_window._timeline, Qt.Key_K)
    assert len(restarted_window._timeline.tracks[0].clips) == 2


def test_window_shortcut_dispatch_keeps_editor_safety_guard(qapp, monkeypatch):
    from types import MethodType, SimpleNamespace
    import app.main_window as main_window_module
    from app.main_window import MainWindow

    editor = object()
    calls = []
    window = SimpleNamespace(
        _editor_interface=editor,
        _stacked_widget=SimpleNamespace(currentWidget=lambda: editor),
    )
    window._is_editor_active_and_safe = MethodType(
        MainWindow._is_editor_active_and_safe, window)
    monkeypatch.setattr(
        main_window_module.QApplication, "activeWindow", lambda: window)
    monkeypatch.setattr(
        main_window_module.QApplication, "activeModalWidget", lambda: None)
    monkeypatch.setattr(
        main_window_module.QApplication, "activePopupWidget", lambda: None)
    monkeypatch.setattr(
        main_window_module.QApplication, "focusWidget", lambda: None)

    MainWindow._dispatch_window_shortcut(window, [lambda: calls.append("run")])
    assert calls == ["run"]

    monkeypatch.setattr(
        main_window_module.QApplication, "activeModalWidget", lambda: object())
    MainWindow._dispatch_window_shortcut(window, [lambda: calls.append("blocked")])
    assert calls == ["run"]
