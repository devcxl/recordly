# PRD: 撤销/重做快捷键与入口

**日期:** 2026-07-19
**状态:** Draft

## 1. 概述

### 1.1 问题陈述

Recordly 的撤销/重做命令体系（`core/commands.py`：`UndoCommand` 抽象基类 + 7 种具体命令）和双栈机制（`ui/timeline.py`：`_undo_stack`/`_redo_stack`）已完整实现，`main_window.py` 中 `_on_undo()`/`_on_redo()` 方法也已就绪，但 **无任何触发入口**：

- 无 Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y 快捷键绑定
- 菜单栏无"编辑"菜单，无撤销/重做项
- 工具栏无撤销/重做按钮

用户无法执行最基础的剪辑回退操作，严重降低编辑效率。

### 1.2 目标用户

所有使用 Recordly 编辑项目的用户。

### 1.3 成功指标

- 按 Ctrl+Z 后上一步剪辑操作被撤销
- 按 Ctrl+Shift+Z 或 Ctrl+Y 后撤销的操作被重做
- 菜单栏显示"编辑 → 撤销（操作名称）"/"重做（操作名称）"
- 工具栏撤销/重做按钮在可操作时启用，不可操作时灰显

## 2. 功能需求

### 2.1 F1：Ctrl+Z 撤销快捷键

- **快捷键**：`Ctrl+Z`（Windows/Linux），macOS 自动映射为 `Cmd+Z`
- **范围**：编辑器界面（`_editor_interface`），排除输入框/弹窗获得焦点时
- **行为**：调用 `_timeline.undo()`，执行栈顶命令的 `undo()` 方法
- **焦点排除**：`QLineEdit`、`QTextEdit`、`QPlainTextEdit`、`QAbstractSpinBox`、`QComboBox`

### 2.2 F2：Ctrl+Shift+Z / Ctrl+Y 重做快捷键

- **快捷键**：`Ctrl+Shift+Z` 和 `Ctrl+Y` 均可触发重做
- **范围与焦点排除**：同 F1
- **行为**：调用 `_timeline.redo()`，执行重做栈顶命令的 `execute()` 方法

### 2.3 F3：编辑菜单（Undo/Redo 菜单项）

- **菜单结构**：
  ```
  编辑
    ├── 撤销 <操作名称>    Ctrl+Z
    └── 重做 <操作名称>    Ctrl+Shift+Z
  ```
- **操作名称**：来自 `UndoCommand.__repr__()`，当前返回类名（如 `MoveClipCommand`），需改为中文可读描述
- **动态禁用**：`_undo_stack` 为空时撤销项灰显，`_redo_stack` 为空时重做项灰显
- **菜单更新时机**：`clips_changed` 信号触发时刷新菜单项状态

### 2.4 F4：工具栏撤销/重做按钮

- **位置**：工具栏左侧，独立一组，与播放控制按钮分隔
- **图标**：↩（撤销）、↪（重做）
- **ToolTip**：显示快捷键和当前操作名称
- **状态**：通过 `clips_changed` 信号同步按钮启用/禁用

### 2.5 F5：操作名称中文化

- `UndoCommand` 新增 `description()` 方法，默认返回类名
- 各子类覆写返回中文描述：
  | 命令 | 描述 |
  |------|------|
  | `AddClipCommand` | 添加片段 |
  | `MoveClipCommand` | 移动片段 |
  | `DeleteClipCommand` | 删除片段 |
  | `SplitClipCommand` | 切割片段 |
  | `ChangeSpeedCommand` | 变更速度 |
  | `CompositeCommand` | 批量操作（如"裁剪开头"/"裁剪结尾"） |
- `CompositeCommand` 内部存储子命令列表，`description()` 根据子命令组合返回语义化名称

## 3. 用户故事

### US-1: 快捷键撤销/重做
**作为** 视频编辑用户
**我想要** 使用 Ctrl+Z 撤销上一步剪辑操作，Ctrl+Shift+Z 重做
**以便** 双手不离开键盘即可快速回退

**验收标准：**
- [ ] 在编辑器内按 Ctrl+Z，上一步操作被撤销
- [ ] 按 Ctrl+Shift+Z 或 Ctrl+Y，被撤销的操作被重做
- [ ] 快捷键在输入框/弹窗获得焦点时不触发
- [ ] 切换到首页或其他非编辑界面时快捷键不触发
- [ ] 撤销后执行新操作，重做栈被清空

### US-2: 菜单和工具栏入口
**作为** 视频编辑用户
**我想要** 在菜单栏和工具栏看到撤销/重做入口
**以便** 知道这些功能可用，必要时用鼠标操作

**验收标准：**
- [ ] 菜单栏有"编辑"菜单，含撤销/重做项，显示操作名称
- [ ] 撤销/重做菜单项在不可用时灰显
- [ ] 工具栏有撤销/重做按钮，状态与菜单同步
- [ ] 按钮 ToolTip 显示快捷键和当前操作名称

## 4. Out of Scope

| 排除项 | 原因 |
|--------|------|
| 历史面板（操作列表） | 标准快捷键+入口已满足核心需求 |
| 撤销深度配置 | 当前不限步数已足够 |
| 跨项目撤销 | 项目切换时清空历史是合理行为 |
| 操作日志导出 | 非剪辑核心需求 |
| macOS Cmd 键显式适配 | PyQt5 QKeySequence 自动处理 Cmd/Ctrl 映射 |

## 5. 技术约束

- 语言：Python 3.11+
- UI 框架：PyQt5
- `UndoCommand` 新增 `description()` 方法，保持向后兼容
- 复用现有 `_on_undo()`/`_on_redo()` 方法，仅新增触发绑定
- 快捷键使用 `QShortcut` + `Qt.WindowShortcut`，与 Space 键保持一致模式
- 焦点排除逻辑复用 `_on_space_shortcut()` 中的 `activeModalWidget`/`activePopupWidget`/`focusWidget` 检查
- `clips_changed` 信号用于驱动菜单/工具栏状态更新
