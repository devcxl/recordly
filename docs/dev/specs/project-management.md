# 项目管理功能 — 技术方案

## 1. 需求概述

### 问题描述
Recordly 当前 `Project` 类仅支持单文件 JSON 序列化，`MainWindow` 中项目列表为空的 `QListWidget`，新建/打开/保存均为空存根。用户无法管理多个项目，录制完成后数据在内存中，关闭即丢失。

### 目标用户/场景
- 用户录制屏幕 → 自动创建项目 → 后续可打开继续编辑
- 用户浏览项目列表 → 通过卡片网格选择已有项目 → 继续编辑
- 用户重命名/删除项目

### 成功标准
- 录制完成后自动创建项目（含缩略图），数据持久化到磁盘
- 项目列表以卡片网格展示，缩略图 + 名称 + 时长
- 支持打开、重命名、删除项目
- 项目目录路径可在设置中配置

---

## 2. 架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        MainWindow                                │
│                                                                  │
│  ┌──────────────────────┐   ┌──────────────────────────────┐    │
│  │   EditorInterface    │   │    ProjectInterface            │    │
│  │                      │   │                                │    │
│  │  Recorder ─┐         │   │  ProjectGallery               │    │
│  │  Compositor│         │   │  ┌─────┐ ┌─────┐ ┌─────┐     │    │
│  │  Timeline  │         │   │  │Card │ │Card │ │Card │ ... │    │
│  │  Preview   │         │   │  └─────┘ └─────┘ └─────┘     │    │
│  │            │         │   │                                │    │
│  │  ┌─────────────────┐ │   │  ┌──────────────────────────┐ │    │
│  │  │ 停止录制后       │ │   │  │ ProjectManager           │ │    │
│  │  │ → 创建项目       │─┼───┼─→│ .list() / .create()      │ │    │
│  │  │ → 刷新画廊       │ │   │  │ .delete() / .rename()    │ │    │
│  │  └─────────────────┘ │   │  └──────────────────────────┘ │    │
│  └──────────────────────┘   └──────────────────────────────┘    │
│                                                                  │
│                        AppConfig                                  │
│                     projects_dir: str                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分及职责

| 模块 | 文件 | 职责 |
|------|------|------|
| **Project 数据模型** | `core/project.py` | 新增 `name`、`modified_at`、`duration`、`thumbnail_path` 字段 |
| **ProjectManager** | `core/project_manager.py`（新建） | 目录扫描、创建/删除/重命名/列出项目 |
| **ProjectCard** | `ui/project_card.py`（新建） | 单张卡片 UI（缩略图 + 名称 + 时长） |
| **ProjectGallery** | `ui/project_gallery.py`（新建） | 卡片网格容器，右键菜单，信号转发 |
| **MainWindow** | `app/main_window.py` | 替换 QListWidget 为 ProjectGallery，集成录制→项目创建流程 |
| **SettingsDialog** | `ui/settings_dialog.py` | 新增"项目目录"设置项 |
| **AppConfig** | `app/config.py` | 已有 `projects_dir`，无需修改 |

### 2.3 数据流向

```
录制结束                              用户操作
─────────                            ────────
MainWindow._on_recording_stopped()
  │
  ├─→ ProjectManager.create()        ProjectGallery
  │     ├─ mkdir 项目目录               ├─ 双击名称 → ProjectManager.rename()
  │     ├─ 保存源视频                   ├─ 右键删除 → ProjectManager.delete()
  │     ├─ FFmpeg 截取缩略图            └─ 点击卡片 → MainWindow._on_open_project()
  │     ├─ Project.save() 写 JSON
  │     └─ 返回 ProjectSummary
  │
  └─→ ProjectGallery.refresh()
```

---

## 3. 模块拆分

### 3.1 模块列表及依赖关系

```
core/project.py          ←─ 无依赖（纯数据模型）
core/project_manager.py  ←─ 依赖 core/project.py, subprocess(FFmpeg)
ui/project_card.py       ←─ 依赖 PyQt5
ui/project_gallery.py    ←─ 依赖 ui/project_card.py, core/project_manager.py
app/main_window.py       ←─ 依赖 ui/project_gallery.py, core/project_manager.py
ui/settings_dialog.py    ←─ 依赖 app/config.py
```

### 3.2 Project 类新增字段

```python
# core/project.py — Project 类新增字段

@dataclass
class Project:
    # 现有字段保持不变 ...

    def __init__(self):
        # ... 现有初始化 ...
        self.name: str = ""             # 项目名称（用于显示）
        self.modified_at: str = ""      # 最后修改时间 ISO 格式
        self.duration: float = 0.0      # 总时长（秒）
        self.thumbnail_path: str = ""   # 缩略图相对路径（如 "thumbnail.png"）

    def save(self, path: str):
        data = {
            # ... 现有字段 ...
            "name": self.name,
            "modified_at": datetime.now().isoformat(),
            "duration": self.duration,
            "thumbnail_path": self.thumbnail_path,
        }
        # ... 其余不变 ...

    @classmethod
    def load(cls, path: str) -> "Project":
        # ... 现有加载逻辑 ...
        proj.name = data.get("name", "")
        proj.modified_at = data.get("modified_at", "")
        proj.duration = data.get("duration", 0.0)
        proj.thumbnail_path = data.get("thumbnail_path", "")
        return proj
```

### 3.3 ProjectManager 接口定义

```python
# core/project_manager.py

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class ProjectSummary:
    """项目列表摘要 — 轻量级，不加载完整 Project"""
    name: str
    path: str                      # 绝对路径
    modified_at: str               # ISO 格式
    duration: float                # 秒
    thumbnail_path: str            # 相对于项目目录的路径

class ProjectManager:
    """多项目管理器 — 基于目录扫描"""

    def __init__(self, projects_dir: str):
        """projects_dir: 项目根目录（如 ~/Recordly/projects）"""

    def list_projects(self) -> list[ProjectSummary]:
        """扫描 projects_dir 下所有包含 project.json 的子目录。
        对每个子目录：只读取 project.json 中的 name/modified_at/duration/thumbnail_path 字段。
        不加载完整 Project 对象。
        按 modified_at 降序排列。
        """

    def create_project(self, name: str, project: Project,
                       source_video_path: str) -> ProjectSummary:
        """新建项目：
        1. 在 projects_dir 下创建子目录（目录名使用时间戳）
        2. 将 source_video_path 复制到子目录
        3. 生成缩略图 → thumbnail.png
        4. 设置 project.name/duration/thumbnail_path/modified_at
        5. 调用 project.save() 写入 project.json
        6. 返回 ProjectSummary
        """

    def open_project(self, project_path: str) -> Project:
        """加载完整 Project 对象"""

    def delete_project(self, project_path: str):
        """删除整个项目目录（递归删除）"""

    def rename_project(self, project_path: str, new_name: str):
        """更新 project.json 中的 name 字段"""

    def generate_thumbnail(self, video_path: str,
                           output_path: str,
                           timestamp: float = 0.0) -> bool:
        """使用 FFmpeg 从视频中截取一帧作为缩略图。
        命令: ffmpeg -ss {timestamp} -i {video_path} -vframes 1 -q:v 2 {output_path}
        图片尺寸: 320x180（16:9 缩放），保持宽高比。
        返回 True 表示成功，False 表示失败（此时使用默认占位图）。
        """
```

### 3.4 ProjectCard 组件设计

```python
# ui/project_card.py

from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

class ProjectCard(QFrame):
    """项目卡片组件 — 缩略图 + 名称 + 时长"""

    clicked = pyqtSignal(str)           # 点击卡片 → 发射项目路径
    rename_requested = pyqtSignal(str)  # 双击名称 → 发射项目路径
    delete_requested = pyqtSignal(str)  # 右键删除 → 发射项目路径

    SIZE = (240, 180)  # 卡片尺寸 (宽 x 高)

    def __init__(self, summary: ProjectSummary, parent=None):
        """summary: ProjectSummary 对象"""

    def update_summary(self, summary: ProjectSummary):
        """更新卡片显示内容（重命名后调用）"""

    # 布局结构：
    # ┌──────────────────────┐
    # │                      │
    # │    缩略图 240x135     │  ← QLabel(QPixmap)
    # │                      │
    # ├──────────────────────┤
    # │ 项目名称 (可双击编辑)  │  ← QLabel, 可双击变为 QLineEdit
    # │ 时长: 00:05:30       │  ← QLabel
    # └──────────────────────┘
```

### 3.5 ProjectGallery 组件设计

```python
# ui/project_gallery.py

from PyQt5.QtWidgets import QScrollArea, QWidget, QMenu, QAction
from PyQt5.QtCore import Qt, pyqtSignal

class ProjectGallery(QScrollArea):
    """项目卡片网格容器"""

    project_opened = pyqtSignal(str)      # 打开项目 → 发射项目路径
    project_deleted = pyqtSignal(str)     # 删除项目 → 发射项目路径
    project_renamed = pyqtSignal(str, str) # 重命名 → 发射 (路径, 新名称)

    def __init__(self, parent=None):
        """初始化可滚动区域 + FlowLayout 容器"""

    def set_projects(self, summaries: list[ProjectSummary]):
        """清空并重新填充卡片网格"""

    def refresh(self):
        """重新扫描项目目录并刷新显示"""

    def contextMenuEvent(self, event):
        """右键菜单: 删除"""
```

### 3.6 数据库表结构

不涉及数据库。使用文件系统目录结构。

---

## 4. 接口设计

### 4.1 ProjectManager API

```python
class ProjectManager:
    def __init__(self, projects_dir: str)
    def list_projects(self) -> list[ProjectSummary]
    def create_project(self, name: str, project: Project, source_video_path: str) -> ProjectSummary
    def open_project(self, project_path: str) -> Project
    def delete_project(self, project_path: str)
    def rename_project(self, project_path: str, new_name: str)
    def generate_thumbnail(self, video_path: str, output_path: str, timestamp: float = 0.0) -> bool
```

### 4.2 ProjectSummary 数据模型

```python
@dataclass
class ProjectSummary:
    name: str            # 项目名称
    path: str            # 项目目录绝对路径
    modified_at: str     # 最后修改时间 ISO 格式
    duration: float      # 时长（秒）
    thumbnail_path: str  # 缩略图相对路径，如 "thumbnail.png"
```

### 4.3 项目 JSON 文件格式（完整示例）

```json
{
  "version": "1.1",
  "name": "2026-07-13_14-30-00",
  "created_at": "2026-07-13T14:30:00",
  "modified_at": "2026-07-13T14:35:00",
  "duration": 120.5,
  "thumbnail_path": "thumbnail.png",
  "source": {
    "video": "source.mp4",
    "audio_mic": "",
    "audio_system": "",
    "duration": 120.5,
    "fps": 30,
    "width": 1920,
    "height": 1080
  },
  "timeline": [],
  "cursor": {},
  "frame_style": {},
  "annotations": [],
  "audio_regions": [],
  "crop_region": null,
  "aspect_ratio": "native"
}
```

### 4.4 信号流

```
ProjectCard.clicked          → ProjectGallery → project_opened → MainWindow._on_open_project(path)
ProjectCard.rename_requested → ProjectGallery → project_renamed → MainWindow._on_project_renamed(path, new_name)
ProjectCard.delete_requested → ProjectGallery → project_deleted → MainWindow._on_project_deleted(path)
```

---

## 5. 集成方案

### 5.1 Recorder → Project 创建流程

修改 `MainWindow._on_recording_stopped()`，在现有录制完成逻辑之后追加：

```
录制完成 → 已有 _recorded_data
  │
  ├─ 1. 保存源视频到临时路径（或直接使用 compositor 渲染）
  │      方式: 使用 ExportWorker 导出为 source.mp4，保存到项目目录
  │      视频路径: {projects_dir}/{timestamp}/{source.mp4}
  │
  ├─ 2. 调用 ProjectManager.create_project()
  │      ├─ 创建项目目录
  │      ├─ 生成缩略图 (FFmpeg: ffmpeg -ss 1.0 -i source.mp4 -vframes 1 -q:v 2 thumbnail.png)
  │      └─ 保存 project.json
  │
  └─ 3. 刷新 ProjectGallery
```

**关键集成点**：录制完成后自动导出源视频 → 创建项目 → 刷新画廊。源视频导出复用现有 `ExportWorker`，但使用快速预设（720p, 较低码率）以加快保存速度。

### 5.2 MainWindow 集成

```python
# MainWindow 修改点

class MainWindow(FluentWindow):
    def __init__(self, config: AppConfig):
        # ... 现有初始化 ...
        self._project_manager = ProjectManager(config.projects_dir)

    def _setup_project_interface(self):
        # 替换: 删除 QListWidget，改用 ProjectGallery
        self._project_gallery = ProjectGallery()
        self._project_gallery.project_opened.connect(self._on_open_project)
        self._project_gallery.project_deleted.connect(self._on_project_deleted)
        self._project_gallery.project_renamed.connect(self._on_project_renamed)
        layout.addWidget(self._project_gallery)
        # 初始加载
        self._refresh_project_gallery()

    def _on_recording_stopped(self):
        # ... 现有逻辑 ...
        # 追加: 自动创建项目
        self._auto_create_project()

    def _auto_create_project(self):
        """录制完成后自动创建项目"""
        # 1. 导出源视频
        # 2. 创建项目
        # 3. 刷新画廊

    def _on_open_project(self, path: str):
        """打开已有项目，加载到编辑器"""
        project = self._project_manager.open_project(path)
        # 加载到 compositor，切换到编辑器界面

    def _on_project_deleted(self, path: str):
        """删除项目"""
        self._project_manager.delete_project(path)
        self._refresh_project_gallery()

    def _on_project_renamed(self, path: str, new_name: str):
        """重命名项目"""
        self._project_manager.rename_project(path, new_name)
        self._refresh_project_gallery()
```

### 5.3 SettingsDialog 集成

在 `_build_general_tab()` 中添加"项目目录"设置行：

```python
def _build_general_tab(self):
    # ... 现有帧率、码率设置 ...
    # 新增: 项目目录
    self._projects_dir_edit = QLineEdit(self._config.projects_dir)
    self._projects_dir_edit.setReadOnly(True)
    browse_btn = QPushButton("浏览...")
    browse_btn.clicked.connect(self._browse_projects_dir)
    # 布局: 项目目录: [路径输入框] [浏览...]
```

### 5.4 缩略图生成方案

使用 FFmpeg 从源视频中截取一帧：

```bash
ffmpeg -ss 1.0 -i {source_video} -vframes 1 -vf "scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2" -q:v 2 {output_thumbnail}
```

- `-ss 1.0`：从第 1 秒处截取（避免片头黑帧）
- `-vframes 1`：只取 1 帧
- `-vf scale=...`：缩放到 320x180，保持宽高比，居中填充
- `-q:v 2`：高质量 JPEG 输出（PNG 编码）

**降级策略**：如果 FFmpeg 不可用或源视频不存在，使用默认占位图（纯色背景 + 项目名称文字）。

---

## 6. 实施计划

### 6.1 子任务拆分及执行顺序

| 序号 | 任务 | 文件 | 依赖 | 验收标准 |
|------|------|------|------|----------|
| 1 | Project 类新增字段 | `core/project.py` | 无 | `save()`/`load()` 正确读写新字段 |
| 2 | ProjectManager 实现 | `core/project_manager.py`（新建） | 1 | `list_projects()` 返回正确列表；`create_project()` 创建完整目录结构 |
| 3 | ProjectCard 组件 | `ui/project_card.py`（新建） | 2 | 卡片渲染正确，点击/双击/右键事件触发 |
| 4 | ProjectGallery 组件 | `ui/project_gallery.py`（新建） | 3 | 网格布局正确，信号转发正确 |
| 5 | MainWindow 集成 | `app/main_window.py` | 2,4 | 录制后自动创建项目；画廊显示正确；打开/删除/重命名功能正常 |
| 6 | SettingsDialog 项目目录 | `ui/settings_dialog.py` | 无 | 可浏览/修改项目目录，保存后生效 |

### 6.2 风险点及对策

| 风险 | 影响 | 对策 |
|------|------|------|
| FFmpeg 未安装 | 缩略图生成失败 | 降级使用默认占位图 |
| 源视频保存耗时 | 录制完成后等待时间长 | 异步导出，后台线程执行 |
| 项目目录权限不足 | 创建/删除失败 | 捕获异常，InfoBar 提示用户 |
| 旧版 project.json 缺少新字段 | load() 失败 | 新字段均有默认值，`data.get()` 兜底 |

---

## 7. 技术选型与约束

### 7.1 技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| 数据存储 | JSON 文件 + 目录结构 | 无需数据库，项目可自由移动/备份 |
| 缩略图生成 | FFmpeg CLI | 现有依赖，无需新库 |
| UI 布局 | PyQt5 FlowLayout | 无外部依赖，与现有 qfluentwidgets 风格兼容 |
| 异步导出 | QThread + ExportWorker | 复用现有导出架构 |

### 7.2 编码规范

- 所有新文件使用 `# -*- coding: utf-8 -*-` 头
- 类名使用 PascalCase，方法名使用 snake_case
- 信号命名使用 `snake_case`（如 `project_opened`）
- 遵循现有项目的样式表组织方式（内联 QSS）

### 7.3 安全考虑

- 删除项目前弹出确认对话框（`QMessageBox.question`）
- `delete_project()` 使用 `shutil.rmtree`，捕获异常防止误删
- 项目目录路径验证：确保在 `projects_dir` 范围内，防止路径穿越
- 缩略图生成使用 `subprocess.run` 带 `timeout=30` 防止卡死