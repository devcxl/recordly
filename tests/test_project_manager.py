"""测试 ProjectManager"""

import json
from pathlib import Path

import pytest

from core.project import Project, SourceInfo
from core.project_manager import ProjectManager, ProjectSummary


class TestProjectSummary:
    """ProjectSummary 数据类基础测试"""

    def test_fields(self):
        s = ProjectSummary(
            name="test",
            path="/a/b",
            modified_at="2024-01-01T00:00:00",
            duration=12.5,
            thumbnail_path="/a/b/thumb.png",
        )
        assert s.name == "test"
        assert s.path == "/a/b"
        assert s.modified_at == "2024-01-01T00:00:00"
        assert s.duration == 12.5
        assert s.thumbnail_path == "/a/b/thumb.png"


class TestProjectManager:
    """ProjectManager 集成测试（使用 tmp_path）"""

    @pytest.fixture
    def mgr(self, tmp_path: Path) -> ProjectManager:
        return ProjectManager(str(tmp_path / "projects"))

    def _create_project_dir(self, base: Path, name: str,
                            modified_at: str = "2024-01-01T00:00:00",
                            duration: float = 10.0) -> Path:
        """在 base 下创建含 project.json 的目录"""
        d = base / name
        d.mkdir(parents=True)
        data = {
            "name": name,
            "modified_at": modified_at,
            "duration": duration,
            "thumbnail_path": "thumbnail.png",
            "version": "1.1",
        }
        with open(d / "project.json", "w") as f:
            json.dump(data, f)
        return d

    # ── list_projects ────────────────────────────────────

    def test_list_projects_empty_dir(self, mgr: ProjectManager):
        assert mgr.list_projects() == []

    def test_list_projects_nonexistent_dir(self, tmp_path: Path):
        mgr = ProjectManager(str(tmp_path / "does_not_exist"))
        assert mgr.list_projects() == []

    def test_list_projects_ignores_non_project_dirs(self, mgr: ProjectManager):
        (Path(mgr._projects_dir) / "empty_dir").mkdir(parents=True)
        (Path(mgr._projects_dir) / "no_json").mkdir()
        assert mgr.list_projects() == []

    def test_list_projects_single(self, mgr: ProjectManager):
        self._create_project_dir(Path(mgr._projects_dir), "proj1")
        projects = mgr.list_projects()
        assert len(projects) == 1
        assert projects[0].name == "proj1"

    def test_list_projects_ordered_by_modified_at_desc(self, mgr: ProjectManager):
        self._create_project_dir(Path(mgr._projects_dir), "older",
                                 modified_at="2023-01-01T00:00:00")
        self._create_project_dir(Path(mgr._projects_dir), "newer",
                                 modified_at="2024-01-01T00:00:00")
        projects = mgr.list_projects()
        assert len(projects) == 2
        assert projects[0].name == "newer"
        assert projects[1].name == "older"

    def test_list_projects_skips_corrupt_json(self, mgr: ProjectManager):
        d = Path(mgr._projects_dir) / "bad"
        d.mkdir(parents=True)
        with open(d / "project.json", "w") as f:
            f.write("not json")
        self._create_project_dir(Path(mgr._projects_dir), "good")
        assert len(mgr.list_projects()) == 1

    # ── create_project ───────────────────────────────────

    def test_create_project_creates_directory_and_files(self, mgr: ProjectManager,
                                                        tmp_path: Path):
        source = tmp_path / "source.mp4"
        source.write_text("fake video content")

        proj = Project()
        proj.source = SourceInfo()
        summary = mgr.create_project("my_project", proj, str(source))

        assert Path(summary.path).is_dir()
        assert (Path(summary.path) / "project.json").is_file()
        assert (Path(summary.path) / "source.mp4").is_file()
        assert (Path(summary.path) / "thumbnail.png").is_file()
        assert summary.name == "my_project"

    def test_create_project_without_source(self, mgr: ProjectManager,
                                           tmp_path: Path):
        """source=None 时 create_project 不崩溃"""
        source = tmp_path / "source.mp4"
        source.write_text("fake video content")

        proj = Project()
        proj.source = None
        summary = mgr.create_project("no_source", proj, str(source))

        assert Path(summary.path).is_dir()
        assert (Path(summary.path) / "project.json").is_file()
        assert summary.name == "no_source"

    def test_create_project_rollback_on_failure(self, mgr: ProjectManager,
                                                tmp_path: Path):
        """创建过程中异常应回滚已创建的目录"""
        source = tmp_path / "source.mp4"
        source.write_text("fake")

        proj = Project()
        proj.source = SourceInfo()

        # 让 copy2 抛出异常：源路径不存在
        with pytest.raises(FileNotFoundError):
            mgr.create_project("rollback_test", proj, "/nonexistent/source.mp4")

        # 不应有残留目录
        for child in Path(mgr._projects_dir).iterdir():
            assert "rollback_test" not in child.name

    def test_create_project_preserves_source_content(self, mgr: ProjectManager,
                                                     tmp_path: Path):
        source = tmp_path / "source.mp4"
        source.write_text("original content")

        proj = Project()
        proj.source = SourceInfo()
        summary = mgr.create_project("test", proj, str(source))

        copied = Path(summary.path) / "source.mp4"
        assert copied.read_text() == "original content"

    # ── open_project ─────────────────────────────────────

    def test_open_project(self, mgr: ProjectManager, tmp_path: Path):
        source = tmp_path / "source.mp4"
        source.write_text("fake")
        proj = Project()
        proj.source = SourceInfo()
        summary = mgr.create_project("test", proj, str(source))

        loaded = mgr.open_project(summary.path)
        assert loaded.name == "test"
        assert isinstance(loaded, Project)

    def test_open_project_raises_on_missing(self, mgr: ProjectManager):
        with pytest.raises(FileNotFoundError):
            mgr.open_project("/nonexistent/path")

    # ── delete_project ───────────────────────────────────

    def test_delete_project(self, mgr: ProjectManager, tmp_path: Path):
        source = tmp_path / "source.mp4"
        source.write_text("fake")
        proj = Project()
        proj.source = SourceInfo()
        summary = mgr.create_project("test", proj, str(source))

        assert Path(summary.path).is_dir()
        mgr.delete_project(summary.path)
        assert not Path(summary.path).exists()

    def test_delete_project_raises_on_missing(self, mgr: ProjectManager):
        with pytest.raises(ValueError, match="不在项目目录范围内"):
            mgr.delete_project("/nonexistent/path")

    def test_delete_project_raises_on_path_traversal(self, mgr: ProjectManager):
        """路径穿越应被拒绝"""
        with pytest.raises(ValueError, match="不在项目目录范围内"):
            mgr.delete_project("/tmp/somewhere_else")

    def test_delete_project_raises_on_path_traversal_dotdot(self,
                                                            mgr: ProjectManager,
                                                            tmp_path: Path):
        """../ 路径穿越应被拒绝"""
        source = tmp_path / "source.mp4"
        source.write_text("fake")
        proj = Project()
        proj.source = SourceInfo()
        summary = mgr.create_project("test", proj, str(source))
        traversal = str(Path(summary.path) / "../../../etc")
        with pytest.raises(ValueError, match="不在项目目录范围内"):
            mgr.delete_project(traversal)

    # ── rename_project ───────────────────────────────────

    def test_rename_project(self, mgr: ProjectManager, tmp_path: Path):
        source = tmp_path / "source.mp4"
        source.write_text("fake")
        proj = Project()
        proj.source = SourceInfo()
        summary = mgr.create_project("old_name", proj, str(source))

        mgr.rename_project(summary.path, "new_name")

        proj_file = Path(summary.path) / "project.json"
        with open(proj_file) as f:
            data = json.load(f)
        assert data["name"] == "new_name"

    def test_rename_project_raises_on_empty_name(self, mgr: ProjectManager,
                                                 tmp_path: Path):
        source = tmp_path / "source.mp4"
        source.write_text("fake")
        proj = Project()
        proj.source = SourceInfo()
        summary = mgr.create_project("test", proj, str(source))

        with pytest.raises(ValueError, match="项目名称不能为空"):
            mgr.rename_project(summary.path, "")
        with pytest.raises(ValueError, match="项目名称不能为空"):
            mgr.rename_project(summary.path, "   ")

    def test_rename_project_raises_on_missing_json(self, mgr: ProjectManager,
                                                    tmp_path: Path):
        d = tmp_path / "no_json"
        d.mkdir()
        with pytest.raises(FileNotFoundError):
            mgr.rename_project(str(d), "new_name")

    # ── generate_thumbnail ───────────────────────────────

    def test_generate_thumbnail_fallback_on_no_ffmpeg(self, mgr: ProjectManager,
                                                      tmp_path: Path):
        """FFmpeg 不可用时生成占位图"""
        video = tmp_path / "nonexistent.mp4"
        output = tmp_path / "thumb.png"
        result = mgr.generate_thumbnail(str(video), str(output))
        assert result is True
        assert output.is_file()
        assert output.stat().st_size > 0
