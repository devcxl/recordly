---
name: "T1: MoveClipCommand 扩展 source 字段"
depends_on: []
labels: ["backend"]
worktree_root: ".worktree/timeline-trim-t1/"
---

## 目标

扩展 `core/commands.py` 中 `MoveClipCommand`，新增 4 个 source 相关字段，使命令能记录和恢复 `source_start`/`source_end`。

## 实现要点

在 `core/commands.py` 的 `MoveClipCommand` dataclass 中：

1. 新增字段（带默认值，向后兼容）：
   - `old_source_start: float = 0.0`
   - `new_source_start: float = 0.0`
   - `old_source_end: float | None = None`
   - `new_source_end: float | None = None`

2. 在 `execute()` 中，设置完 start/end 后恢复 source 字段：
   ```python
   clip.source_start = self.new_source_start
   clip.source_end = self.new_source_end
   ```

3. 在 `undo()` 中，恢复完 start/end 后恢复 source 字段：
   ```python
   clip.source_start = self.old_source_start
   clip.source_end = self.old_source_end
   ```

## 验收标准

- [ ] MoveClipCommand 有 4 个新字段，有默认值
- [ ] execute 恢复 new_source_start/new_source_end
- [ ] undo 恢复 old_source_start/old_source_end
- [ ] 现有 `MoveClipCommand(...)` 调用位置无语法错误（新字段有默认值）
- [ ] 单元测试：test_commands.py 验证 source 字段的 execute/undo 行为

## Worktree
- 路径: `.worktree/timeline-trim-t1/`
- 分支: `feat/timeline-trim-t1`
