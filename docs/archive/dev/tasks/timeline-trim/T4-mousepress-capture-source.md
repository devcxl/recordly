---
name: "T4: mousePressEvent 捕获 drag_orig_source"
depends_on: ["T2: mouseMoveEvent 更新 source"]
labels: ["frontend"]
worktree_root: ".worktree/timeline-trim-t4/"
---

## 目标

在 `mousePressEvent` 的边缘拖拽捕获处记录 source 字段的初始值，供 T2/T3 使用。

## 实现要点

1. `__init__` 中新增成员变量：
   ```python
   self._drag_orig_source_start = 0.0
   self._drag_orig_source_end = None
   ```

2. `mousePressEvent` 中 `_hit_edge()` 返回后（L191-197）新增：
   ```python
   self._drag_orig_source_start = clip.source_start
   self._drag_orig_source_end = clip.source_end
   ```

## 验收标准

- [ ] `_drag_orig_source_start` / `_drag_orig_source_end` 在边缘拖拽开始时正确初始化
- [ ] move 拖拽（非 resize）场景下不影响现有行为
- [ ] 变量在 `__init__` 中初始化，避免 AttributeError

## Worktree
- 路径: `.worktree/timeline-trim-t4/`
- 分支: `feat/timeline-trim-t4`
