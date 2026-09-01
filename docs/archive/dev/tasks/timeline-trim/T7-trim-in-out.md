---
name: "T7: trim_in/trim_out + keyPressEvent 绑定"
depends_on: ["T6: CompositeCommand 宏命令"]
labels: ["frontend"]
worktree_root: ".worktree/timeline-trim-t7/"
---

## 目标

实现 `trim_in()` / `trim_out()` 方法，绑定 I/O 键，实现播放头一键裁剪。

## 实现要点

1. `ui/timeline.py` 新增 `trim_in()`：
   - 无选中 clip → 返回
   - playhead ≤ clip.start → 返回
   - playhead ≥ clip.end → 删除整个 clip
   - playhead 在中间 → `CompositeCommand([SplitClipCommand, DeleteClipCommand(左)])`

2. `ui/timeline.py` 新增 `trim_out()`：
   - 同上，但删除的是右半边

3. `keyPressEvent` 中绑定：
   ```python
   if event.key() == Qt.Key_I:
       self.trim_in()
       return
   if event.key() == Qt.Key_O:
       self.trim_out()
       return
   ```

## 验收标准

- [ ] I 键裁掉 playhead 之前的内容（选中 clip 内）
- [ ] O 键裁掉 playhead 之后的内容（选中 clip 内）
- [ ] 一次 Ctrl+Z 恢复整个裁剪操作（非两步撤销）
- [ ] playhead 在 clip 开头按 I 无操作
- [ ] playhead 在 clip 结尾按 O 无操作
- [ ] 无选中 clip 时按 I/O 无操作

## Worktree
- 路径: `.worktree/timeline-trim-t7/`
- 分支: `feat/timeline-trim-t7`
