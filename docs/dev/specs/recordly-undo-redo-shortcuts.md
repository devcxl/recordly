# 撤销/重做快捷键与入口 — 技术方案

**日期:** 2026-07-19
**状态:** Draft
**关联:** Issue #93 / `docs/prd/recordly-undo-redo-shortcuts.md`

---

## 1. 目标与范围

Recordly 的 `UndoCommand` 命令体系（7 种命令）和双栈机制（`_undo_stack`/`_redo_stack`）已在 `core/commands.py` 和 `ui/timeline.py` 中完整实现，`main_window.py` 中 `_on_undo()`/`_on_redo()` 方法也已就绪，但缺少用户入口。本方案在现有架构上增量添加：

1. Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y 快捷键
2. 菜单栏"编辑"菜单（撤销/重做项）
3. 工具栏撤销/重做按钮
4. `UndoCommand.description()` 中文化操作名称

坚持最小设计：不新增模块、不修改 timeline 双栈逻辑、不引入新信号、不改变项目持久化。

---

## 2. 现状与兼容性结论

### 2.1 当前实现

| 组件 | 关键代码 | 职责 |
|------|---------|------|
| `core/commands.py` | `UndoCommand` 抽象基类 + 7 个子类 | 命令封装，纯数据层，无 Qt 依赖 |
| `ui/timeline.py` | `_undo_stack`/`_redo_stack` + `undo()`/`redo()`/`_push_undo()` | 双栈管理，`clips_changed` 信号驱动 UI 刷新 |
| `app/main_window.py` | `_on_undo()` (L1432-1434)、`_on_redo()` (L1436-1438) | 空壳调用，无入口绑定 |
| `app/main_window.py` | `_on_space_shortcut()` (L327-340) | 焦点排除模式（modal/popup/input 守卫） |
| `app/main_window.py` | `_setup_menus()` (L342-357) | 仅有"文件""帮助"菜单 |
| `app/main_window.py` | `_setup_toolbar()` (L359-378) | 仅有播放控制、导出、裁剪、添加音频按钮 |
| `app/main_window.py` | `_on_clips_changed()` (L983-1010) | 已连接 `clips_changed`，负责同步 compositor + 播放控制器 |

### 2.2 兼容性结论

- 快捷键复用 `QShortcut` + `Qt.WindowShortcut`，与 Space 快捷键完全一致的焦点排除模式
- 菜单和工具栏通过已有的 `clips_changed` 信号动态刷新状态
- `UndoCommand.description()` 为新增方法，不影响现有子类（默认回退到类名）
- `_on_undo()`/`_on_redo()` 原样复用，零修改
- timeline.py 的 `undo()`/`redo()`/`can_undo`/`can_redo` 无需修改

---

## 3. 总体架构

```text
Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y
  QShortcut（MainWindow / WindowShortcut）
    → 编辑器页守卫（同 Space 焦点排除模式）
    → MainWindow._on_undo() / _on_redo()
    → TimelineWidget.undo() / redo()
    → clips_changed → MainWindow._on_clips_changed()
                    → MainWindow._refresh_undo_redo_state()

"编辑"菜单
  QMenu("编辑")
    ├── QAction(undo_label)   Ctrl+Z
    └── QAction(redo_label)   Ctrl+Shift+Z
  _refresh_undo_redo_state() 读取 can_undo/can_redo + description()
  由 clips_changed 信号驱动

工具栏按钮
  QToolButton("↩") / QToolButton("↪")
  状态同菜单，ToolTip 显示快捷键+操作名称
  由 clips_changed 信号驱动刷新
```

---

## 4. 详细设计

### 4.1 `UndoCommand.description()` — 命令描述中文化

**文件:** `core/commands.py`

**基类新增:**

```python
class UndoCommand(ABC):
    # ... 现有 execute/undo/__repr__ ...

    def description(self) -> str:
        """返回面向用户的中文操作描述，菜单和 ToolTip 使用。"""
        return self.__class__.__name__
```

**各子类覆写:**

| 命令 | `description()` 返回值 |
|------|----------------------|
| `AddClipCommand` | `"添加片段"` |
| `MoveClipCommand` | `"移动片段"` |
| `DeleteClipCommand` | `"删除片段"` |
| `SplitClipCommand` | `"切割片段"` |
| `ChangeSpeedCommand` | `"变更速度"` |
| `CompositeCommand` | 根据子命令组合返回语义名称（见 4.1.1） |

#### 4.1.1 `CompositeCommand.description()` 推断规则

`CompositeCommand` 不直接知道业务语义，需根据 `sub_commands` 列表推断。当前使用场景只有两处（`timeline.py:trim_in()`、`trim_out()`），均为 `[SplitClipCommand, DeleteClipCommand]`。

推断策略：
- 若 `len(sub_commands) == 2` 且分别为 `SplitClipCommand` + `DeleteClipCommand`：
  - 根据 `DeleteClipCommand.clip_index` 判断删除左半边（clip_index 不变）还是右半边（clip_index + 1）
  - 左半边 → `"裁剪开头"`
  - 右半边 → `"裁剪结尾"`
- 否则 → `f"批量操作({len(sub_commands)}步)"`
- 不遍历子命令 `description()`，避免递归和歧义

**改动范围:** `commands.py` 新增 ~30 行（基类 2 行 + 6 个子类 6 行 + CompositeCommand ~20 行）

---

### 4.2 快捷键 — Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y

**文件:** `app/main_window.py`

#### 4.2.1 创建快捷键

在 `_setup_navigation()` 中（`_setup_space_shortcut()` 之后）新增方法 `_setup_undo_redo_shortcuts()`：

```python
def _setup_undo_redo_shortcuts(self):
    # Ctrl+Z → 撤销
    self._undo_shortcut = QShortcut(QKeySequence.Undo, self)       # Qt 自动映射为 Ctrl+Z
    self._undo_shortcut.setContext(Qt.WindowShortcut)
    self._undo_shortcut.setAutoRepeat(False)
    self._undo_shortcut.activated.connect(self._maybe_undo)

    # Ctrl+Shift+Z → 重做（Adobe 风格）
    self._redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
    self._redo_shortcut.setContext(Qt.WindowShortcut)
    self._redo_shortcut.setAutoRepeat(False)
    self._redo_shortcut.activated.connect(self._maybe_redo)

    # Ctrl+Y → 重做（Windows 标准风格）
    self._redo_y_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
    self._redo_y_shortcut.setContext(Qt.WindowShortcut)
    self._redo_y_shortcut.setAutoRepeat(False)
    self._redo_y_shortcut.activated.connect(self._maybe_redo)
```

**设计决策:** 使用三个独立的 `QShortcut` 而非 `QAction.setShortcut()`，原因见 ADR 决策 1。

#### 4.2.2 焦点排除守卫

新增 `_maybe_undo()` / `_maybe_redo()` 方法，复用 `_on_space_shortcut()` 的守卫逻辑：

```python
def _maybe_undo(self):
    if not self._is_editor_active_and_safe():
        return
    self._on_undo()

def _maybe_redo(self):
    if not self._is_editor_active_and_safe():
        return
    self._on_redo()

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

**重构 `_on_space_shortcut()`:**
```python
def _on_space_shortcut(self):
    if not self._is_editor_active_and_safe():
        return
    self._on_play_toggle()
```

将原本内联在 `_on_space_shortcut()` 中的 5 个守卫条件提取为 `_is_editor_active_and_safe()`，`_on_space_shortcut` 和 `_maybe_undo`/`_maybe_redo` 共用。这避免了代码重复，且 `_is_editor_active_and_safe()` 语义清晰，便于未来新增快捷键复用它。

**注意:** `_on_play_toggle()` 不得移入 `_is_editor_active_and_safe()` — 那个方法只负责守卫判断，播放逻辑仍留在调用方。

**改动范围:** `main_window.py` 新增 ~40 行（3 个方法 + `_setup_undo_redo_shortcuts` 调用），`_on_space_shortcut` 修改 ~3 行（替换为调用 `_is_editor_active_and_safe`）

---

### 4.3 编辑菜单

**文件:** `app/main_window.py`

#### 4.3.1 菜单结构

在 `_setup_menus()` 中，于"文件"菜单之前插入"编辑"菜单：

```python
def _setup_menus(self):
    menubar = self.menuBar()

    # 新增：编辑菜单
    edit_menu = menubar.addMenu("编辑")
    self._menu_undo = edit_menu.addAction("撤销", self._maybe_undo,
                                          QKeySequence.Undo)
    self._menu_redo = edit_menu.addAction("重做", self._maybe_redo,
                                          QKeySequence("Ctrl+Shift+Z"))
    edit_menu.addSeparator()

    # 文件菜单（现有，不变）
    file_menu = menubar.addMenu("文件")
    # ...
```

**重要:** `QAction` 上设置了 `QKeySequence.Undo` 和 `QKeySequence("Ctrl+Shift+Z")` 作为 `QAction.setShortcut()`。但这仅用于菜单项右侧显示快捷键文本，实际快捷键由 `QShortcut` 处理（见 ADR 决策 1）。`QAction` 的 shortcut 不会实际响应按键，因为 `QShortcut` 优先级更高。

#### 4.3.2 状态刷新

新增 `_refresh_undo_redo_state()` 方法：

```python
def _refresh_undo_redo_state(self):
    """根据 timeline 命令栈刷新编辑菜单和工具栏按钮状态。"""
    if not hasattr(self, '_timeline') or not hasattr(self, '_menu_undo'):
        return

    can_undo = self._timeline.can_undo
    can_redo = self._timeline.can_redo

    # 菜单
    if can_undo:
        desc = self._timeline._undo_stack[-1].description()
        self._menu_undo.setText(f"撤销 {desc}")
    else:
        self._menu_undo.setText("撤销")
    self._menu_undo.setEnabled(can_undo)

    if can_redo:
        desc = self._timeline._redo_stack[-1].description()
        self._menu_redo.setText(f"重做 {desc}")
    else:
        self._menu_redo.setText("重做")
    self._menu_redo.setEnabled(can_redo)

    # 工具栏按钮
    self._btn_undo.setEnabled(can_undo)
    if can_undo:
        self._btn_undo.setToolTip(f"撤销 {desc} (Ctrl+Z)")
    else:
        self._btn_undo.setToolTip("撤销 (Ctrl+Z)")

    self._btn_redo.setEnabled(can_redo)
    if can_redo:
        self._btn_redo.setToolTip(f"重做 {desc} (Ctrl+Shift+Z)")
    else:
        self._btn_redo.setToolTip("重做 (Ctrl+Shift+Z)")
```

#### 4.3.3 信号连接

在 `_connect_timeline_signals()` 中，`clips_changed` 已连接 `_on_clips_changed`。在此方法末尾追加 `_refresh_undo_redo_state()` 调用：

```python
def _on_clips_changed(self):
    # ... 现有逻辑（同步 compositor、播放控制器等）...
    self._refresh_undo_redo_state()  # 新增
```

**注意:** `_connect_timeline_signals()` 使用 `try/except disconnect` 模式确保幂等。由于 `_on_clips_changed` 已在此连接，追加调用不会破坏幂等性。

#### 4.3.4 菜单可见性

`_update_menu_visibility()` 中，编辑菜单需要与"文件"菜单在同一条件下显示/隐藏：

```python
def _update_menu_visibility(self):
    is_editor = self._stacked_widget.currentWidget() == self._editor_interface
    self._menu_undo.setVisible(is_editor)       # 新增
    self._menu_redo.setVisible(is_editor)       # 新增
    self._menu_save.setVisible(is_editor)
    self._menu_export.setVisible(is_editor)
    self._menu_back_home.setVisible(is_editor)
    self._menu_settings.setVisible(not is_editor)
```

实际上更简洁的做法是直接隐藏整个"编辑"菜单，需要存储 `self._edit_menu` 引用，然后 `self._edit_menu.menuAction().setVisible(is_editor)`。

**改动范围:** `main_window.py` 新增 ~50 行（`_refresh_undo_redo_state` 方法约 30 行 + 菜单创建代码 15 行 + 信号连接 5 行）

---

### 4.4 工具栏按钮

**文件:** `app/main_window.py`

#### 4.4.1 按钮创建

在 `_setup_toolbar()` 中，在播放控制按钮之前插入（或独立一组后插入）：

```python
def _setup_toolbar(self):
    self._toolbar = QToolBar("工具")
    # ...

    # ── 撤销/重做按钮（新增）────────────────────────────
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
    # ── 播放控制按钮（现有，不变）───────────────────────
    self._add_playback_toolbar_buttons()
    # ...
```

**ToolTip 刷新:** 已在 `_refresh_undo_redo_state()` 中处理（见 4.3.2）。

#### 4.4.2 初始状态

按钮初始 `setEnabled(False)`，与 `_menu_undo`/`_menu_redo` 的初始禁用状态一致。进入编辑器且有操作历史后，`clips_changed` 触发 `_refresh_undo_redo_state()` 激活按钮。

**改动范围:** `main_window.py` `_setup_toolbar()` 新增 ~15 行

---

## 5. 组件改动汇总

| 文件 | 改动类型 | 行数估算 | 说明 |
|------|---------|---------|------|
| `core/commands.py` | 新增方法 | ~30 | `UndoCommand.description()` + 7 个子类覆写 |
| `app/main_window.py` | 新增/修改 | ~120 | 快捷键（3 个 QShortcut + 守卫提取）、编辑菜单、工具栏按钮、状态刷新、可见性控制 |
| `ui/timeline.py` | 无修改 | 0 | 双栈和 `can_undo`/`can_redo`/`undo()`/`redo()` 完全复用 |

**总计:** 2 个文件，~150 行代码。

---

## 6. 假设与不确定项

| 项目 | 说明 |
|------|------|
| `QKeySequence.Undo` | PyQt5 在 Linux 上返回 `Ctrl+Z`，macOS 返回 `Cmd+Z`。方案依赖 Qt 的平台自动映射，不做手动判断。 |
| 菜单项快捷键显示 | `QAction.setShortcut(QKeySequence.Undo)` 在 macOS 上会正确显示 `⌘Z`。如果 Qt 的翻译不工作，备选方案是手动设置 `QAction.setText("撤销 ...\tCtrl+Z")`。 |
| `CompositeCommand` 描述推断 | 当前仅 `trim_in`/`trim_out` 使用 `CompositeCommand([SplitClipCommand, DeleteClipCommand])`。如果未来新增使用场景，需扩展描述推断逻辑。 |
| 工具栏按钮 Unicode 字符 ↩/↪ | 跨平台显示效果可能不一致。如果某些平台渲染异常，备选方案是使用 `QStyle.standardIcon` 或纯文本 "撤"/"重"。 |
| 编辑菜单位置 | PRD 定义为顶栏菜单。方案中将"编辑"菜单放在"文件"菜单之前（符合多数桌面应用的习惯）。如有要求可调整。 |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| `_is_editor_active_and_safe()` 重构可能引入 Space 快捷键回归 | `_on_space_shortcut` 逻辑 1:1 提取，应无行为差异；建议合并后执行一次 Space 按键冒烟测试 |
| `QAction.setShortcut` 与 `QShortcut` 冲突 | 已通过 ADR 决策 1 分析：`QShortcut` 优先级更高，`QAction` 的 shortcut 仅用于菜单文本显示，不会触发 |
| `description()` 返回字符串在 UI 线程中被频繁调用 | 性能忽略不计（字符串常量，非动态计算） |

---

## 8. 测试策略

### 冒烟测试（交互验证）

1. **快捷键撤销:** 拖动 clip → Ctrl+Z → clip 回到原位 → 菜单显示"撤销 移动片段"
2. **快捷键重做:** 撤销后 → Ctrl+Shift+Z → clip 回到拖动位置 → 菜单显示"重做 移动片段"
3. **Ctrl+Y 重做:** 同 Ctrl+Shift+Z，验证 Ctrl+Y 等效
4. **焦点排除:** 在项目名称输入框焦点下按 Ctrl+Z → 不触发撤销
5. **首页不可用:** 切换到首页 → 按 Ctrl+Z → 无效果 → 编辑菜单不可见
6. **栈空禁用:** 无操作时菜单/按钮灰显，无法点击
7. **重做栈清空:** 撤销 2 步 → 执行新操作 → 按 Ctrl+Y 无效果
8. **菜单按钮同步:** 按钮和菜单状态在 `clips_changed` 后同步刷新

### 单元/集成测试（可选，非必须）

- `test_undo_command_description()` — 验证各子类 `description()` 返回预期中文文本
- `test_composite_description()` — 验证 `[SplitClipCommand, DeleteClipCommand]` 返回"裁剪开头"/"裁剪结尾"
- 不要求为 QShortcut/PyQt 交互编写自动化测试（GUI 测试成本高，冒烟测试已覆盖）
