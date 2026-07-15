"""ProjectSession 单元测试"""

import json
import os
import tempfile
import pytest

from core.project import Project
from app.project_session import ProjectSession


class TestProjectSessionCreate:
    def test_create_generates_unique_project_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ProjectSession.create(tmpdir, "测试录制")
            assert os.path.isdir(session.project_dir)
            assert os.path.exists(session.project_file)
            assert session.project.name == "测试录制"

    def test_create_project_file_is_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ProjectSession.create(tmpdir, "test")
            loaded = Project.load(session.project_file)
            assert loaded.name == "test"
            assert loaded.version == Project.VERSION


class TestProjectSessionLoad:
    def test_load_from_existing_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ProjectSession.create(tmpdir, "demo")
            session2 = ProjectSession.load(session.project_dir)
            assert os.path.samefile(session2.project_dir, session.project_dir)
            assert session2.project.name == "demo"

    def test_load_missing_dir_raises(self):
        with pytest.raises(FileNotFoundError):
            ProjectSession.load("/nonexistent/dir")

    def test_load_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_file = os.path.join(tmpdir, "project.json")
            with open(proj_file, "w") as f:
                f.write("not json")
            with pytest.raises((ValueError, json.JSONDecodeError)):
                ProjectSession.load(tmpdir)


class TestProjectSessionPaths:
    def test_frames_data_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ProjectSession.create(tmpdir, "test")
            assert session.frames_data_path.endswith("frames.data")

    def test_audio_paths_empty_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ProjectSession.create(tmpdir, "test")
            assert session.audio_mic_path == ""
            assert session.audio_system_path == ""


class TestProjectSessionNormalize:
    def test_normalize_project_json_file(self):
        p = ProjectSession.normalize_path(
            os.path.join("home", "user", "Recordly", "projects", "test", "project.json"))
        expected = os.path.normpath(os.path.join("home", "user", "Recordly", "projects", "test"))
        assert p == expected

    def test_normalize_directory_unchanged(self):
        p = ProjectSession.normalize_path(
            os.path.join("home", "user", "Recordly", "projects", "demo"))
        expected = os.path.normpath(os.path.join("home", "user", "Recordly", "projects", "demo"))
        assert p == expected
