---
id: T2
title: "TimelineWidget mouseDoubleClickEvent 扩展 + playhead_seek_play 信号"
depends_on: []
estimated_effort: "2h"
assignee_type: "backend"
issue: "https://github.com/devcxl/recordly/issues/97"
---

## 目标

在 `TimelineWidget` 中新增"双击空白区域 → 跳转 + 播放"行为，并添加 `playhead_seek_play` 信号供 `MainWindow` 消费。

## 修改范围

**文件：** `ui/timeline.py`

### 1. 新增信号（L32-40，信号声明区）

在 `TimelineWidget` 类属性区添加：

```python
playhead_seek_play = pyqtSignal(float)
```

插入位置：`clips_changed = pyqtSignal()` 之后或 `status_message = pyqtSignal(str)` 之后均可。

### 2. 扩展 `mouseDoubleClickEvent`（L350-361）

**当前代码（仅 zoom 轨道）：**

```python
def mouseDoubleClickEvent(self, event):
    pos = event.localPos()
    ti, ci = self._hit_test(pos)
    if ti < 0 and pos.y() >= RULER_HEIGHT:
        candidate = int((pos.y() - RULER_HEIGHT) // TRACK_HEIGHT)
        if 0 <= candidate < len(self._tracks):
            ti = candidate
    if ti >= 0 and self._tracks[ti].type == "zoom":
        clip = self._tracks[ti].clips[ci] if ci >= 0 else None
        self.zoom_double_clicked.emit(min(
            self._x_to_time(int(pos.x())), self._duration), clip)
    super().mouseDoubleClickEvent(event)
```

**修改后：在 `zoom_double_clicked.emit` 之后增加 `elif` 分支：**

```python
def mouseDoubleClickEvent(self, event):
    pos = event.localPos()
    ti, ci = self._hit_test(pos)
    if ti < 0 and pos.y() >= RULER_HEIGHT:
        candidate = int((pos.y() - RULER_HEIGHT) // TRACK_HEIGHT)
        if 0 <= candidate < len(self._tracks):
            ti = candidate
    
    # --- Zoom 轨道双击（现有行为，保持不变）---
    if ti >= 0 and self._tracks[ti].type == "zoom":
        clip = self._tracks[ti].clips[ci] if ci >= 0 else None
        self.zoom_double_clicked.emit(
            min(self._x_to_time(int(pos.x())), self._duration), clip)
    # --- 空白区域双击（新增行为）---
    elif ci < 0 and pos.y() >= RULER_HEIGHT:
        self._playhead_s = min(self._x_to_time(int(pos.x())), self._duration)
        self.update()
        self.playhead_changed.emit(self._playhead_s)
        self.playhead_seek_play.emit(self._playhead_s)
    
    super().mouseDoubleClickEvent(event)
```

### 3. 新增测试

**文件：** `tests/test_timeline.py`

| 测试用例 | 验证点 |
|----------|--------|
| `test_double_click_blank_area_emits_playhead_seek_play` | 空白区域双击 → `playhead_seek_play` 信号发射，`playhead_changed` 也发射 |
| `test_double_click_blank_area_does_not_emit_on_clip` | 在 clip 上方双击 → `playhead_seek_play` 不发射 |
| `test_double_click_blank_area_does_not_emit_on_ruler` | 在标尺上双击 → `playhead_seek_play` 不发射 |
| `test_double_click_blank_area_in_zoom_track_does_not_emit` | 在 zoom 轨道空白处双击 → zoom 逻辑优先，`playhead_seek_play` 不发射 |
| `test_playhead_seek_play_signal_carries_correct_time` | 确认信号携带的时间值与 `_playhead_s` 一致 |

## 触发条件判断逻辑

```
✨ 空白区域双击触发条件（elif 分支）：
  - ci < 0                          — 位置不在任何 clip 上方
  - pos.y() >= RULER_HEIGHT         — 位置在轨道区域（非标尺）
  - 已在 elif 分支                  — zoom 轨道判断已在 if 中筛选掉
```

## PyQt5 事件顺序说明

PyQt5 双击时先触发 `mousePressEvent` → 再触发 `mouseDoubleClickEvent`。空白区域双击时：
1. `mousePressEvent`（T1 重构后）→ 移动播放头到点击位置
2. `mouseDoubleClickEvent` → 再次设置 `_playhead_s`（同一位置）→ emit `playhead_changed` + `playhead_seek_play`
两次播放头更新位置相同，无副作用。

## 参考

- 技术方案：`docs/dev/specs/recordly-playhead-click-behavior.md` §3.1、§3.3
- ADR：`docs/adr/2026-07-19-playhead-click-behavior.md` 决策 2、决策 4
