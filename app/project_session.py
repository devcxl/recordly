"""项目会话 — 拥有项目目录、Project 模型和媒体资源路径契约"""

import os
from pathlib import Path

from core.project import Project


class ProjectSession:
    """当前项目会话。纯 Python 对象，非 QObject，可独立测试。"""

    def __init__(self, project_dir: str):
        """
        Raises:
            FileNotFoundError: 项目目录不存在
            ValueError: project.json 损坏或不兼容
        """
        self._project_dir = str(Path(project_dir).resolve())
        if not os.path.isdir(self._project_dir):
            raise FileNotFoundError(f"项目目录不存在: {self._project_dir}")
        self._project = Project.load(self.project_file)

    @property
    def project_dir(self) -> str:
        return self._project_dir

    @property
    def project(self) -> Project:
        return self._project

    @property
    def project_file(self) -> str:
        return os.path.join(self._project_dir, "project.json")

    @property
    def frames_data_path(self) -> str:
        return os.path.join(self._project_dir, "frames.data")

    @property
    def audio_mic_path(self) -> str:
        mic = self._project.source.audio_mic if self._project.source else ""
        if mic:
            return os.path.join(self._project_dir, mic)
        return ""

    @property
    def audio_system_path(self) -> str:
        sys_path = self._project.source.audio_system if self._project.source else ""
        if sys_path:
            return os.path.join(self._project_dir, sys_path)
        return ""

    @classmethod
    def create(cls, projects_dir: str, name: str) -> "ProjectSession":
        """创建新项目目录和占位 project.json"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = os.path.join(projects_dir, f"{timestamp}_{name}")
        os.makedirs(project_dir, exist_ok=True)
        project = Project()
        project.name = name
        project.save(os.path.join(project_dir, "project.json"))
        session = cls.__new__(cls)
        session._project_dir = project_dir
        session._project = project
        return session

    @classmethod
    def load(cls, project_dir: str) -> "ProjectSession":
        """从目录加载并校验 schema。校验失败抛 ValueError 且不修改参数目录。"""
        return cls(project_dir)

    def save(self, project: Project):
        """原子保存 project.json"""
        project.save(self.project_file)

    @staticmethod
    def normalize_path(input_path: str) -> str:
        """将 project.json 文件路径规范化为项目目录路径"""
        if input_path.endswith("project.json"):
            return str(Path(input_path).parent)
        return input_path
