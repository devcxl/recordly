# 技术方案：播放头点击行为修正

**日期:** 2026-07-19
**关联:** Issue #94
**PRD:** `docs/prd/recordly-playhead-click-behavior.md`

---

## 1. 概述

修正 `TimelineWidget.mousePressEvent` 的执行顺序（先判断点击目标，再决定是否移动播放头），并在 `mouseDoubleClickEvent` 中新增空白区域双击 → "跳转 + 播放" 行为。

## 2. 变更范围

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `ui/timeline.py` | 修改 | 重构 `mousePressEvent`（L202-245）、扩展 `mouseDoubleClickEvent`（L350-361）、新增信号 |
| `app/main_window.py` | 修改 | 新增 `_on_playhead_seek_play` 槽函数、连接新信号 |

## 3. 详细设计

### 3.1 新增信号

在 `TimelineWidget` 类属性区新增：

```python
playhead_seek_play = pyqtSignal(float)
```

信号携带双击位置的时间（秒），由 `MainWindow` 消费。

### 3.2 `mousePressEvent` 重构

**当前执行顺序（有 Bug）：**

```
1. 无条件更新播放头 → 2. 判断 _hit_edge → 3. 判断 _hit_test
   ↑ 问题：步骤 1 已移动播放头并发射 playhead_changed
```

**修正后执行顺序：**

```
1. 标尺区域 (pos.y() < RULER_HEIGHT) → 移动播放头，return
2. _hit_edge 检测 → 命中则进入 resize 拖拽，不移播放头，return
3. _hit_test 检测 → 命中则选中 clip + 进入 move 拖拽，不移播放头，return
4. 空白区域 → 移动播放头 + 清除选中，return
```

**伪代码：**

```python
def mousePressEvent(self, event):
    if event.button() != Qt.LeftButton:
        return
    self._snap_alignment_time = None
    pos = event.localPos()

    # --- 标尺区域：始终移动播放头 ---
    if pos.y() < RULER_HEIGHT:
        self._playhead_s = min(self._x_to_time(int(pos.x())), self._duration)
        self._drag_state = "playhead"
        self.update()
        self.playhead_changed.emit(self._playhead_s)
        return

    # --- 轨道区域：先判断点击目标 ---

    # 1. 边缘拖拽（resize）
    edge = self._hit_edge(pos)
    if edge:
        self._drag_track, self._drag_clip, self._drag_state = edge
        self._drag_start_x = pos.x()
        clip = self._tracks[self._drag_track].clips[self._drag_clip]
        self._drag_orig_start = clip.start
        self._drag_orig_end = clip.end
        self._drag_orig_source_start = clip.source_start
        self._drag_orig_source_end = clip.source_end
        self.update()
        return  # ← 不移动播放头

    # 2. 片段内部（选中 + move）
    ti, ci = self._hit_test(pos)
    if ti >= 0 and ci >= 0:
        self._selected_track = ti
        self._selected_clip = ci
        self._drag_track = ti
        self._drag_clip = ci
        self._drag_state = "move"
        self._drag_start_x = pos.x()
        clip = self._tracks[ti].clips[ci]
        self._drag_orig_start = clip.start
        self._drag_orig_end = clip.end
        self._drag_orig_source_start = clip.source_start
        self._drag_orig_source_end = clip.source_end
        if self._tracks[ti].type == "zoom":
            self.zoom_clip_selected.emit(clip)
        self.update()
        return  # ← 不移动播放头

    # 3. 空白区域 → 移动播放头
    self._selected_track = -1
    self._selected_clip = -1
    self._playhead_s = min(self._x_to_time(int(pos.x())), self._duration)
    self._drag_state = "playhead"
    self.update()
    self.playhead_changed.emit(self._playhead_s)
```

**与原始代码的关键差异：**

| 原始代码 | 修正后 |
|----------|--------|
| 先移动播放头，后判断点击目标 | 先判断点击目标，命中 clip 则跳过播放头更新 |
| 标尺区域无特殊处理（统一移播放头） | 标尺区域提前 return，不受 clip 判断影响 |
| `_hit_edge` 命中后仍已移动播放头 | `_hit_edge` 命中后不移动播放头 |
| `_hit_test` 命中后仍已移动播放头 | `_hit_test` 命中后不移动播放头 |

**不破坏的现有行为：**

- clip 拖拽（move）：`_drag_state = "move"` + `_drag_orig_*` 赋值逻辑不变
- clip 缩放（resize）：`_hit_edge` 返回 `"resize_left"/"resize_right"` 逻辑不变
- 撤销/重做：`mouseReleaseEvent` 中 `_make_move_cmd()` 逻辑不变
- zoom clip 选中信号：`zoom_clip_selected.emit(clip)` 在命中 zoom clip 时仍会发射
- 标尺点击：`pos.y() < RULER_HEIGHT` 时始终移动播放头，与预期一致

### 3.3 `mouseDoubleClickEvent` 扩展

**当前行为（仅 zoom 轨道）：**

```python
def mouseDoubleClickEvent(self, event):
    pos = event.localPos()
    ti, ci = self._hit_test(pos)
    if ti < 0 and pos.y() >= RULER_HEIGHT:
        candidate = int((pos.y() - RULER_HEIGHT) // TRACK_HEIGHT)
        if 0 <= candidate < len(self._tracks):
            ti = candidate
    if ti >= 0 and self._tracks[ti].type == "zoom":
        # zoom 轨道双击逻辑
        ...
    super().mouseDoubleClickEvent(event)
```

**扩展后：**

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

**触发条件判断逻辑：**

- `ti >= 0 and self._tracks[ti].type == "zoom"` → zoom 轨道双击（现有行为，优先级最高）
- `ci < 0 and pos.y() >= RULER_HEIGHT` → 空白区域双击（新增行为）
  - `ci < 0` 确保位置不在任何 clip 上方
  - `pos.y() >= RULER_HEIGHT` 确保位置在轨道区域（非标尺）
  - 已经在 `elif` 分支，确保不与 zoom 轨道冲突
- 其他情况（如点在 clip 上方、点在标尺上）→ 不做额外处理

**注意：** PyQt5 的鼠标事件机制决定 `mousePressEvent` 会在 `mouseDoubleClickEvent` 之前触发。空白区域双击的 `mousePressEvent` 将按 3.2 的逻辑移动播放头，然后 `mouseDoubleClickEvent` 再次更新播放头并发射 `playhead_seek_play`。两次播放头更新位置相同，不产生副作用。

### 3.4 `MainWindow` 集成

#### 3.4.1 信号连接

在 `_connect_timeline_signals()` 中新增：

```python
(self._timeline.playhead_seek_play, self._on_playhead_seek_play),
```

#### 3.4.2 槽函数实现

```python
def _on_playhead_seek_play(self, time_s: float):
    """双击空白区域 → Seek + Play"""

    # ── 焦点排除（复用 _on_space_shortcut 的检查模式）──
    if QApplication.activeWindow() is not self:
        return
    if QApplication.activeModalWidget() is not None:
        return
    if QApplication.activePopupWidget() is not None:
        return
    if isinstance(QApplication.focusWidget(), (
        QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
    )):
        return

    # ── 无帧时静默忽略 ──
    if not self._compositor.frames:
        return

    # ── Seek ──
    if self._playback:
        idx = int(time_s * self._compositor.fps)
        self._playback.seek(idx)
        self._update_frame_counter(idx)

    # ── 确保播放状态 ──
    if not self._playback:
        self._create_playback_controller()
        idx = int(time_s * self._compositor.fps)
        self._playback.play(idx)
    elif self._playback.is_paused:
        self._playback.pause()   # resume from pause
    elif not self._playback._playing:
        self._playback.play(self._playback.current_frame)

    self._btn_play.setText("⏸")
    self._btn_play.setToolTip("暂停")
```

**播放状态处理逻辑：**

| 当前播放状态 | 行为 |
|-------------|------|
| `_playback` 不存在 | 创建 → seek → play |
| 暂停 (`is_paused`) | seek → 恢复播放 |
| 停止 (`not _playing`) | seek → play |
| 正在播放 | seek（保持播放，不改变状态） |

**播放按钮同步：** 无论之前状态如何，最终都设置按钮为 "⏸"（暂停图标），与行为一致。

## 4. 边界条件覆盖

| 场景 | 预期行为 | 实现保障 |
|------|----------|----------|
| 单击视频/音频 clip | 选中 clip，播放头不动 | `_hit_test` 命中后 return，跳过播放头更新 |
| 单击 clip 边缘（resize 区） | 进入 resize 模式，播放头不动 | `_hit_edge` 命中后 return，跳过播放头更新 |
| 单击缩放 clip | 选中 + emit `zoom_clip_selected`，播放头不动 | `_hit_test` 命中后 return，保留 `zoom_clip_selected.emit` |
| 单击空白轨道区域 | 播放头跳转 | `_hit_test` 返回 (-1,-1)，进入播放头更新分支 |
| 单击标尺区域 | 播放头跳转 | `pos.y() < RULER_HEIGHT` 提前 return，不受 clip 判断影响 |
| 双击空白轨道区域 | 播放头跳转 + 开始播放 | `mouseDoubleClickEvent` 的 `elif` 分支 |
| 双击缩放轨道区域 | 缩放块创建/选中（现有行为） | zoom 轨道判断在 `if` 分支，优先级高于 `elif` |
| 双击在 clip 上方 | 无额外行为 | `ci >= 0` 不满足 `elif` 条件 |
| 双击时无视频帧 | 静默忽略 | `_on_playhead_seek_play` 中 `frames` 检查 |
| 输入框/弹窗获得焦点时双击 | 不触发播放 | `_on_playhead_seek_play` 中焦点排除检查 |

## 5. 不涉及的部分

| 排除项 | 原因 |
|--------|------|
| `mouseMoveEvent` (L247-289) | 拖拽/seek 逻辑不受影响，仍根据 `_drag_state` 分发 |
| `mouseReleaseEvent` (L327-348) | 仍根据 `_drag_state` 判断是否创建 `MoveClipCommand` |
| `_make_move_cmd` (L363-382) | 命令创建逻辑不变 |
| `paintEvent` 及渲染逻辑 | 播放头绘制仅依赖 `_playhead_s` 值，值正确则绘制正确 |
| 预览组件 (`PreviewWidget`) | `playhead_changed` 信号链路不变 |

## 6. 假设与不确定项

- **假设 1：** `PlaybackController` 的 `_playing` 和 `is_paused` 属性在 `_playback` 创建后立即反映正确状态。验证方式：创建后 `_playing` 应为 `False`，`play()` 调用后变为 `True`。
- **假设 2：** `mouseDoubleClickEvent` → `mousePressEvent` → `mouseDoubleClickEvent` 的 PyQt5 事件顺序不会因本次重构产生副作用（两次 playhead 更新到同一位置）。
- **不确定项：** 当前 `_hit_edge` 命中时，原始代码未设置 `_selected_track` / `_selected_clip`，修正后保持相同行为。如果未来需要 resize 时自动选中 clip，可另行变更。
