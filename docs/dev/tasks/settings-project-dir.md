---
name: "settings-project-dir"
depends_on: []
labels: ["frontend"]
worktree_root: ".worktree/settings-project-dir/"
---

## 目标

在 `ui/settings_dialog.py` 中添加"项目目录"设置项。

## 实现要点

1. 在 `_build_general_tab()` 中添加项目目录设置行
2. 只读 `QLineEdit` 显示当前路径 + "浏览..." 按钮
3. 浏览按钮 → `QFileDialog.getExistingDirectory()`
4. 保存后写入 `AppConfig.projects_dir`
5. AppConfig 已有 `projects_dir` 属性，检查是否完备

## 验收标准

- 项目目录设置项显示正确
- 浏览按钮可打开目录选择对话框
- 选择后路径显示在输入框中
- 保存后重启应用，项目目录保持生效

## Worktree
- 路径: `.worktree/settings-project-dir/`
- 分支: `feat/settings-project-dir`
- 创建时机: `/code` 阶段首次执行时自动创建
- 清理时机: PR 合并后自动删除