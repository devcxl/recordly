---
name: "T4: Timeline 视频片段吸附与对齐线"
depends_on: ["T3: Timeline X 播放头切割"]
labels: ["enhancement", "ready-for-agent"]
worktree_root: ".worktree/timeline-video-snapping/"
issue: 83
---

## 目标

拖动同一视频轨道内的 Clip 时，以 8px Qt 逻辑像素阈值吸附相邻边缘并绘制瞬态对齐线，最终继续由 `MoveClipCommand` 记录位置。

## TDD 红绿步骤

### Red

在 `tests/test_timeline.py` 先增加失败测试：

1. 左边缘对目标右边缘、右边缘对目标左边缘，恰好 8px 吸附，超过 8px 不吸附。
2. 多候选取浮点像素距离最近者；等距保持 `Track.clips` 遍历顺序。
3. 不同视频轨、audio/zoom 轨、resize 状态不吸附。
4. `_snap_alignment_time` 在命中时设置，在离开阈值、鼠标释放、拖动取消、`set_tracks()` 后清空。
5. 释放只增加一个 move undo 项；undo/redo 恢复位置，`source_start/source_end/speed/content` 不变。

### Green

- 增加独立的 8px Clip 吸附常量，不复用现有边缘 resize 命中常量。
- 先按现有规则计算并 clamp 候选 start/end，再用 `abs(candidate_time - target_time) * _pixels_per_sec` 比较。
- 仅在 move 且当前 Track/Clip 都为 video 时，比较当前左↔其他右、当前右↔其他左。
- 保存目标时间到 `_snap_alignment_time`；`paintEvent()` 每次转换 x 后绘制轨道区域垂直虚线。
- 普通 move 开始时补齐 source 原值捕获，防止 `_make_move_cmd()` 使用上次拖拽缓存。

## 精确实现范围

- 修改：`ui/timeline.py`
- 修改：`tests/test_timeline.py`
- 不修改：`core/commands.py`、`app/main_window.py`
- 不实现跨轨、播放头、刻度、边界或 resize 吸附。
- 对齐线不进入 Clip、Project 或 undo/redo 数据。

## 验收标准

- [ ] 8px 阈值使用逻辑像素和浮点时间差，行为不受整数 x 取整影响。
- [ ] 同轨双向边缘吸附和稳定候选选择正确。
- [ ] 非目标轨道/状态不吸附。
- [ ] 对齐线显示和清理生命周期完整。
- [ ] Clip 时长及 start/end 之外字段保持不变。
- [ ] move 只产生一个可正确撤销/重做的命令。

## 验证命令

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py -k "snap or alignment or drag"
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py
git diff --check
```

## Worktree

- 路径：`.worktree/timeline-video-snapping/`
- 分支：`feat/timeline-video-snapping`
- 基线：#82 实现 PR 合入后的 `master`

## 对应 PR

PR body 必须包含：

```text
Closes #83
```
