---
name: "project-gallery"
depends_on: ["project-card"]
labels: ["frontend"]
worktree_root: ".worktree/project-gallery/"
---

## 目标

新建 `ui/project_gallery.py`，实现 `ProjectGallery` 卡片网格容器。

## 实现要点

1. 继承 `QScrollArea`，内部使用 `FlowLayout` 实现自适应网格布局
2. `set_projects(summaries)`：清空并重新填充 ProjectCard
3. `refresh()`：重新调用 `ProjectManager.list_projects()` 并刷新显示
4. 信号转发：`project_opened`、`project_deleted`、`project_renamed`
5. 右键菜单：删除 → 确认对话框 → 发射 `project_deleted`
6. 空状态处理：无项目时显示引导文字"还没有项目，开始录制吧！"

## 验收标准

- 卡片在网格中正确排列，窗口缩放时自适应换行
- 点击卡片 → `project_opened` 信号携带正确路径
- 删除操作弹出确认对话框，确认后正确删除
- 空状态显示引导文字

## Worktree
- 路径: `.worktree/project-gallery/`
- 分支: `feat/project-gallery`
- 创建时机: `/code` 阶段首次执行时自动创建
- 清理时机: PR 合并后自动删除