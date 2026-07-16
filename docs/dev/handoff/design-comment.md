# 设计评论摘要 — 时间线裁剪功能完善

**日期:** 2026-07-17
**关联:** PRD `docs/prd/recordly-timeline-trim.md` / Spec `docs/dev/specs/recordly-timeline-trim.md` / ADR `docs/adr/2026-07-17-timeline-trim-source-sync.md`

---

## 核心设计决策

### F1 — resize source 同步公式

```
new_source = old_source + (new_timeline - old_timeline) × speed
```

**与 SplitClipCommand:100 一致。** 这确保 timeline 位置与 source 位置的映射关系在 resize 前后保持不变。

实现方式：基于 `_drag_orig_source_start` 的**绝对计算**（非每帧增量），避免浮点误差累积。source 字段通过扩展 `MoveClipCommand` 纳入 undo/redo 体系。

> 备选方案"不更新 source（当前行为）"被拒绝——这正是 bug 根因。
> 备选方案"反向换算 source -= dt / speed"被拒绝——与 SplitClipCommand 公式不一致，语义错误。

### F3 — CompositeCommand 组合 Split + Delete

**创建通用 `CompositeCommand` 宏命令**，将 `SplitClipCommand` + `DeleteClipCommand` 包装为单个可撤销单元。

`trim_in`(I 键)：拆分 → 删除左半边
`trim_out`(O 键)：拆分 → 删除右半边

> 备选方案"新建 TrimClipCommand"被拒绝——重复实现 SplitClipCommand 的 source 计算逻辑，增加维护面。

### 改动范围

仅两个文件：
- `core/commands.py`: MoveClipCommand +4 字段，+CompositeCommand
- `ui/timeline.py`: 边缘 drag source 同步，hover 光标，trim_in/out + I/O 键绑定

### 未解决的潜在问题

`exporter.py:616` 在 source_end=None 时计算 `source_start + (end - start)` **未乘 speed**，而 `sync_audio_regions_from_clips`（project.py:152）则乘了。这不影响 F1（F1 仅涉及显式 source_end 的 clip），但非拆分 clip 变速导出时可能有音频长度错位。需独立排查，但不在本次 PRD 范围。

---

## 给 @backend 的实现指南

1. **先改 commands.py**：`MoveClipCommand` 加 source 字段（含 execute/undo 中的 restore 逻辑）+ `CompositeCommand`
2. **再改 timeline.py**：
   - `__init__` 加 `_drag_orig_source_start/end`
   - `mousePressEvent` 边缘拖拽时捕获 source 原值
   - `mouseMoveEvent` resize_left/right 分支用 `_drag_orig_*` + 累积 dt 计算 source
   - `mouseMoveEvent` 末尾加 hover 光标切换（`_hit_edge` + `setCursor`）
   - `_make_move_cmd` 传 source 字段
   - 加 `trim_in()`/`trim_out()` 方法
   - `keyPressEvent` 加 `Qt.Key_I` / `Qt.Key_O` 分支

每个文件独立可测。建议改完 commands.py 先跑现有测试，再改 timeline.py。
