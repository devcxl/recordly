---
name: "mainwindow-integration"
depends_on: ["project-manager", "project-gallery"]
labels: ["backend", "frontend"]
worktree_root: ".worktree/mainwindow-integration/"
---

## 目标

修改 `app/main_window.py`，集成 ProjectGallery 和 ProjectManager，替换空的 QListWidget。

## 实现要点

1. `_setup_project_interface()`：替换 QListWidget 为 ProjectGallery，连接信号
2. 初始化 `ProjectManager`，加载项目列表到画廊
3. `_on_recording_stopped()`：录制完成后 → 保存源视频 → 调用 `ProjectManager.create_project()` → 刷新画廊
4. 源视频保存复用现有 `ExportWorker`，使用快速预设（720p, 低码率）
5. `_on_open_project(path)`：加载项目，切换到编辑器界面
6. `_on_project_deleted(path)`：删除项目，刷新画廊
7. `_on_project_renamed(path, new_name)`：重命名项目，刷新画廊
8. 异常处理：项目目录不存在时创建，权限不足时 InfoBar 提示

## 验收标准

- 主界面项目列表显示卡片网格而非空列表
- 录制完成后自动创建项目，画廊中出现新卡片
- 点击卡片可打开项目继续编辑
- 删除项目后画廊刷新
- 重命名项目后画廊刷新

## Worktree
- 路径: `.worktree/mainwindow-integration/`
- 分支: `feat/mainwindow-integration`
- 创建时机: `/code` 阶段首次执行时自动创建
- 清理时机: PR 合并后自动删除