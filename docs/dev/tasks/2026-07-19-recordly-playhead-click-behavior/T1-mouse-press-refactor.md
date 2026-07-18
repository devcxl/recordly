---
id: T1
title: "TimelineWidget mousePressEvent 重构 — 先判断点击目标后移动播放头"
depends_on: []
estimated_effort: "3h"
assignee_type: "backend"
issue: "https://github.com/devcxl/recordly/issues/95"
---

## 目标

修正 `TimelineWidget.mousePressEvent` 的执行顺序：**先判断点击目标（clip、边缘、空白），再决定是否移动播放头**，消除"点击 clip 时播放头误跳转"的 bug。

## 当前问题

```python
# L208-211 — 无条件先移动播放头
self._playhead_s = min(self._x_to_time(int(pos.x())), self._duration)
self._drag_state = "playhead"
self.update()
self.playhead_changed.emit(self._playhead_s)

# L213-245 — 然后才判断 hit_test / hit_edge
```

结果：点击 clip 选中 → 播放头跳转到点击位置（不符合预期）。

## 修改范围

**文件：** `ui/timeline.py`

### 1. 重构 `mousePressEvent`（L202-245）

重写为四个顺序分支：

```
1. pos.y() < RULER_HEIGHT → 标尺区域，移动播放头，return
2. _hit_edge → 命中边缘，进入 resize 拖拽，return（不移动播放头）
3. _hit_test → 命中 clip，选中 + 进入 move 拖拽，return（不移动播放头）
4. 空白区域 → 移动播放头 + 清除选中
```

**不修改的逻辑：**
- `_hit_edge` 返回值结构不变（`(track, clip, "resize_left" | "resize_right")`）
- `_hit_test` 返回值结构不变（`(track, clip)` 或 `(-1, -1)`）
- `_drag_orig_*` 赋值逻辑不变
- `zoom_clip_selected.emit(clip)` 保留
- `_snap_alignment_time = None` 初始化保留

### 2. 更新/新增测试

**文件：** `tests/test_timeline.py`

需要增加以下测试用例（或适配现有用例）：

| 测试用例 | 验证点 |
|----------|--------|
| `test_click_on_clip_does_not_move_playhead` | 单击 clip 后 `_playhead_s` 不变，`playhead_changed` 不发射 |
| `test_click_on_clip_edge_does_not_move_playhead` | 单击 clip 边缘后进入 resize，`_playhead_s` 不变 |
| `test_click_on_blank_area_moves_playhead` | 单击空白区域后 `_playhead_s` 更新到点击位置 |
| `test_click_on_ruler_moves_playhead` | 单击标尺后 `_playhead_s` 更新，`playhead_changed` 发射 |
| `test_click_on_clip_clears_selection_on_blank` | 先选中 clip → 点空白 → 选中清除 |
| **(适配)** `test_single_click_zoom_clip_emits_selected_clip` | 验证 `zoom_clip_selected` 仍发射，同时确认播放头位置不变 |

## 边界条件

| 场景 | 预期 |
|------|------|
| 标尺上任何时候点击 | 移动播放头 |
| 点击 clip 边缘（resize 区） | resize 模式，不移播放头 |
| 点击 clip 内部 | 选中 clip + move 模式，不移播放头 |
| 点击 zoom clip | 选中 + emit `zoom_clip_selected`，不移播放头 |
| 点击空白轨道区域 | 移动播放头 + 清除选中 |

## 与 T2 的协调

- T1 和 T2 修改同一文件 `timeline.py` 但**不同方法**，可并行开发
- 若 T1 和 T2 同时合并，注意 `mouseDoubleClickEvent` 中的 `elif` 分支新增 `playhead_seek_play.emit()` — 该信号在 T2 中声明，T1 不涉及
- 建议先合 T1，再合 T2

## 参考

- 技术方案：`docs/dev/specs/recordly-playhead-click-behavior.md` §3.2
- ADR：`docs/adr/2026-07-19-playhead-click-behavior.md` 决策 1
