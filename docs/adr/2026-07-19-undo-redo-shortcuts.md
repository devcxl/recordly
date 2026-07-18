# ADR: 撤销/重做快捷键使用 QShortcut + 命令描述独立于 UI

**日期:** 2026-07-19
**状态:** Proposed
**关联:** Issue #93 / `docs/dev/specs/recordly-undo-redo-shortcuts.md`

---

## 背景

Recordly 需要为撤销/重做功能添加 Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y 快捷键入口，同时需要在菜单和工具栏中动态显示当前可撤销/重做的操作名称。

两个关键技术选择需要决策：
1. 快捷键实现方式 — `QAction.setShortcut()` vs `QShortcut`
2. 操作名称来源 — 在命令层新增 `description()` 方法 vs UI 层硬编码命令类名→中文映射表

---

## 决策 1：快捷键使用 `QShortcut` + `Qt.WindowShortcut`，而非 `QAction.setShortcut()`

### 上下文

在 PyQt5 中，为菜单项绑定快捷键有两种主流方式：

**方式 A: `QAction.setShortcut()`**
```python
action = menu.addAction("撤销", self._on_undo, QKeySequence.Undo)
```
- 优点：一行代码，快捷键文本自动显示在菜单项右侧
- 缺点：快捷键在菜单不可见时可能被禁用；无法独立控制快捷键的上下文和 auto-repeat；难以实现焦点排除守卫

**方式 B: `QShortcut` + `Qt.WindowShortcut`**
```python
self._undo_shortcut = QShortcut(QKeySequence.Undo, self)
self._undo_shortcut.setContext(Qt.WindowShortcut)
self._undo_shortcut.activated.connect(self._maybe_undo)
```
- 优点：完全控制上下文、auto-repeat、守卫逻辑；与 Space 快捷键一致的实现模式
- 缺点：需要手动设置菜单项的快捷键显示文本（`QAction.setShortcut()` 仅用于显示，不处理输入）

### 选择：方式 B（QShortcut）

理由：

1. **焦点排除守卫一致性。** Space 快捷键已使用 `QShortcut` + 守卫方法，验证了该模式在 Recordly 的首页/编辑器双页面架构中工作良好。Ctrl+Z 复用相同守卫 `_is_editor_active_and_safe()`，无需为 QAction 发明新的焦点控制机制。

2. **`QAction.setShortcut()` 的隐式上下文问题。** QAction 的快捷键行为与 Action 的可见性、所属菜单/工具栏的启禁用状态耦合。当编辑菜单在首页不可见时，QAction 快捷键的行为在不同平台和 Qt 版本间不一致（有的平台禁用，有的不禁用）。`QShortcut` 的行为完全由显式的上下文和守卫控制，无耦合。

3. **独立于菜单生命周期。** `QShortcut` 是顶层窗口的子对象，其生命周期与窗口一致，不受菜单创建/销毁影响。后续若菜单重构，快捷键不受波及。

4. **菜单显示文本不受影响。** 可以为 `QAction` 设置 shortcut（仅用于菜单文本显示 `\tCtrl+Z`），但不依赖它处理按键。这在 Qt 中是完全合法的用法。

### 选择：2 个重做快捷键（Ctrl+Shift+Z + Ctrl+Y）

大多数桌面应用同时支持 Ctrl+Shift+Z（Adobe/Chrome 风格）和 Ctrl+Y（Windows 标准风格）。Recordly 是跨平台应用，支持两种重做快捷键可以覆盖更多用户的肌肉记忆。

两个快捷键共享同一个 `_maybe_redo()` 槽，无需额外逻辑。

### 备选方案

**仅使用 `QAction.setShortcut()`。** 拒绝。无法实现焦点排除守卫（输入框获得焦点时应让 Ctrl+Z 作用于输入框的文本，而非全局撤销）。需要额外的 event filter 或 context 管理，增加复杂度且与其他快捷键模式不一致。

**使用 `eventFilter` 全局拦截。** 拒绝。侵入所有键盘事件，比 QShortcut + 守卫更复杂。Space 快捷键已验证 QShortcut 模式足够。

---

## 决策 2：在命令层新增 `UndoCommand.description()`，而非 UI 层硬编码映射表

### 上下文

菜单和工具栏需要显示"撤销 移动片段"、"重做 删除片段"等动态文本。需要一种机制从当前栈顶命令获取操作名称。

**方式 A: 命令层 `description()` 方法**
```python
class MoveClipCommand(UndoCommand):
    def description(self) -> str:
        return "移动片段"
```
- 命令自己知道自己的语义

**方式 B: UI 层硬编码映射**
```python
_CMD_DESCRIPTIONS = {
    MoveClipCommand: "移动片段",
    DeleteClipCommand: "删除片段",
    ...
}
# 使用：_CMD_DESCRIPTIONS[type(cmd)]
```
- UI 层维护命令类→中文的字典

### 选择：方式 A（命令层 `description()`）

理由：

1. **信息与行为同地（Co-location）。** `MoveClipCommand` 知道自己是"移动片段"操作，这是命令的内在属性。将描述放在命令类中符合单一职责原则的内聚要求。

2. **避免 UI 层导入命令类。** 方式 B 要求 `main_window.py` 导入所有 7 个命令类来构建映射表。当前 `main_window.py` 已导入 `core.commands` 中的类（用于 type hints），但映射表的维护会引入隐式依赖：新增命令时必须同步更新映射表，否则运行时无描述或显示默认类名。

3. **`CompositeCommand` 描述需要命令内部信息。** `CompositeCommand` 的描述需要根据 `sub_commands` 列表推断（如 `"裁剪开头"` vs `"裁剪结尾"`）。方式 B 要么把推断逻辑也放到 UI 层（进一步耦合），要么无法实现。

4. **向后兼容。** 基类 `description()` 默认返回类名，子类不覆写也不破坏现有行为（菜单显示 `"撤销 MoveClipCommand"` 而不是崩溃）。

5. **命令层无 Qt 依赖。** `description()` 返回纯字符串，不引入 PyQt5 依赖，保持 `core/commands.py` 的纯数据层地位。

### 备选方案

**方式 B（UI 层映射表）。** 拒绝。符合"数据与 UI 分离"原则的方向应是数据层提供数据、UI 层消费 — 而非 UI 层反过来定义数据层的元数据。映射表方式制造了双向知识：命令类知道自己做什么，UI 层也必须知道命令类叫什么。新增命令时容易遗忘更新映射表。

---

## 决策 3：守卫逻辑提取为 `_is_editor_active_and_safe()` 方法

### 上下文

Ctrl+Z/Ctrl+Shift+Z/Ctrl+Y 的焦点排除条件与 Space 快捷键完全相同（编辑器页 + 主窗口活跃 + 无 modal/popup + 不在输入控件内）。PRD 明确要求"复用 Space 快捷键的焦点排除模式"。

### 选择：提取共用方法

```python
def _is_editor_active_and_safe(self) -> bool:
    if self._stacked_widget.currentWidget() is not self._editor_interface:
        return False
    if QApplication.activeWindow() is not self:
        return False
    if QApplication.activeModalWidget() is not None:
        return False
    if QApplication.activePopupWidget() is not None:
        return False
    if isinstance(QApplication.focusWidget(), (
        QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
    )):
        return False
    return True
```

理由：
- 消除代码重复（5 行守卫 × 2 快捷键 = 10 行重复）
- 语义清晰的方法名减少未来快捷键开发者误用
- 守卫条件变更时只需改一处

替代方案"复制粘贴守卫代码"被拒绝 — 5 个条件在三处重复是不可接受的。

---

## 影响

- `core/commands.py` 新增 `description()` 方法，纯增量，不影响现有子类
- `app/main_window.py` 新增 ~120 行（快捷键、菜单、按钮、状态刷新）
- `ui/timeline.py` 零修改
- 无项目持久化变更，无新增依赖
