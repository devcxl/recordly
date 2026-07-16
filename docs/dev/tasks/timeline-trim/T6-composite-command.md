---
name: "T6: CompositeCommand 宏命令"
depends_on: []
labels: ["backend"]
worktree_root: ".worktree/timeline-trim-t6/"
---

## 目标

在 `core/commands.py` 中新增 `CompositeCommand`，将多个子命令包装为单个 undo/redo 单元。

## 实现要点

```python
@dataclass
class CompositeCommand(UndoCommand):
    """将多个子命令组合为单个可撤销/重做单元。
    execute: 顺序执行子命令
    undo:    逆序撤销子命令
    """
    sub_commands: list  # list[UndoCommand]

    def execute(self, timeline):
        for cmd in self.sub_commands:
            cmd.execute(timeline)

    def undo(self, timeline):
        for cmd in reversed(self.sub_commands):
            cmd.undo(timeline)

    def __repr__(self):
        inner = ', '.join(repr(c) for c in self.sub_commands)
        return f"Composite({inner})"
```

## 验收标准

- [ ] CompositeCommand 继承 UndoCommand
- [ ] execute 顺序执行子命令
- [ ] undo 逆序撤销子命令
- [ ] 单元测试：test_commands.py 验证 SplitClip + DeleteClip 组合的 execute/undo 正确性

## Worktree
- 路径: `.worktree/timeline-trim-t6/`
- 分支: `feat/timeline-trim-t6`
