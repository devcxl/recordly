---
id: T1
title: "快捷键注册表与 QSettings 持久化"
type: backend
depends_on: []
acceptance:
  - "ShortcutRegistry 提供固定的 12 个 action、按 scope 查询、绑定快照、单项与整批原子校验及恢复默认。"
  - "注册表保持纯 Python，不导入 PyQt、AppConfig 或 UI 模块；默认 PortableText 键位唯一。"
  - "AppConfig 从 shortcuts/<action_id> 读取并保存全部 12 项，缺失或 Qt 无法解析的值回退默认并调用 sync()。"
  - "新增的注册表和配置测试覆盖目录、冲突、原子替换、恢复默认、QSettings 往返和旧配置兼容。"
files:
  - "core/shortcuts.py"
  - "app/config.py"
  - "tests/test_shortcuts.py"
  - "tests/test_config.py"
issue_number: 106
---

## 目标

建立 ADR 定义的快捷键唯一事实源，并将用户绑定作为 `AppConfig` 的机器级 QSettings 偏好持久化；不接入任何 QWidget 或编辑器动作。

## 实现边界

- 新增纯 Python `ShortcutAction`、`ShortcutValidation` 和 `ShortcutRegistry`，目录严格包含技术方案 3.2 节的 12 个 action、`scope` 与默认 `QKeySequence.PortableText`。
- `ShortcutRegistry` 负责 action ID、当前绑定、按 scope 查询、冲突检测、单行/全部恢复及整批原子替换；未知 action、空值和冲突必须返回方案 3.4 节对应结果码，失败不得修改内存映射。
- `AppConfig.shortcuts` 使用安全的 `default_factory`；`load()` 对每个目录 action 从 `shortcuts/<action_id>` 读取，缺失或 UI 层无法解析的值回退默认；`save()` 写入全部 12 项并执行 `sync()`。
- 不修改 `project.json`、`core/commands.py`、`MainWindow`、`TimelineWidget` 或 `SettingsDialog`。

## 协作契约

- 向 T2/T3/T4 提供 `ShortcutRegistry(config.shortcuts)`、`actions(scope)`、`binding(action_id)`、`bindings()`、`validate()`、`replace_bindings()`、`reset_binding()`、`reset_all()`。
- 绑定值是 PortableText 字符串；Qt 事件和显示文本转换由 UI 任务处理。
- `config.shortcuts` 始终包含目录中的 12 个 action ID；消费者不得从 QSettings 直接读取快捷键。

## 验收与验证

1. `tests/test_shortcuts.py` 覆盖 12 个唯一 action/default、scope、同 action 覆盖、跨 action 冲突、恢复与整批失败不部分更新。
2. `tests/test_config.py` 覆盖缺失键默认回退、12 项 QSettings 往返、非法值回退、既有配置字段不退化和 `sync()`。
3. 执行：`QT_QPA_PLATFORM=offscreen pytest -q tests/test_shortcuts.py tests/test_config.py`。

## Worktree

- 分支：`feat/recordly-shortcut-registry-persistence`
- 仅修改本任务 frontmatter `files` 中的实现与测试文件；不得提前接入 UI 路由。

## 预估

3 小时。主要风险是将 Qt 解析逻辑泄漏到 `core`；保持注册表只处理字符串和规则。
