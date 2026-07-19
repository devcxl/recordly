"""Tests for app/config.py"""

import pytest


class TestAppConfig:
    def test_importable(self):
        from app.config import AppConfig
        assert AppConfig is not None

    def test_defaults(self):
        from app.config import AppConfig
        c = AppConfig()
        assert c.recordings_dir == "~/Recordly/recordings"
        assert c.default_fps == 30
        assert c.default_bitrate == "10M"
        assert c.language == "zh_CN"
        assert c.cursor_style == "dot"

    def test_custom_values(self):
        from app.config import AppConfig
        c = AppConfig(recordings_dir="~/custom", default_fps=60, language="en")
        assert c.recordings_dir == "~/custom"
        assert c.default_fps == 60
        assert c.language == "en"

    def test_save_and_load(self):
        """验证 save/load 接口可用"""
        from app.config import AppConfig
        c = AppConfig()
        assert callable(c.save)
        assert hasattr(AppConfig, 'load')

    def test_os_path_expansion_on_load(self):
        """load() 时 recordings_dir 被 expanduser"""
        from app.config import AppConfig
        c = AppConfig.load()
        assert '~' not in c.recordings_dir

    def test_cursor_style_roundtrips_through_settings(self, monkeypatch):
        import app.config as config_module

        storage = {}

        class FakeSettings:
            def __init__(self, *_args):
                pass

            def value(self, key, default=None):
                return storage.get(key, default)

            def setValue(self, key, value):
                storage[key] = value

            def sync(self):
                pass

        monkeypatch.setattr(config_module, "QSettings", FakeSettings)
        config = config_module.AppConfig(cursor_style="spotlight")

        config.save()
        loaded = config_module.AppConfig.load()

        assert loaded.cursor_style == "spotlight"

    def test_shortcuts_default_to_independent_catalog_bindings(self):
        from app.config import AppConfig

        first_config = AppConfig()
        second_config = AppConfig()
        first_config.shortcuts["undo"] = "Ctrl+K"

        assert len(first_config.shortcuts) == 12
        assert second_config.shortcuts["undo"] == "Ctrl+Z"

    def test_explicit_shortcuts_are_completed_and_ignore_unknown_actions(self):
        from app.config import AppConfig
        from core.shortcuts import ShortcutRegistry

        config = AppConfig(shortcuts={"undo": "Ctrl+K", "missing": "Ctrl+M"})

        assert config.shortcuts["undo"] == "Ctrl+K"
        assert config.shortcuts.keys() == ShortcutRegistry().bindings().keys()
        assert config.shortcuts["redo"] == "Ctrl+Shift+Z"
        assert "missing" not in config.shortcuts

    def test_load_uses_defaults_for_missing_shortcuts_and_keeps_old_fields(self, monkeypatch):
        import app.config as config_module
        from core.shortcuts import ShortcutRegistry

        storage = {"default_fps": "60", "cursor_style": "spotlight"}

        class FakeSettings:
            def __init__(self, *_args):
                pass

            def value(self, key, default=None):
                return storage.get(key, default)

            def setValue(self, key, value):
                storage[key] = value

            def sync(self):
                pass

        monkeypatch.setattr(config_module, "QSettings", FakeSettings)

        loaded = config_module.AppConfig.load()

        assert loaded.default_fps == 60
        assert loaded.cursor_style == "spotlight"
        assert loaded.shortcuts == ShortcutRegistry().bindings()

    def test_shortcuts_roundtrip_all_bindings_and_syncs(self, monkeypatch):
        import app.config as config_module

        storage = {}
        sync_calls = []

        class FakeSettings:
            def __init__(self, *_args):
                pass

            def value(self, key, default=None):
                return storage.get(key, default)

            def setValue(self, key, value):
                storage[key] = value

            def sync(self):
                sync_calls.append(True)

        monkeypatch.setattr(config_module, "QSettings", FakeSettings)
        config = config_module.AppConfig()
        config.shortcuts["undo"] = "Ctrl+K"
        config.shortcuts["redo_alt"] = "ctrl+y"

        config.save()
        loaded = config_module.AppConfig.load()

        saved_shortcut_ids = {
            key.removeprefix("shortcuts/")
            for key in storage
            if key.startswith("shortcuts/")
        }
        assert saved_shortcut_ids == set(config.shortcuts)
        assert config.shortcuts["redo_alt"] == "Ctrl+Y"
        assert storage["shortcuts/redo_alt"] == "Ctrl+Y"
        assert loaded.shortcuts == config.shortcuts
        assert sync_calls == [True]

    def test_load_normalizes_shortcut_for_registry_conflict_detection(self, monkeypatch):
        import app.config as config_module
        from core.shortcuts import ShortcutRegistry

        storage = {"shortcuts/redo_alt": "ctrl+y"}

        class FakeSettings:
            def __init__(self, *_args):
                pass

            def value(self, key, default=None):
                return storage.get(key, default)

            def setValue(self, key, value):
                storage[key] = value

            def sync(self):
                pass

        monkeypatch.setattr(config_module, "QSettings", FakeSettings)

        loaded = config_module.AppConfig.load()
        validation = ShortcutRegistry(loaded.shortcuts).validate("undo", "Ctrl+Y")

        assert loaded.shortcuts["redo_alt"] == "Ctrl+Y"
        assert validation.code == "SHORTCUT_CONFLICT"
        assert validation.conflicting_action_id == "redo_alt"

    def test_load_replaces_invalid_shortcut_value_with_default(self, monkeypatch):
        import app.config as config_module
        from core.shortcuts import ShortcutRegistry

        storage = {"shortcuts/undo": "not-a-shortcut"}

        class FakeSettings:
            def __init__(self, *_args):
                pass

            def value(self, key, default=None):
                return storage.get(key, default)

            def setValue(self, key, value):
                storage[key] = value

            def sync(self):
                pass

        monkeypatch.setattr(config_module, "QSettings", FakeSettings)

        loaded = config_module.AppConfig.load()

        assert loaded.shortcuts["undo"] == ShortcutRegistry().binding("undo")
