# 时间线裁剪功能完善 — 技术方案

**日期:** 2026-07-17
**状态:** Draft

---

## 1. 需求概述

基于 PRD `docs/prd/recordly-timeline-trim.md`，实现三个核心功能：

- **F1**: 修复边缘拖拽（`resize_left`/`resize_right`）时不更新 `source_start`/`source_end` 的 bug
- **F2**: Clip 边缘 hover 光标变化（`SizeHorCursor`）
- **F3**: 播放头一键裁剪（I 键裁前 / O 键裁后），复用 `SplitClipCommand` + `DeleteClipCommand`

影响文件：`ui/timeline.py`, `core/commands.py`

---

## 2. 整体架构变更

### 2.1 变更范围

```
core/commands.py          ← MoveClipCommand 扩展 source 字段
                             新增 CompositeCommand 宏命令
ui/timeline.py            ← mousePressEvent 捕获 _drag_orig_source_*
                             mouseMoveEvent 更新 source_start/source_end
                             mouseMoveEvent 非拖拽时边缘 hover 光标
                             _make_move_cmd 捕获 source 变更
                             新增 trim_in() / trim_out()
                             keyPressEvent 绑定 I/O 键
```

### 2.2 数据流 — F1 边缘拖拽修复

```
mousePressEvent
  ├─ _hit_edge() → resize_left / resize_right
  ├─ 记录 _drag_orig_source_start = clip.source_start
  ├─ 记录 _drag_orig_source_end   = clip.source_end
  └─ 记录 _drag_orig_start, _drag_orig_end

       ▼

mouseMoveEvent (每帧)
  ├─ resize_left:
  │   clip.start          = clamp(_drag_orig_start + dt, 0, clip.end - 0.5)
  │   clip.source_start   = _drag_orig_source_start + (clip.start - _drag_orig_start) * clip.speed
  │
  └─ resize_right:
      clip.end            = clamp(_drag_orig_end + dt, clip.start + 0.5, _duration)
      if clip.source_end is not None:
        clip.source_end   = _drag_orig_source_end + (clip.end - _drag_orig_end) * clip.speed

       ▼

mouseReleaseEvent
  └─ _make_move_cmd() 捕获:
      old_source_start, new_source_start (从 clip 当前值)
      old_source_end,   new_source_end   (从 clip 当前值)
      → MoveClipCommand 存入 undo 栈
```

### 2.3 数据流 — F3 一键裁剪

```
keyPressEvent (I 键)
  └─ trim_in()
      ├─ playhead 在 clip 内 → CompositeCommand(SplitClipCommand + DeleteClipCommand(左))
      └─ 一个 undo 步恢复整体操作

keyPressEvent (O 键)
  └─ trim_out()
      ├─ playhead 在 clip 内 → CompositeCommand(SplitClipCommand + DeleteClipCommand(右))
      └─ 一个 undo 步恢复整体操作
```

---

## 3. F1: 边缘拖拽 source 同步

### 3.1 问题根因

`ui/timeline.py:242-250` 中 `mouseMoveEvent` 的 `resize_left`/`resize_right` 分支只更新 `clip.start`/`clip.end`，不更新 `source_start`/`source_end`。

拆分后的 clip 具有显式 `source_end`（由 `SplitClipCommand:110-113` 设置），此时再拖拽边缘，`exporter.py:616` 使用的 `source_end` 仍是拆分时的旧值，导致 atrim 读取错误的音频范围。

### 3.2 解决方案

**核心公式（与 SplitClipCommand 一致）**：

```
source_position = source_start + (timeline_position - start) * speed
```

#### 3.2.1 resize_left

```
new_source_start = old_source_start + (new_start - old_start) * speed
```

- `source_start` 随左边缘移动同步漂移
- 右边缘不动，故 `source_end` 保持不变
- 适用于 source_end=None（首次录制 clip）和 source_end≠None（拆分后 clip）

#### 3.2.2 resize_right

当 `clip.source_end is not None`（拆分后 clip）：

```
new_source_end = old_source_end + (new_end - old_end) * speed
```

当 `clip.source_end is None`（未拆分 clip）：
- 不更新 source_end，导出时 `exporter.py:616` 动态计算 `source_start + (end - start)`

### 3.3 代码变更

#### 3.3.1 `ui/timeline.py` — `mousePressEvent`

在边缘拖拽捕获处新增两个成员变量：

```python
# __init__ 中新增（L51-52附近）
self._drag_orig_source_start = 0.0
self._drag_orig_source_end = None   # float | None，与 Clip.source_end 类型一致
```

```python
# mousePressEvent L191-197 修改
if edge:
    self._drag_track, self._drag_clip, self._drag_state = edge
    self._drag_start_x = pos.x()
    clip = self._tracks[self._drag_track].clips[self._drag_clip]
    self._drag_orig_start = clip.start
    self._drag_orig_end = clip.end
    self._drag_orig_source_start = clip.source_start       # 新增
    self._drag_orig_source_end = clip.source_end             # 新增
    return
```

#### 3.3.2 `ui/timeline.py` — `mouseMoveEvent`

修改 L242-250 的 resize 分支：

```python
elif self._drag_state == "resize_left":
    new_start = max(0.0, min(self._drag_orig_start + dt, clip.end - 0.5))
    d_start = new_start - self._drag_orig_start
    clip.start = new_start
    clip.source_start = self._drag_orig_source_start + d_start * clip.speed
elif self._drag_state == "resize_right":
    new_end = min(
        self._duration,
        max(clip.start + 0.5, self._drag_orig_end + dt),
    )
    d_end = new_end - self._drag_orig_end
    clip.end = new_end
    if clip.source_end is not None:
        clip.source_end = self._drag_orig_source_end + d_end * clip.speed
```

> **设计要点**：使用 `_drag_orig_source_start` + 累积偏移（而非每帧增量），避免浮点误差累积。

#### 3.3.3 `ui/timeline.py` — `_make_move_cmd`

扩展命令创建逻辑（L289-298）：

```python
def _make_move_cmd(self) -> MoveClipCommand | None:
    if self._drag_state in ("move", "resize_left", "resize_right"):
        clip = self._tracks[self._drag_track].clips[self._drag_clip]
        if abs(clip.start - self._drag_orig_start) > 0.01 or abs(clip.end - self._drag_orig_end) > 0.01:
            return MoveClipCommand(
                track_index=self._drag_track, clip_index=self._drag_clip,
                old_start=self._drag_orig_start, new_start=clip.start,
                old_end=self._drag_orig_end, new_end=clip.end,
                old_source_start=self._drag_orig_source_start,
                new_source_start=clip.source_start,
                old_source_end=self._drag_orig_source_end,
                new_source_end=clip.source_end,
            )
    return None
```

#### 3.3.4 `core/commands.py` — `MoveClipCommand` 扩展

新增 4 个字段，在 `execute`/`undo` 中同时恢复 source 字段：

```python
@dataclass
class MoveClipCommand(UndoCommand):
    track_index: int
    clip_index: int
    old_start: float
    new_start: float
    old_end: float
    new_end: float
    old_track: int = -1
    new_track: int = -1
    old_source_start: float = 0.0
    new_source_start: float = 0.0
    old_source_end: float | None = None
    new_source_end: float | None = None

    def execute(self, timeline):
        if self.new_track >= 0 and self.new_track != self.old_track:
            clip = timeline._tracks[self.old_track].clips.pop(self.clip_index)
            timeline._tracks[self.new_track].clips.append(clip)
            clip.start = self.new_start
            clip.end = self.new_end
        else:
            t = timeline._tracks[self.track_index]
            clip = t.clips[self.clip_index]
            clip.start = self.new_start
            clip.end = self.new_end
        # 新增：恢复 source 字段
        clip.source_start = self.new_source_start
        clip.source_end = self.new_source_end

    def undo(self, timeline):
        if self.new_track >= 0 and self.new_track != self.old_track:
            clip = timeline._tracks[self.new_track].clips.pop()
            timeline._tracks[self.old_track].clips.insert(self.clip_index, clip)
            clip.start = self.old_start
            clip.end = self.old_end
        else:
            t = timeline._tracks[self.track_index]
            clip = t.clips[self.clip_index]
            clip.start = self.old_start
            clip.end = self.old_end
        # 新增：恢复 source 字段
        clip.source_start = self.old_source_start
        clip.source_end = self.old_source_end

    def __repr__(self):
        return f"MoveClip(t{self.track_index}: {self.old_start:.1f}→{self.new_start:.1f})"
```

---

## 4. F2: Clip 边缘 hover 光标

### 4.1 实现方案

在 `mouseMoveEvent` 的非拖拽分支中，调用 `_hit_edge()` 检测边缘接近度，用 `setCursor` 切换光标。

**阈值**：复用 `SnapDistance = 5`（5 像素），初版不额外引入独立阈值。若体验需要可后续调大。

### 4.2 代码变更

仅 `ui/timeline.py` — `mouseMoveEvent`：

```python
def mouseMoveEvent(self, event):
    pos = event.localPos()

    if self._drag_state in ("move", "resize_left", "resize_right", "playhead"):
        # ... 现有拖拽逻辑不变 ...
        return

    # 非拖拽状态 — 边缘 hover 光标
    if pos.y() >= RULER_HEIGHT and self._hit_edge(pos):
        self.setCursor(Qt.SizeHorCursor)
    else:
        self.setCursor(Qt.ArrowCursor)
```

---

## 5. F3: 播放头一键裁剪

### 5.1 设计决策

**选择方案 B：组合 SplitClipCommand + DeleteClipCommand，通过 CompositeCommand 包装为单个可撤销单元。**

理由：
- 复用现有测试过的 SplitClipCommand 和 DeleteClipCommand，不引入重复逻辑
- `CompositeCommand` 将两个子命令封装为一个 undo 步，满足"一次 Ctrl+Z 恢复整个裁剪操作"
- `CompositeCommand` 本身是通用组件，后续 Ripple Delete (E2) 等复合操作可复用

### 5.2 代码变更

#### 5.2.1 `core/commands.py` — 新增 `CompositeCommand`

```python
@dataclass
class CompositeCommand(UndoCommand):
    """将多个子命令组合为单个可撤销/重做单元。
    execute: 顺序执行子命令
    undo:    逆序撤销子命令
    """
    sub_commands: list  # list[UndoCommand]

    def execute(self, timeline):
        for cmd in self.sub_commands:
            cmd.execute(timeline)

    def undo(self, timeline):
        for cmd in reversed(self.sub_commands):
            cmd.undo(timeline)

    def __repr__(self):
        inner = ', '.join(repr(c) for c in self.sub_commands)
        return f"Composite({inner})"
```

#### 5.2.2 `ui/timeline.py` — 新增 `trim_in()` / `trim_out()`

```python
def trim_in(self):
    """裁掉播放头之前的内容（I 键）。
    对选中 clip：播放头处拆分 → 删除左半边。
    整体作为一个 undo 步。
    """
    if self._selected_clip < 0:
        return
    clip = self._tracks[self._selected_track].clips[self._selected_clip]
    if self._playhead_s <= clip.start:
        return
    if self._playhead_s >= clip.end:
        self.delete_clip(self._selected_track, self._selected_clip)
        self._selected_clip = -1
        return

    split_cmd = SplitClipCommand(
        self._selected_track, self._selected_clip, self._playhead_s)
    delete_cmd = DeleteClipCommand(
        self._selected_track, self._selected_clip)
    # 拆分后左半边在 self._selected_clip，删除后右半边自动移到该位置
    self._push_undo(CompositeCommand([split_cmd, delete_cmd]))

def trim_out(self):
    """裁掉播放头之后的内容（O 键）。
    对选中 clip：播放头处拆分 → 删除右半边。
    """
    if self._selected_clip < 0:
        return
    clip = self._tracks[self._selected_track].clips[self._selected_clip]
    if self._playhead_s >= clip.end:
        return
    if self._playhead_s <= clip.start:
        self.delete_clip(self._selected_track, self._selected_clip)
        self._selected_clip = -1
        return

    split_cmd = SplitClipCommand(
        self._selected_track, self._selected_clip, self._playhead_s)
    # 拆分后右半边在 self._selected_clip + 1
    delete_cmd = DeleteClipCommand(
        self._selected_track, self._selected_clip + 1)
    self._push_undo(CompositeCommand([split_cmd, delete_cmd]))
```

#### 5.2.3 `ui/timeline.py` — `keyPressEvent` 绑定

在 `keyPressEvent` 中（L363 之后）插入：

```python
if event.key() == Qt.Key_I:
    self.trim_in()
    return
if event.key() == Qt.Key_O:
    self.trim_out()
    return
```

### 5.3 边界情况处理

| 场景 | trim_in 行为 | trim_out 行为 |
|------|-------------|---------------|
| 无选中 clip | 无操作 | 无操作 |
| playhead ≤ clip.start | 无操作 | 删除整个 clip |
| playhead ≥ clip.end | 删除整个 clip | 无操作 |
| playhead 在 clip 内 | 拆分 + 删除左 | 拆分 + 删除右 |
| 多个 clip 覆盖 playhead | 仅操作选中的那一个 | 仅操作选中的那一个 |

---

## 6. 测试策略

### 6.1 F1 — 边缘拖拽 source 同步

| 测试场景 | 验证点 |
|----------|--------|
| 未拆分 clip 做 resize_left | source_start 随 start 增加 `d_start * speed`；source_end 保持 None |
| 未拆分 clip 做 resize_right | start/end 改变；source_end 保持 None |
| 拆分后右半 clip 做 resize_left | source_start 增加，source_end 不变；undo 后恢复原值 |
| 拆分后右半 clip 做 resize_right | source_end 减少；undo 后恢复原值 |
| 拆分后 clip 做 resize 后导出 | 音频长度 = 视觉长度 |
| resize 操作 undo/redo | start/end/source_start/source_end 全部恢复 |
| speed=2.0 时 resize_left | source_start 偏移量 = 时间线偏移 × 2 |

### 6.2 F2 — 边缘 hover 光标

| 测试场景 | 验证点 |
|----------|--------|
| 鼠标在左边缘 5px 内 | 光标变为 SizeHorCursor |
| 鼠标在右边缘 5px 内 | 光标变为 SizeHorCursor |
| 鼠标移离边缘 | 光标恢复 ArrowCursor |
| 鼠标在 clip 中间 | 光标为 ArrowCursor |
| 拖拽过程中 | 光标切换不影响拖拽行为 |

### 6.3 F3 — 一键裁剪

| 测试场景 | 验证点 |
|----------|--------|
| 选中 clip，playhead 在中间，按 I | clip 拆分为二，左边删除，右边保留 |
| 选中 clip，playhead 在中间，按 O | clip 拆分为二，右边删除，左边保留 |
| 按 I 后再 Ctrl+Z | 一次撤销恢复整个裁剪操作（非两步） |
| 按 O 后再 Ctrl+Z | 一次撤销恢复整个裁剪操作 |
| playhead 在 clip 开头，按 I | 无操作 |
| playhead 在 clip 结尾，按 O | 无操作 |
| 无选中 clip 时按 I/O | 无操作 |
| 裁剪后 project.json 保存再加载 | Clip 数据完整 |

---

## 7. 实施计划

### 7.1 子任务 DAG

```
T1: MoveClipCommand 扩展 source 字段     ← 无依赖
T2: mouseMoveEvent 更新 source           ← T1
T3: _make_move_cmd 捕获 source 变更       ← T1
T4: mousePressEvent 捕获 drag_orig_source ← T2
T5: 边缘 hover 光标 (F2)                  ← 无依赖
T6: CompositeCommand (F3)                ← 无依赖
T7: trim_in/trim_out + keyPressEvent     ← T6
T8: 集成测试 + 手动验证                   ← T4, T5, T7
```

### 7.2 实施建议

- **T1-T4** 作为一组连续提交（F1 完整修复），改动集中在 `ui/timeline.py` 和 `core/commands.py`
- **T5** 独立提交（F2），仅改动 `mouseMoveEvent` 末尾
- **T6-T7** 作为一组提交（F3），引入 `CompositeCommand` + 两个 trim 方法
- 每个任务 1-2 小时可完成

---

## 8. 技术约束

| 约束 | 遵循方式 |
|------|---------|
| Python 3.11+ | 使用 `float \| None` 类型注解 |
| PyQt5 | 使用 `Qt.SizeHorCursor` / `Qt.ArrowCursor` / `Qt.Key_I` / `Qt.Key_O` |
| 所有修改经 UndoCommand | MoveClipCommand 扩展 + CompositeCommand |
| 与 SplitClipCommand 公式一致 | `source_start + (time - start) * speed` |
| JSON 序列化兼容 | source_start/source_end 均为 float/None，已支持 |

---

## 9. 假设与不确定项

1. **SnapDistance=5 作为边缘 hover 阈值**：当前 `_hit_edge` 使用 `SnapDistance=5`。初版复用此值，若用户反馈 "不好点到"，后续可调至 8-10px 而无需改逻辑。

2. **I/O 键未冲突**：当前 `keyPressEvent` 中 Delete/Backspace/S/←/→ 已占用，I/O 空闲。后续添加 JKL 播放控制时需注意不与 I/O 冲突。

3. **trim_in/trim_out 仅作用于选中 clip**：不自动选择覆盖 playhead 的 clip。这是保守选择，避免"裁剪了用户未预期的 clip"。后续可考虑"无选中时自动选择 playhead 处的 clip"。

4. **exporter 中 source_end 默认计算未乘 speed**：`exporter.py:616` 在 source_end=None 时使用 `source_start + (end - start)` 而非 `source_start + (end - start) * speed`。这与 `sync_audio_regions_from_clips`（`project.py:152-155`）的行为不一致。本修复不改变 exporter 行为，因为 F1 仅涉及显式 source_end 场景（拆分后 clip）。该不一致是否影响非拆分 clip 的变速导出需单独排查，但不在本 PRD 范围内。
