# ADR: 编辑器快捷键注册表与 QSettings 配置持久化

**日期：** 2026-07-19  
**状态：** Proposed  
**关联：** Issue #105 / `docs/dev/specs/recordly-editor-usability-fixes.md`

---

## 背景

Recordly 的播放、撤销/重做和时间线编辑键位分散在 `MainWindow` 的 `QShortcut`、`TimelineWidget.keyPressEvent()`、菜单与 ToolTip 字符串中。新增可配置快捷键若继续逐处读取 `QSettings`，会造成默认值、冲突规则和显示文本再次分叉。

本决策同时确定：

1. 12 个编辑器动作的唯一注册位置；
2. 快捷键的持久化位置与格式；
3. 动态更新后窗口级和时间线级快捷键的路由方式。

## 决策

### 决策 1：使用纯 Python `ShortcutRegistry` 作为唯一动作目录

新增 `core/shortcuts.py`，定义不可变 `ShortcutAction`（`action_id`、显示名称、分类、默认 PortableText 键位、`scope`）和 `ShortcutRegistry`。

- 注册表定义固定的 12 个动作及默认键位。
- 注册表管理当前绑定快照、未知 action、空/非法键位和冲突校验；不导入 PyQt，不持有 handler、QSettings 或 QWidget。
- Qt 层负责 `QKeySequence` 的 PortableText 规范化、事件捕获和实际动作分发。
- `MainWindow` 只维护窗口级 action 的 `QShortcut`；`TimelineWidget` 只在自身 `keyPressEvent()` 中匹配时间线 action。

### 决策 2：快捷键作为 AppConfig 的机器级偏好，逐 action 写入 QSettings

`AppConfig.shortcuts` 保存 `dict[str, str]`，使用现有：

```text
QSettings("Recordly", "Recordly")
shortcuts/<action_id> = <QKeySequence.PortableText>
```

例如 `shortcuts/undo = Ctrl+Z`、`shortcuts/nudge_left = Left`。缺失键或无法解析的值回退目录默认值。保存时写入全部 12 项并 `sync()`。

快捷键不写入 `project.json`，也不新增 schema 版本。设置对话框采用草稿：单行编辑和恢复只改草稿；点击窗口“保存”后完整校验、替换 registry、保存 AppConfig，并通知 MainWindow 立即重绑；点击“取消”不产生副作用。

### 决策 3：窗口级快捷键保留 QShortcut + WindowShortcut；重复配置按键序列分组分发

- 每个不同的窗口级 PortableText 键序列对应一个 `QShortcut`，`Qt.WindowShortcut`，`autoRepeat=False`。
- 激活后先复用 `_is_editor_active_and_safe()`；通过后按 action 目录顺序调用 handler。
- 正常设置 UI 不允许两个 action 保存相同键位。若用户手工修改 QSettings 形成重复，分组让所有动作确定性生效，避免多个同键 `QShortcut` 的 ambiguous 行为；设置页下次保存前要求消除冲突。
- 菜单、工具栏 ToolTip 和快捷键表显示均从 registry 读取；`QAction` 不承担输入处理。

## 理由

1. **单一事实源。** 新增动作只需更新目录；持久化、设置 UI、路由和提示均可按 `action_id` 消费，避免硬编码漂移。
2. **保持分层。** ADR-007 要求 `core` 保持 Qt 无关。注册表仅存字符串和规则，QSettings/PyQt 细节保留在 `app`、`ui`。
3. **兼容既有输入边界。** ADR `2026-07-19-undo-redo-shortcuts.md` 已验证 `QShortcut + Qt.WindowShortcut + 焦点守卫` 适合 Space、撤销和重做；Timeline 编辑操作仍受 Timeline 焦点限制。
4. **用户偏好不是项目内容。** 快捷键反映用户工作习惯，应跨项目和应用重启保留；把它写入 project.json 会导致打开其他项目意外改变全局操作习惯。
5. **PortableText 适合存储。** 它是可解析的稳定字符串；NativeText 仅用于本机显示，允许 Qt 在 macOS 上显示 Cmd 符号。
6. **草稿避免取消副作用。** 现有 SettingsDialog 已有统一保存/取消体验；快捷键编辑不能绕过它。

## 备选方案

### 方案 A：每个 Widget 直接读写 QSettings

拒绝。会使 Timeline、MainWindow、设置页各自维护默认值和冲突规则；动态刷新、菜单显示和测试都会分叉。

### 方案 B：把 12 个键位建模为 AppConfig 的 12 个 dataclass 字段

拒绝。动作元数据仍会在设置页和路由处重复，新增 action 需要同步修改多个结构；字典按 action_id 与注册表天然对齐。

### 方案 C：将 QKeySequence 或 QShortcut 放入 core 注册表

拒绝。会让 `core` 依赖 PyQt，违背 ADR-007 的分层边界，且纯单元测试需要创建 Qt 环境。

### 方案 D：所有快捷键改由 MainWindow eventFilter 全局拦截

拒绝。会抢占输入框、弹窗和 Timeline 以外控件的键盘语义；比现有 QShortcut + widget 焦点边界更侵入、更难测试。

### 方案 E：使用 QAction.setShortcut() 统一处理窗口级快捷键

拒绝。Action 的可见性/启用状态与输入行为耦合，难以复用 `_is_editor_active_and_safe()`；与已采纳的 undo/redo ADR 不一致。

### 方案 F：将快捷键写入 project.json

拒绝。用户偏好会随项目复制、覆盖且需要 schema 迁移；不符合用户级设置的生命周期。

## 后果

### 正向

- 全部 12 个默认键位、显示文本和冲突规则集中可审计。
- 修改后无需重启即可生效，重启后由 QSettings 恢复。
- 不新增依赖、不修改项目 JSON 或命令层。
- 保持 WindowShortcut 的 modal/popup/文本焦点保护和 Timeline 的强焦点边界。

### 代价

- 新增一个小型核心模块、配置映射和设置表格，需覆盖 Qt 捕获与重绑的 GUI 测试。
- `MainWindow` 需要维护动作 ID 到既有 handler 的显式映射，并在设置保存后刷新 QShortcut、菜单和 ToolTip。
- 外部手工制造的重复配置有确定性但可能组合多个动作；正常设置页面会禁止创建该状态。

## 兼容性

- 无 `shortcuts/*` 的既有 QSettings 自动使用默认值。
- 默认值保持当前 Space、Ctrl+Z、Ctrl+Shift+Z、Ctrl+Y、X、S、Delete、Backspace、I、O、Left、Right 行为。
- 不影响 ADR-005 双页面边界、ADR-006 JSON 持久化、ADR-007 Controller 分层，以及已采纳的 Timeline source 同步和 undo/redo QShortcut 决策。
