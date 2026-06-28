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
