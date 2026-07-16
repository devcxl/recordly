---
name: "T2: mouseMoveEvent 更新 source"
depends_on: ["T1: MoveClipCommand 扩展 source 字段"]
labels: ["frontend"]
worktree_root: ".worktree/timeline-trim-t2/"
---

## 目标

在 `ui/timeline.py` 的 `mouseMoveEvent` 中，让 `resize_left`/`resize_right` 拖拽时同步更新 `source_start`/`source_end`。

## 实现要点

修改 `mouseMoveEvent` 中的 resize 分支（L242-250）：

1. `resize_left`：
   ```python
   new_start = max(0.0, min(self._drag_orig_start + dt, clip.end - 0.5))
   d_start = new_start - self._drag_orig_start
   clip.start = new_start
   clip.source_start = self._drag_orig_source_start + d_start * clip.speed
   ```

2. `resize_right`：
   ```python
   new_end = min(self._duration, max(clip.start + 0.5, self._drag_orig_end + dt))
   d_end = new_end - self._drag_orig_end
   clip.end = new_end
   if clip.source_end is not None:
       clip.source_end = self._drag_orig_source_end + d_end * clip.speed
   ```

## 验收标准

- [ ] resize_left 时 `source_start` 按 `d_start * speed` 偏移
- [ ] resize_right 时 `source_end`（非 None）按 `d_end * speed` 偏移
- [ ] resize_right 时 `source_end` 为 None 时不修改
- [ ] 使用 `_drag_orig_source_start`/`_drag_orig_source_end`（已在 T4 中设置）避免浮点累积

## Worktree
- 路径: `.worktree/timeline-trim-t2/`
- 分支: `feat/timeline-trim-t2`
