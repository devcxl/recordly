---
name: "project-card"
depends_on: ["project-manager"]
labels: ["frontend"]
worktree_root: ".worktree/project-card/"
---

## 目标

新建 `ui/project_card.py`，实现 `ProjectCard` 卡片组件。

## 实现要点

1. 继承 `QFrame`，固定尺寸 240×180
2. 布局：上方缩略图 QLabel（240×135）+ 下方项目名称 QLabel + 时长 QLabel
3. 双击名称 → 变为 QLineEdit 编辑模式，Enter 确认 → 发射 `rename_requested` 信号
4. 点击卡片 → 发射 `clicked` 信号
5. 右键菜单 → "删除" 动作 → 发射 `delete_requested` 信号
6. 缩略图加载失败时显示占位图（纯色背景 + 文字）
7. 样式：圆角边框、阴影效果（使用 QSS）

## 验收标准

- 卡片渲染正确，缩略图 + 名称 + 时长显示正常
- 点击、双击、右键事件正确触发对应信号
- 双击名称可编辑，Enter 确认后信号携带新名称
- 缩略图缺失时显示占位图

## Worktree
- 路径: `.worktree/project-card/`
- 分支: `feat/project-card`
- 创建时机: `/code` 阶段首次执行时自动创建
- 清理时机: PR 合并后自动删除