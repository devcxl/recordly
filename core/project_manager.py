"""项目管理器 — 目录扫描、CRUD、缩略图生成"""

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.project import Project


@dataclass
class ProjectSummary:
    name: str
    path: str
    modified_at: str
    duration: float
    thumbnail_path: str


class ProjectManager:
    """基于目录的项目管理器"""

    def __init__(self, projects_dir: str):
        self._projects_dir = Path(projects_dir)

    # ── 查询 ──────────────────────────────────────────────

    def list_projects(self) -> list[ProjectSummary]:
        """扫描 projects_dir 下所有子目录，读取 project.json 元数据，按 modified_at 降序。"""
        if not self._projects_dir.is_dir():
            return []

        results: list[ProjectSummary] = []
        for child in sorted(self._projects_dir.iterdir()):
            if not child.is_dir():
                continue
            proj_file = child / "project.json"
            if not proj_file.is_file():
                continue
            try:
                with open(proj_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            results.append(ProjectSummary(
                name=data.get("name", child.name),
                path=str(child),
                modified_at=data.get("modified_at", ""),
                duration=data.get("duration", 0.0),
                thumbnail_path=data.get("thumbnail_path", ""),
            ))

        results.sort(key=lambda p: p.modified_at, reverse=True)
        return results

    # ── 创建 ──────────────────────────────────────────────

    def create_project(self, name: str, project: Project,
                       source_video_path: str) -> ProjectSummary:
        """创建时间戳子目录 → 复制源视频 → 生成缩略图 → 保存 project.json。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_dir = self._projects_dir / f"{timestamp}_{name}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            # 复制源视频
            source_dest = dest_dir / "source.mp4"
            shutil.copy2(source_video_path, source_dest)

            # 生成缩略图
            thumbnail_path = dest_dir / "thumbnail.png"
            self.generate_thumbnail(str(source_dest), str(thumbnail_path))

            # 填充 project 元数据
            project.name = name
            if project.source:
                project.source.video = str(source_dest)
            # duration 由调用方录制器在 project 对象上预设
            project.thumbnail_path = "thumbnail.png"

            # 保存
            proj_file = dest_dir / "project.json"
            project.save(str(proj_file))

            return ProjectSummary(
                name=name,
                path=str(dest_dir),
                modified_at=project.modified_at,
                duration=project.duration,
                thumbnail_path="thumbnail.png",
            )
        except Exception:
            shutil.rmtree(dest_dir, ignore_errors=True)
            raise

    # ── 打开 ──────────────────────────────────────────────

    def open_project(self, project_path: str) -> Project:
        """加载完整 Project 对象。"""
        proj_file = Path(project_path) / "project.json"
        if not proj_file.is_file():
            raise FileNotFoundError(f"项目文件不存在: {proj_file}")
        return Project.load(str(proj_file))

    # ── 删除 ──────────────────────────────────────────────

    def delete_project(self, project_path: str):
        """递归删除整个项目目录。"""
        path = Path(project_path).resolve()
        root = self._projects_dir.resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"项目路径不在项目目录范围内: {path}")
        if not path.is_dir():
            raise FileNotFoundError(f"项目目录不存在: {path}")
        shutil.rmtree(path)

    # ── 重命名 ────────────────────────────────────────────

    def rename_project(self, project_path: str, new_name: str):
        """更新 project.json 中的 name 字段。"""
        if not new_name or not new_name.strip():
            raise ValueError("项目名称不能为空")
        proj_file = Path(project_path) / "project.json"
        if not proj_file.is_file():
            raise FileNotFoundError(f"项目文件不存在: {proj_file}")

        with open(proj_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["name"] = new_name.strip()
        data["modified_at"] = datetime.now().isoformat()

        # 原子写入：临时文件 → replace
        fd, tmp_path = tempfile.mkstemp(dir=str(proj_file.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, proj_file)
        except Exception:
            os.unlink(tmp_path)
            raise

    # ── 缩略图 ────────────────────────────────────────────

    def generate_thumbnail(self, video_path: str,
                           output_path: str, timestamp: float = 0.0) -> bool:
        """调用 FFmpeg 截帧生成缩略图，失败时生成占位图。"""
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss", str(timestamp),
                    "-i", video_path,
                    "-vframes", "1",
                    "-vf", "scale=320:180:force_original_aspect_ratio=decrease,"
                           "pad=320:180:(ow-iw)/2:(oh-ih)/2",
                    "-q:v", "2",
                    output_path,
                ],
                capture_output=True,
                timeout=30,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return self._fallback_thumbnail(output_path)

    def _fallback_thumbnail(self, output_path: str) -> bool:
        """FFmpeg 不可用时生成占位图。"""
        try:
            from PIL import Image
            img = Image.new("RGB", (320, 180), (64, 64, 64))
            img.save(output_path)
            return True
        except ImportError:
            return False
