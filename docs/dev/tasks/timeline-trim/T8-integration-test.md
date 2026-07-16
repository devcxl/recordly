---
name: "T8: 集成测试 + 手动验证"
depends_on: ["T4: mousePressEvent 捕获 drag_orig_source", "T5: 边缘 hover 光标", "T7: trim_in/trim_out + keyPressEvent"]
labels: ["backend", "frontend"]
worktree_root: ".worktree/timeline-trim-t8/"
---

## 目标

编写 F1/F2/F3 的完整集成测试，确保所有场景覆盖。

## 实现要点

### F1 测试（test_commands.py / test_timeline.py）
- [ ] 未拆分 clip resize_left → source_start 随 start 增加
- [ ] 未拆分 clip resize_right → source_end 保持 None
- [ ] 拆分后 clip resize_left → source_start 增加，undo 恢复
- [ ] 拆分后 clip resize_right → source_end 减少，undo 恢复
- [ ] speed=2.0 时 resize_left → source_start 偏移 = 时间线偏移 × 2

### F2 测试（test_preview_widget.py 或 manual）
- [ ] 光标 hover 检测逻辑（manual 或 QTest 模拟）

### F3 测试（test_timeline.py）
- [ ] trim_in 拆分+删除左半边，一次 undo 恢复
- [ ] trim_out 拆分+删除右半边，一次 undo 恢复
- [ ] playhead 在边界时无操作/删除整个 clip
- [ ] 无选中时无操作

## 验收标准

- [ ] 所有测试通过
- [ ] 手动验证：打开项目 → 拖拽边缘 → 保存 → 重新加载 → 导出音频与视频长度一致

## Worktree
- 路径: `.worktree/timeline-trim-t8/`
- 分支: `feat/timeline-trim-t8`
