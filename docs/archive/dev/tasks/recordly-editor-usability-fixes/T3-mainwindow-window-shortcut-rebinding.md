---
id: T3
title: "MainWindow 窗口级快捷键重绑与提示刷新"
type: frontend
depends_on:
  - T1
acceptance:
  - "MainWindow 从 AppConfig.shortcuts 创建共享 ShortcutRegistry，并以实际 PortableText 键序列分组创建窗口级 QShortcut。"
  - "play_pause、undo、redo、redo_alt 使用 WindowShortcut、关闭 auto-repeat，且继续经过现有编辑器安全焦点守卫。"
  - "设置保存后窗口级旧键失效、新键立即生效；外部重复配置按 action 目录顺序确定性分发。"
  - "撤销/重做菜单文字和工具栏 ToolTip 从注册表读取当前主键/备用键，不再硬编码 Ctrl+Z 或 Ctrl+Shift+Z。"
files:
  - "app/main_window.py"
  - "tests/test_main_window.py"
issue_number: 108
---

## 目标

将 MainWindow 的 Space、撤销和重做三个硬编码 `QShortcut` 迁移为 T1 注册表驱动的窗口级重绑机制，并同步菜单和 ToolTip 提示。

## 实现边界

- MainWindow 初始化一个基于 `config.shortcuts` 的共享注册表，替换 `_setup_space_shortcut()` 和 `_setup_undo_redo_shortcuts()` 为可重复调用的 `_rebind_window_shortcuts()`。
- 按实际 PortableText 键序列分组：每个键序列只创建一个 `QShortcut`，`Qt.WindowShortcut`、`autoRepeat=False`；激活后先复用 `_is_editor_active_and_safe()`，再按 action 目录顺序调用既有播放/撤销/重做 handler。
- 设置窗口 Accepted 后，用 `config.shortcuts` 原子更新共享注册表并重绑窗口级快捷键；本任务不向 Timeline 注入注册表，该组合根连接由 T5 完成。
- 编辑菜单及撤销/重做工具栏 ToolTip 从当前注册表生成主/备用键显示；不以 `QAction` 承担输入处理。
- 不修改 `ui/settings_dialog.py`、`ui/timeline.py`、`core/shortcuts.py` 或 `app/config.py`。

## 协作契约

- T3 提供 `self._shortcut_registry` 和可重入的 `_rebind_window_shortcuts()`；T5 在设置成功后将同一对象传给 Timeline。
- T2 的现有 `SettingsDialog(config, parent)` 签名不变；T3 只读取其保存后的 `config.shortcuts`。

## 验收与验证

1. 测试覆盖三个窗口范围动作的 context、auto-repeat、编辑器/首页/非活跃窗口/modal/popup/文本输入守卫。
2. 测试设置保存后旧键不触发、新键触发，及外部重复配置不产生 Qt ambiguous shortcut。
3. 测试 undo/redo 菜单和 ToolTip 显示当前注册表的主键/备用键。
4. 执行：`QT_QPA_PLATFORM=offscreen pytest -q tests/test_main_window.py`。

## Worktree

- 分支：`feat/recordly-mainwindow-shortcut-rebinding`
- 可与 T2/T4 并行，仅依赖 T1；不得提前改动 Timeline 路由。

## 预估

3 小时。主要风险是旧 `QShortcut` 未销毁导致双触发；重绑必须先断开并删除旧对象引用。
