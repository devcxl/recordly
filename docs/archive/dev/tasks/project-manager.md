---
name: "project-manager"
depends_on: ["project-model-fields"]
labels: ["backend"]
worktree_root: ".worktree/project-manager/"
---

## 目标

新建 `core/project_manager.py`，实现 `ProjectManager` 类和 `ProjectSummary` 数据类。

## 实现要点

1. `ProjectSummary` dataclass：`name`、`path`、`modified_at`、`duration`、`thumbnail_path`
2. `ProjectManager.__init__(projects_dir)`：设置工作目录
3. `list_projects()`：扫描 `projects_dir` 下所有包含 `project.json` 的子目录，只读取元数据字段，按 `modified_at` 降序排列
4. `create_project(name, project, source_video_path)`：创建子目录 → 复制源视频 → 生成缩略图 → 保存 `project.json`
5. `open_project(project_path)`：加载完整 `Project` 对象
6. `delete_project(project_path)`：`shutil.rmtree`，捕获异常
7. `rename_project(project_path, new_name)`：更新 `project.json` 中的 `name` 字段
8. `generate_thumbnail(video_path, output_path, timestamp=0.0)`：调用 FFmpeg 截帧，失败降级为占位图

## 验收标准

- `list_projects()` 返回正确的项目列表
- `create_project()` 创建完整目录结构，包含 `project.json`、`thumbnail.png`、源视频
- `delete_project()` 正确删除整个目录
- `rename_project()` 更新 JSON 中的名称
- FFmpeg 不可用时生成占位图而非崩溃
- 单元测试覆盖所有方法

## Worktree
- 路径: `.worktree/project-manager/`
- 分支: `feat/project-manager`
- 创建时机: `/code` 阶段首次执行时自动创建
- 清理时机: PR 合并后自动删除