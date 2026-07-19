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


def test_rebound_window_qshortcut_uses_real_events_and_safety_guards(
        qapp, monkeypatch):
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QKeySequence
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QDialog, QLineEdit, QStackedWidget, QWidget
    from app.config import AppConfig
    from app.main_window import MainWindow
    import ui.settings_dialog as settings_dialog_module

    class ShortcutIntegrationWindow(MainWindow):
        def _setup_navigation(self):
            self._home_interface = QWidget()
            self._stacked_widget = QStackedWidget()
            self._stacked_widget.addWidget(self._home_interface)
            self._stacked_widget.addWidget(self._editor_interface)
            self._stacked_widget.setCurrentWidget(self._editor_interface)
            self.setCentralWidget(self._stacked_widget)
            self._rebind_window_shortcuts()

        def _setup_tray(self):
            pass

        def _check_deps(self):
            pass

        def _update_ui_state(self):
            pass

    class AcceptedSettingsDialog:
        Accepted = QDialog.Accepted

        def __init__(self, config, _parent):
            bindings = config.shortcuts.copy()
            bindings["play_pause"] = "Ctrl+K"
            config.shortcuts = bindings

        def exec_(self):
            return self.Accepted

    monkeypatch.setattr(
        settings_dialog_module, "SettingsDialog", AcceptedSettingsDialog)
    window = ShortcutIntegrationWindow(AppConfig(projects_dir=str(Path.cwd())))
    calls = []
    window._on_play_toggle = lambda: calls.append("play")
    window.show()
    window.activateWindow()
    qapp.processEvents()

    window._on_open_settings()

    assert {
        shortcut.key().toString(QKeySequence.PortableText)
        for shortcut in window._window_shortcuts
    } == {"Ctrl+K", "Ctrl+Z", "Ctrl+Shift+Z", "Ctrl+Y"}
    QTest.keyClick(window, Qt.Key_Space)
    qapp.processEvents()
    assert calls == []
    QTest.keyClick(window, Qt.Key_K, Qt.ControlModifier)
    qapp.processEvents()
    assert calls == ["play"]

    window._stacked_widget.setCurrentWidget(window._home_interface)
    QTest.keyClick(window, Qt.Key_K, Qt.ControlModifier)
    qapp.processEvents()
    assert calls == ["play"]

    window._stacked_widget.setCurrentWidget(window._editor_interface)
    input_field = QLineEdit(window._editor_interface)
    input_field.show()
    input_field.setFocus()
    QTest.keyClick(input_field, Qt.Key_K, Qt.ControlModifier)
    qapp.processEvents()
    assert calls == ["play"]

    dialog = QDialog(window)
    dialog.setModal(True)
    dialog.show()
    qapp.processEvents()
    QTest.keyClick(dialog, Qt.Key_K, Qt.ControlModifier)
    qapp.processEvents()
    assert calls == ["play"]
    dialog.close()
    window.hide()
