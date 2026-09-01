---
id: T2
title: "设置页快捷键编辑、冲突提示与恢复默认"
type: frontend
depends_on:
  - T1
acceptance:
  - "SettingsDialog 新增快捷键 Tab，按分类展示全部 12 个操作、当前 NativeText 键位、编辑和单行恢复默认入口。"
  - "捕获对话框拒绝纯修饰键，正确捕获含修饰键组合；Esc 或取消不会改变草稿。"
  - "冲突或非法键位提示且不改草稿；单行和全部恢复默认按草稿语义工作，全部恢复需要二次确认。"
  - "仅点击设置窗口保存后才校验、写入 config.shortcuts 并 save()；取消不修改配置或 QSettings。"
files:
  - "ui/settings_dialog.py"
  - "tests/test_settings_dialog.py"
issue_number: 107
---

## 目标

在现有 `SettingsDialog` 中交付可编辑的快捷键 Tab。该任务只处理设置草稿和持久化，不直接创建 `QShortcut` 或调用编辑器 handler。

## 实现边界

- 以 T1 的 `ShortcutRegistry` 从 `config.shortcuts` 建立本地草稿；表格可滚动，显示分类、操作、当前快捷键、编辑和恢复默认，窗口最小尺寸满足方案 3.5 节。
- 将 `ShortcutCaptureDialog` 保持为 `settings_dialog.py` 内私有对话框；`QKeySequence` 使用 PortableText 保存、NativeText 展示，忽略单独 Ctrl/Alt/Shift/Meta，Esc 取消。
- 编辑、单行恢复和全部恢复只改草稿；冲突/空/非法错误保留在对话框且显示技术方案 3.4 节的用户文案。全部恢复默认须二次确认。
- `_on_save()` 完整校验后写入 `config.shortcuts` 并调用 `config.save()`；`reject()` 不产生快捷键副作用。保持构造函数 `SettingsDialog(config, parent=None)`，避免与并行 T3 产生接口依赖。
- 不修改 `app/main_window.py`、`ui/timeline.py`、`core/shortcuts.py` 或 `app/config.py`。

## 协作契约

- 保存成功后，`config.shortcuts` 是 T1 注册表的完整、无冲突 PortableText 映射；T3/T5 负责把它应用到运行中的窗口和 Timeline。
- 任何保存失败或取消必须使 `config.shortcuts` 与进入对话框时完全一致。

## 验收与验证

1. offscreen GUI 测试验证 12 行、分类、双击/编辑、`Ctrl+Shift+K` 捕获、纯修饰键拒绝、冲突提示、单行恢复、全量恢复确认、取消无副作用及保存落盘。
2. 既有通用、光标、缩放、预览和关于 Tab 的保存行为保持通过。
3. 执行：`QT_QPA_PLATFORM=offscreen pytest -q tests/test_settings_dialog.py tests/test_main_window.py`。

## Worktree

- 分支：`feat/recordly-settings-shortcut-editor`
- 独立工作树可基于 T1 实现；不依赖 T3/T4 的运行时重绑，避免并行代码耦合。

## 预估

4 小时。主要风险是捕获对话框修改真实配置；必须以草稿注册表隔离所有临时改动。
