---
name: "T5: 边缘 hover 光标"
depends_on: []
labels: ["frontend"]
worktree_root: ".worktree/timeline-trim-t5/"
---

## 目标

鼠标靠近 clip 左/右边缘时，光标变为水平调整箭头（`SizeHorCursor`）。

## 实现要点

修改 `ui/timeline.py` 的 `mouseMoveEvent`，在非拖拽分支末尾新增：

```python
# 非拖拽状态 — 边缘 hover 光标
if pos.y() >= RULER_HEIGHT and self._hit_edge(pos):
    self.setCursor(Qt.SizeHorCursor)
else:
    self.setCursor(Qt.ArrowCursor)
```

复用现有 `_hit_edge()` 方法（已使用 `SnapDistance = 5` 阈值）。

## 验收标准

- [ ] 鼠标在 clip 左边缘 5px 内 → 光标变为 SizeHorCursor
- [ ] 鼠标在 clip 右边缘 5px 内 → 光标变为 SizeHorCursor
- [ ] 鼠标移离边缘 → 光标恢复 ArrowCursor
- [ ] 鼠标在 clip 中间区域 → 光标为 ArrowCursor
- [ ] 拖拽过程中不触发光标切换

## Worktree
- 路径: `.worktree/timeline-trim-t5/`
- 分支: `feat/timeline-trim-t5`
