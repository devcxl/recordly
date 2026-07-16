---
name: "T3: _make_move_cmd 捕获 source 变更"
depends_on: ["T1: MoveClipCommand 扩展 source 字段"]
labels: ["frontend"]
worktree_root: ".worktree/timeline-trim-t3/"
---

## 目标

扩展 `_make_move_cmd()` 方法，在创建 `MoveClipCommand` 时传入当前的 `source_start`/`source_end` 值。

## 实现要点

修改 `ui/timeline.py` 的 `_make_move_cmd()`（L289-298）：

```python
def _make_move_cmd(self) -> MoveClipCommand | None:
    if self._drag_state in ("move", "resize_left", "resize_right"):
        clip = self._tracks[self._drag_track].clips[self._drag_clip]
        if abs(clip.start - self._drag_orig_start) > 0.01 or abs(clip.end - self._drag_orig_end) > 0.01:
            return MoveClipCommand(
                track_index=self._drag_track, clip_index=self._drag_clip,
                old_start=self._drag_orig_start, new_start=clip.start,
                old_end=self._drag_orig_end, new_end=clip.end,
                old_source_start=self._drag_orig_source_start,
                new_source_start=clip.source_start,
                old_source_end=self._drag_orig_source_end,
                new_source_end=clip.source_end,
            )
    return None
```

## 验收标准

- [ ] 创建的 MoveClipCommand 包含 source 字段
- [ ] `_push_undo` 后 undo/redo 正确恢复 source_start 和 source_end

## Worktree
- 路径: `.worktree/timeline-trim-t3/`
- 分支: `feat/timeline-trim-t3`
