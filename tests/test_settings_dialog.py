"""设置对话框快捷键页的 GUI 回归测试。"""


def test_shortcut_tab_lists_all_actions_with_native_text(qapp):
    from PyQt5.QtGui import QKeySequence

    from app.config import AppConfig
    from core.shortcuts import ShortcutRegistry
    from ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(AppConfig())
    actions = ShortcutRegistry().actions()

    assert dialog.minimumWidth() >= 720
    assert dialog.minimumHeight() >= 560
    assert dialog._shortcut_table.rowCount() == len(actions) == 12
    assert dialog._shortcut_table.verticalScrollBar() is not None
    assert [
        dialog._shortcut_table.horizontalHeaderItem(column).text()
        for column in range(dialog._shortcut_table.columnCount())
    ] == ["分类", "操作", "当前快捷键", "编辑", "恢复默认"]

    for row, action in enumerate(actions):
        assert dialog._shortcut_table.item(row, 0).text() == action.category
        assert dialog._shortcut_table.item(row, 1).text() == action.display_name
        assert dialog._shortcut_table.item(row, 2).text() == QKeySequence(
            action.default_keys,
            QKeySequence.PortableText,
        ).toString(QKeySequence.NativeText)


def test_shortcut_capture_rejects_modifiers_and_cancels_with_escape(qapp):
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent
    from PyQt5.QtWidgets import QDialog

    from core.shortcuts import ShortcutRegistry
    from ui.settings_dialog import _ShortcutCaptureDialog

    capture = _ShortcutCaptureDialog(ShortcutRegistry(), "undo")
    capture.show()
    qapp.processEvents()

    assert capture.focusWidget() is capture._sequence_label

    qapp.sendEvent(capture.focusWidget(), QKeyEvent(
        QEvent.KeyPress,
        Qt.Key_Control,
        Qt.ControlModifier,
    ))

    assert capture._portable_text is None
    assert capture._error_label.text() == "请按下包含非修饰键的快捷键"

    qapp.sendEvent(capture.focusWidget(), QKeyEvent(
        QEvent.KeyPress,
        Qt.Key_K,
        Qt.ControlModifier | Qt.ShiftModifier,
    ))
    capture._on_accept()

    assert capture.result() == QDialog.Accepted
    assert capture._portable_text == "Ctrl+Shift+K"

    capture.setResult(QDialog.Accepted)
    capture.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))

    assert capture.result() == QDialog.Rejected


def test_shortcut_capture_keeps_draft_on_conflict_or_invalid_key(qapp):
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent

    from core.shortcuts import ShortcutRegistry
    from ui.settings_dialog import _ShortcutCaptureDialog

    registry = ShortcutRegistry()
    conflict_capture = _ShortcutCaptureDialog(registry, "undo")
    conflict_capture.keyPressEvent(QKeyEvent(
        QEvent.KeyPress,
        Qt.Key_Y,
        Qt.ControlModifier,
    ))
    conflict_capture._on_accept()

    assert registry.binding("undo") == "Ctrl+Z"
    assert conflict_capture._error_label.text() == "与「重做（备用）」冲突，请重新设置"

    invalid_capture = _ShortcutCaptureDialog(registry, "undo")
    invalid_capture.keyPressEvent(QKeyEvent(
        QEvent.KeyPress,
        Qt.Key_unknown,
        Qt.NoModifier,
    ))

    assert invalid_capture._portable_text is None
    assert invalid_capture._error_label.text() == "快捷键无效，请重新输入"


def test_editing_shortcut_updates_only_draft_until_settings_save(qapp, monkeypatch):
    from PyQt5.QtWidgets import QDialog

    from app.config import AppConfig
    import ui.settings_dialog as settings_dialog_module

    class AcceptedCapture:
        def __init__(self, *_args):
            self._portable_text = next(captured_bindings)

        def exec_(self):
            return QDialog.Accepted

    config = AppConfig()
    dialog = settings_dialog_module.SettingsDialog(config)
    captured_bindings = iter(("Ctrl+K", "Ctrl+L"))
    monkeypatch.setattr(
        settings_dialog_module,
        "_ShortcutCaptureDialog",
        AcceptedCapture,
    )

    undo_row = next(
        row
        for row, action in enumerate(dialog._shortcut_actions)
        if action.action_id == "undo"
    )
    dialog._shortcut_table.cellWidget(undo_row, 3).click()

    assert dialog._shortcut_draft.binding("undo") == "Ctrl+K"
    assert dialog._shortcut_table.item(undo_row, 2).text() == "Ctrl+K"

    dialog._shortcut_table.cellDoubleClicked.emit(undo_row, 2)

    assert dialog._shortcut_draft.binding("undo") == "Ctrl+L"
    assert dialog._shortcut_table.item(undo_row, 2).text() == "Ctrl+L"
    assert config.shortcuts["undo"] == "Ctrl+Z"


def test_shortcut_resets_change_only_draft_after_confirmation(qapp, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox

    from app.config import AppConfig
    import ui.settings_dialog as settings_dialog_module

    config = AppConfig(shortcuts={"undo": "Ctrl+K", "redo": "Ctrl+L"})
    dialog = settings_dialog_module.SettingsDialog(config)

    dialog._reset_shortcut("undo")

    assert dialog._shortcut_draft.binding("undo") == "Ctrl+Z"
    assert config.shortcuts["undo"] == "Ctrl+K"

    monkeypatch.setattr(
        settings_dialog_module.QMessageBox,
        "question",
        lambda *_args: QMessageBox.No,
    )
    dialog._reset_all_shortcuts()

    assert dialog._shortcut_draft.binding("redo") == "Ctrl+L"

    monkeypatch.setattr(
        settings_dialog_module.QMessageBox,
        "question",
        lambda *_args: QMessageBox.Yes,
    )
    dialog._reset_all_shortcuts()

    assert dialog._shortcut_draft.bindings() == settings_dialog_module.ShortcutRegistry().bindings()
    assert config.shortcuts == {**settings_dialog_module.ShortcutRegistry().bindings(), "undo": "Ctrl+K", "redo": "Ctrl+L"}


def test_shortcuts_are_saved_only_when_settings_are_saved(qapp, monkeypatch):
    from PyQt5.QtWidgets import QDialog

    from app.config import AppConfig
    import ui.settings_dialog as settings_dialog_module

    class AcceptedCapture:
        def __init__(self, *_args):
            self._portable_text = "Ctrl+K"

        def exec_(self):
            return QDialog.Accepted

    config = AppConfig()
    save_calls = []
    monkeypatch.setattr(config, "save", lambda: save_calls.append(True))
    monkeypatch.setattr(
        settings_dialog_module,
        "_ShortcutCaptureDialog",
        AcceptedCapture,
    )

    cancelled_dialog = settings_dialog_module.SettingsDialog(config)
    cancelled_dialog._edit_shortcut("undo")
    cancelled_dialog.reject()

    assert config.shortcuts["undo"] == "Ctrl+Z"
    assert save_calls == []

    saved_dialog = settings_dialog_module.SettingsDialog(config)
    saved_dialog._edit_shortcut("undo")
    saved_dialog._on_save()

    assert saved_dialog.result() == QDialog.Accepted
    assert config.shortcuts == saved_dialog._shortcut_draft.bindings()
    assert config.shortcuts["undo"] == "Ctrl+K"
    assert save_calls == [True]


def test_invalid_shortcut_draft_blocks_settings_save(qapp, monkeypatch):
    from app.config import AppConfig
    from core.shortcuts import ShortcutRegistry
    from ui.settings_dialog import SettingsDialog

    config = AppConfig()
    save_calls = []
    monkeypatch.setattr(config, "save", lambda: save_calls.append(True))
    dialog = SettingsDialog(config)
    dialog._shortcut_draft = ShortcutRegistry({"undo": "Ctrl+Y"})

    dialog._on_save()

    assert config.shortcuts["undo"] == "Ctrl+Z"
    assert save_calls == []
    assert dialog._shortcut_error_label.text() == "与「撤销」冲突，请重新设置"
