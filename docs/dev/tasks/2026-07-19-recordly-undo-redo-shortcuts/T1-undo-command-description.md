---
id: T1
title: "UndoCommand.description() 基类方法 + 7 个子类覆写"
depends_on: []
estimated_effort: "2h"
assignee_type: "core"
---

## 目标

在 `core/commands.py` 中为 `UndoCommand` 基类新增 `description()` 方法，各子类覆写返回中文操作名称，供 UI 层的菜单和 ToolTip 使用。

## 实现要点

### 1. 基类 `UndoCommand.description()`

在 `UndoCommand` 抽象基类中新增：

```python
def description(self) -> str:
    """返回面向用户的中文操作描述，菜单和 ToolTip 使用。"""
    return self.__class__.__name__
```

- 默认回退到类名，保证所有子类无覆写时不崩溃
- 纯字符串返回，无 Qt 依赖，保持 `core/commands.py` 数据层定位

### 2. 子类覆写

| 命令 | `description()` 返回值 |
|------|----------------------|
| `AddClipCommand` | `"添加片段"` |
| `MoveClipCommand` | `"移动片段"` |
| `DeleteClipCommand` | `"删除片段"` |
| `SplitClipCommand` | `"切割片段"` |
| `ChangeSpeedCommand` | `"变更速度"` |
| `CompositeCommand` | 见下方推断规则 |

### 3. `CompositeCommand.description()` 推断规则

`CompositeCommand` 的描述需要根据 `sub_commands` 列表推断：

- 若 `len(sub_commands) == 2` 且分别为 `SplitClipCommand` + `DeleteClipCommand`：
  - 读取 `DeleteClipCommand.clip_index` 判断删除的是左半边还是右半边
  - 若删除的是左半边的 split 产物（clip_index 不变） → `"裁剪开头"`
  - 若删除的是右半边（clip_index + 1） → `"裁剪结尾"`
- 否则 → `f"批量操作({len(sub_commands)}步)"`
- 不遍历子命令 `description()`，避免递归和歧义

### 4. `MoveClipCommand.__repr__` 保持不变

`MoveClipCommand` 已有自定义 `__repr__()`，与 `description()` 职责不同（repr 面向开发者，description 面向用户）。两个方法不冲突。

## 改动范围

- 文件：`core/commands.py`
- 行数：~35 行（基类 2 行 + 6 个子类各 ~1 行 + CompositeCommand ~25 行）
- 纯增量，不影响现有 `execute()`/`undo()` 逻辑

## 验收标准

- [ ] 所有 7 个命令子类均可调用 `description()` 并返回非空字符串
- [ ] `AddClipCommand().description()` → `"添加片段"`
- [ ] `MoveClipCommand().description()` → `"移动片段"`
- [ ] `DeleteClipCommand().description()` → `"删除片段"`
- [ ] `SplitClipCommand().description()` → `"切割片段"`
- [ ] `ChangeSpeedCommand().description()` → `"变更速度"`
- [ ] `CompositeCommand(sub_commands=[SplitClipCommand(...), DeleteClipCommand(clip_index=0)]).description()` → `"裁剪开头"`
- [ ] `CompositeCommand(sub_commands=[SplitClipCommand(...), DeleteClipCommand(clip_index=1)]).description()` → `"裁剪结尾"`
- [ ] `CompositeCommand(sub_commands=[AddClipCommand(...), DeleteClipCommand(...)]).description()` → `"批量操作(2步)"`
- [ ] 现有 `test_timeline.py` 和 `test_main_window.py` 全绿

## 风险

- `CompositeCommand` 推断规则依赖 `[SplitClipCommand, DeleteClipCommand]` 的固定顺序。当前 `timeline.py:trim_in()` / `trim_out()` 满足此约定。若未来新增 `CompositeCommand` 用例，需扩展推断逻辑。

Parent: #93
