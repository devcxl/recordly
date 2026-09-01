---
id: T2
title: "MainWindow 快捷键 + 编辑菜单 + 工具栏按钮"
depends_on: ["T1"]
estimated_effort: "4h"
assignee_type: "frontend"
---

## 目标

在 `app/main_window.py` 中新增撤销/重做的三个入口：快捷键（Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y）、菜单栏"编辑"菜单、工具栏按钮。所有入口复用现有 `_on_undo()` / `_on_redo()` 方法，并动态显示当前操作名称。

## 实现要点

### 1. 守卫方法提取 — `_is_editor_active_and_safe()`

将 `_on_space_shortcut()` (L327-340) 中的 5 个守卫条件提取为独立方法：

```python
def _is_editor_active_and_safe(self) -> bool:
    """编辑器页面活跃且焦点不在输入控件内。"""
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

然后重构 `_on_space_shortcut()` 为：

```python
def _on_space_shortcut(self):
    if not self._is_editor_active_and_safe():
        return
    self._on_play_toggle()
```

### 2. 快捷键创建 — `_setup_undo_redo_shortcuts()`

在 `_setup_navigation()` 中（`_setup_space_shortcut()` 之后）新增调用 `_setup_undo_redo_shortcuts()`。

三个 `QShortcut`，使用 `Qt.WindowShortcut`（与 Space 快捷键一致的模式）：

| 快捷键 | 键序列 | 连接方法 |
|--------|--------|---------|
| Ctrl+Z | `QKeySequence.Undo` | `_maybe_undo` |
| Ctrl+Shift+Z | `QKeySequence("Ctrl+Shift+Z")` | `_maybe_redo` |
| Ctrl+Y | `QKeySequence("Ctrl+Y")` | `_maybe_redo` |

`_maybe_undo()` / `_maybe_redo()` 复用 `_is_editor_active_and_safe()` 守卫：

```python
def _maybe_undo(self):
    if not self._is_editor_active_and_safe():
        return
    self._on_undo()

def _maybe_redo(self):
    if not self._is_editor_active_and_safe():
        return
    self._on_redo()
```

### 3. 编辑菜单 — 在 `_setup_menus()` 中新增

在"文件"菜单之前插入"编辑"菜单：

```python
# 编辑菜单
edit_menu = menubar.addMenu("编辑")
self._edit_menu = edit_menu
self._menu_undo = edit_menu.addAction("撤销", self._maybe_undo, QKeySequence.Undo)
self._menu_redo = edit_menu.addAction("重做", self._maybe_redo, QKeySequence("Ctrl+Shift+Z"))
```

**重要：** 存储 `self._edit_menu` 引用以便在 `_update_menu_visibility()` 中控制整个编辑菜单的可见性。

`QAction.setShortcut()` 仅用于菜单项右侧显示快捷键文本，实际按键由 `QShortcut` 处理（见 ADR 决策 1）。

### 4. 工具栏按钮 — 在 `_setup_toolbar()` 中新增

在播放控制按钮之前插入撤销/重做按钮：

```python
self._btn_undo = QToolButton()
self._btn_undo.setText("↩")
self._btn_undo.setToolTip("撤销 (Ctrl+Z)")
self._btn_undo.clicked.connect(self._maybe_undo)
self._btn_undo.setEnabled(False)
self._btn_undo.setStyleSheet("font-size: 16px;")

self._btn_redo = QToolButton()
self._btn_redo.setText("↪")
self._btn_redo.setToolTip("重做 (Ctrl+Shift+Z)")
self._btn_redo.clicked.connect(self._maybe_redo)
self._btn_redo.setEnabled(False)
self._btn_redo.setStyleSheet("font-size: 16px;")

self._toolbar.addWidget(self._btn_undo)
self._toolbar.addWidget(self._btn_redo)
self._toolbar.addSeparator()
```

初始状态禁用以防止编辑器未加载时的空操作。

### 5. 状态刷新 — `_refresh_undo_redo_state()`

新增方法，根据 `_timeline.can_undo` / `_timeline.can_redo` 和 `_undo_stack[-1].description()` 动态刷新菜单文本和按钮状态：

- 菜单项：`"撤销 {description()}"` / `"重做 {description()}"` 或回退到 `"撤销"` / `"重做"`
- 按钮 ToolTip：`"撤销 {desc} (Ctrl+Z)"` / `"重做 {desc} (Ctrl+Shift+Z)"`
- enable/disable 由栈状态控制

### 6. 信号连接

在 `_on_clips_changed()`（L983-1010）末尾追加 `self._refresh_undo_redo_state()` 调用。由于 `_connect_timeline_signals()` 已将 `clips_changed` 连接到 `_on_clips_changed`，add/delete/move/split/undo/redo 等操作后均会自动触发状态刷新。

### 7. 菜单可见性

在 `_update_menu_visibility()`（L463-469）中追加：

```python
self._edit_menu.menuAction().setVisible(is_editor)
```

确保编辑菜单仅在编辑器页面可见。

## 改动范围

- 文件：`app/main_window.py`
- 行数：~120 行
  - `_is_editor_active_and_safe()`：~15 行
  - `_setup_undo_redo_shortcuts()` + 调用 `_setup_navigation()`：~20 行
  - `_maybe_undo()` / `_maybe_redo()`：~8 行
  - `_on_space_shortcut()` 重构：~3 行修改
  - `_setup_menus()` 编辑菜单：~10 行
  - `_setup_toolbar()` 按钮：~15 行
  - `_refresh_undo_redo_state()`：~30 行
  - `_update_menu_visibility()`：~1 行
  - `_on_clips_changed()` 追加调用：~1 行

## 验收标准

- [ ] Ctrl+Z 在编辑器中触发撤销，在首页/输入框焦点下不触发
- [ ] Ctrl+Shift+Z 和 Ctrl+Y 触发重做，行为一致
- [ ] Space 快捷键行为不变（守卫提取后无回归）
- [ ] 编辑菜单在编辑器页可见、首页隐藏
- [ ] 菜单项文本动态显示 `"撤销 移动片段"` / `"重做 移动片段"`
- [ ] 工具栏按钮 ToolTip 显示快捷键 + 操作名称
- [ ] 无历史时菜单和按钮灰显、不可点击
- [ ] 撤销后执行新操作 → 重做栈清空 → Ctrl+Y 无效果
- [ ] 项目加载后菜单/按钮状态正确初始化（`clips_changed` 触发）
- [ ] 现有 `test_main_window.py` 和 `test_timeline.py` 全绿

## 风险

- `_is_editor_active_and_safe()` 提取后可能引入 Space 快捷键回归 → 冒烟测试验证
- 菜单项快捷键显示文本在 macOS 上依赖 Qt 的平台映射（`QKeySequence.Undo` → `⌘Z`） → 如不生效，备选手动 `setText("撤销\tCtrl+Z")`
- 工具栏 Unicode 字符 `↩`/`↪` 跨平台渲染不一致 → 备选纯文本 `"撤"` / `"重"`

Parent: #93
