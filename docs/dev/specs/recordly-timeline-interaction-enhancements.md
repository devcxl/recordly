# 时间线编辑器交互增强 — 技术方案

**日期:** 2026-07-19
**状态:** Draft
**关联:** Parent Issue #78 / `docs/prd/recordly-timeline-interaction-enhancements.md`

---

## 1. 目标与范围

本方案在现有 PyQt5 时间线、命令栈和预览组件上增量实现三项能力：

1. Space 在编辑器范围内切换播放/暂停；X 在时间线获得焦点时切割播放头下的视频片段。
2. 移动视频片段时，在同一视频轨道内按 8px 逻辑像素阈值吸附相邻片段边缘，并绘制临时对齐线。
3. 缩放轨道空白区域支持右键创建缩放块，创建操作进入现有 undo/redo 栈。

坚持最小设计：不引入新框架、新 Controller、新持久化模型或全局事件总线；不实现 JKL、多选、跨轨拖动、播放头吸附、缩放关键帧、缩放曲线或工具栏入口。

## 2. 现状与兼容性结论

### 2.1 当前实现

- `MainWindow._on_play_toggle()` 已统一工具栏播放按钮及 `PlaybackController` 的播放/暂停行为。
- `TimelineWidget.keyPressEvent()` 已承载 Delete、S、I、O、方向键等时间线快捷键，时间线在编辑器中使用 `Qt.StrongFocus`。
- `SplitClipCommand` 已正确按 `speed` 拆分 `source_start/source_end`，并支持 undo/redo。
- 片段移动在 `mouseMoveEvent()` 中实时修改 `Clip.start/end`，释放鼠标后写入 `MoveClipCommand`。
- 缩放效果已使用 `Clip(type="zoom")`、`Track(type="zoom")` 和 `ZoomOverlay`；双击空白缩放轨道会由 `MainWindow._on_zoom_double_clicked()` 直接追加 Clip，但当前创建不进入命令栈。
- `PreviewWidget`/`ZoomOverlay` 已支持缩放矩形显示、移动和按项目画面宽高比缩放，无需修改。

### 2.2 兼容性结论

方案与现有架构兼容，且无需数据迁移：

- 快捷键只复用 `MainWindow` 的播放入口与 `TimelineWidget` 的键盘入口，不下沉到 `PlaybackController`。
- X 复用 `SplitClipCommand`；吸附复用 `MoveClipCommand`；缩放创建仅补充最小的 `AddClipCommand`。
- 缩放块继续序列化为现有 `Clip`，`project.json` schema 不变。
- `ui/preview_widget.py`、`core/project.py`、合成器和导出管线均不需要修改。

## 3. 总体架构

```text
Space
  QShortcut（MainWindow / WindowShortcut）
    → 编辑器页、弹窗、Popup、输入焦点守卫
    → MainWindow._on_play_toggle()
    → PlaybackController + 工具栏按钮状态

X（TimelineWidget 有焦点）
  TimelineWidget.keyPressEvent()
    → 查找 playhead 严格落在内部的视频 Clip
    → SplitClipCommand → _push_undo()
    → clips_changed → MainWindow._on_clips_changed()

视频 Clip 拖动
  mouseMoveEvent()
    → 计算未吸附且已 clamp 的候选 start/end
    → 同轨视频 Clip 边缘候选，按逻辑像素选择最近点
    → 实时写入 start/end + 保存对齐时间
    → paintEvent() 绘制临时虚线
  mouseReleaseEvent()
    → MoveClipCommand 记录最终吸附位置

缩放轨右键 / 现有双击
  TimelineWidget 发出创建请求
    → MainWindow 构造默认 Clip(type="zoom")
    → TimelineWidget.add_clip()
    → AddClipCommand → _push_undo()
    → 自动选中 + MainWindow 显示 ZoomOverlay
```

## 4. 详细设计

### 4.1 Space：应用交互层路由与焦点边界

#### 4.1.1 路由

Space 由 `MainWindow` 持有一个 `QShortcut`，上下文使用 `Qt.WindowShortcut`，并关闭 auto-repeat。快捷键只调用现有 `_on_play_toggle()`，确保工具栏按钮、播放状态及起播位置继续使用同一条逻辑。

不使用 `Qt.ApplicationShortcut`。Recordly 的播放操作属于当前编辑窗口；应用级上下文会在其他顶层窗口活跃时仍参与匹配，增加设置、导出等窗口误触风险。

#### 4.1.2 触发守卫

仅同时满足下列条件时处理 Space：

1. 当前页面是 `_editor_interface`，首页不响应。
2. `MainWindow` 是当前活动窗口。
3. `QApplication.activeModalWidget()` 和 `activePopupWidget()` 均为空。
4. 当前焦点不是文本或数值输入控件：`QLineEdit`、`QTextEdit`、`QPlainTextEdit`、`QAbstractSpinBox`、`QComboBox`。

守卫失败时不调用 `_on_play_toggle()`，保留控件或对话框自身的 Space 语义。无可播放帧时继续沿用 `_on_play_toggle()` 的无操作行为。

#### 4.1.3 状态语义

| 当前状态 | Space 结果 |
|----------|------------|
| 正在播放 | 暂停，当前帧和播放头保持不变 |
| 已暂停 | 从当前帧继续播放 |
| 已停止且有帧 | 从当前播放位置起播；若位于末帧则沿用现有逻辑回到第 0 帧 |
| 无帧、首页、输入框或弹窗 | 不处理 |

### 4.2 X：自动查找播放头下的视频 Clip

X 保留在 `TimelineWidget.keyPressEvent()`，因此只有时间线实际获得焦点时触发。仅处理 `Qt.NoModifier` 的 X，避免覆盖组合快捷键。

新增私有查询方法，按轨道顺序、Clip 列表顺序查找第一个满足以下条件的目标：

```text
track.type == "video"
clip.type == "video"
clip.start < playhead < clip.end
```

使用严格开区间，播放头等于任一边缘时视为无目标，防止零宽片段。命中后调用现有 `_split_clip(track_index, clip_index)`，由 `SplitClipCommand` 完成 source 映射和 undo/redo。

未命中时不修改选择、模型或命令栈，通过新增 `status_message(str)` 信号发送固定文案 `播放头下无视频片段`，`MainWindow.update_status()` 负责显示；不弹出阻塞对话框。

当前项目只有一个主视频轨。若异常数据中存在多个重叠视频 Clip，采用“轨道顺序优先、Clip 列表顺序优先”的确定性规则，不在本次引入层级或多选模型。

### 4.3 同轨视频片段吸附与对齐线

#### 4.3.1 生效范围

仅在 `_drag_state == "move"` 且当前 Track、Clip 均为 `video` 时计算吸附。以下场景明确不参与：

- `resize_left` / `resize_right`；
- zoom、audio、audio_extra 等非视频轨道；
- 其他视频轨道；
- 播放头、刻度线、项目起止边界。

#### 4.3.2 坐标语义

8px 指 Qt widget 坐标系中的逻辑像素。Qt 鼠标坐标和 `_pixels_per_sec` 均基于逻辑坐标，因此不乘 `devicePixelRatio`。

先按现有规则计算并 clamp 未吸附位置，再比较以下两类边缘：

```text
拖动 Clip 左边缘  ↔ 同轨其他 Clip 右边缘
拖动 Clip 右边缘  ↔ 同轨其他 Clip 左边缘

distance_px = abs(candidate_time - target_time) * _pixels_per_sec
```

当 `distance_px <= 8.0` 且对齐后的 start 仍位于 `[0, duration - clip_duration]` 时成为候选；选择距离最小的候选，等距时保持 Track.clips 遍历顺序。吸附后只平移 `start/end`，保持时长及其他字段不变。

该计算不使用 `_time_to_x()` 的整数结果，避免整数取整导致 8px 边界在不同缩放比例下漂移。

#### 4.3.3 对齐线

`TimelineWidget` 增加瞬态状态 `_snap_alignment_time: float | None`，保存目标边缘的时间值而不是缓存 x 坐标。`paintEvent()` 每次用 `_time_to_x()` 转换并绘制贯穿轨道区域的 1px 垂直虚线。

以下时机必须清空对齐线并刷新：

- 当前移动帧没有吸附候选；
- 鼠标释放或拖动取消；
- `set_tracks()` 更换项目数据。

对齐线不进入 Clip、Project 或 undo/redo 数据。

#### 4.3.4 undo/redo 与 source 字段

吸附在拖动过程中实时修改 Clip；鼠标释放后仍由现有 `_make_move_cmd()` 记录最终值。`MoveClipCommand` 无需新增字段。

为满足“不改变 start/end 之外属性”，普通 move 开始时必须与 resize 一样捕获 `_drag_orig_source_start/_drag_orig_source_end`，使 `_make_move_cmd()` 的 old/new source 均为当前 Clip 原值。否则现有代码可能沿用上一次拖拽的缓存，在 undo/redo 时错误覆盖 source 字段。

### 4.4 缩放轨右键创建及 undo/redo

#### 4.4.1 入口与命中规则

`TimelineWidget._show_context_menu()` 在下列条件同时满足时增加“添加缩放块”：

- 右键位置位于 `type="zoom"` 的 Track 行；
- x 位于时间线内容区（不含 Track header）；
- 当前位置没有命中已有 Clip。

菜单动作将 x 转换为 `[0, duration]` 内的时间，并通过新增 `zoom_add_requested(float)` 信号交给 `MainWindow._on_zoom_double_clicked(time_s, None)`。现有双击行为及 `zoom_double_clicked(float, object)` 信号保持不变，两条入口复用同一个创建流程。

为避免 GUI 测试阻塞，可将菜单构造提取为返回 `QMenu` 的私有方法，`_show_context_menu()` 只负责 `exec_()`。

#### 4.4.2 默认 Clip

由 `MainWindow` 继续使用项目画面尺寸和 `config.zoom_rect_ratio` 构造现有模型：

```text
type                = "zoom"
start               = 点击时间
end                 = min(start + 2.0, timeline.duration)
content             = "手动缩放"
rect                = 项目画面中央、宽高比与项目画面一致
transition_duration = 0.4
```

点击位置距项目结尾不足 2 秒时，保持 start 等于点击时间并将 end 截断到项目时长；不允许创建超出视频时间线的效果。

#### 4.4.3 创建命令

`core/commands.py` 新增 `AddClipCommand`：

```python
@dataclass
class AddClipCommand(UndoCommand):
    track_index: int
    clip_data: dict
    clip_index: int | None = None

    def execute(self, timeline): ...  # 在固定索引插入 Clip
    def undo(self, timeline): ...     # 删除同一索引的 Clip
```

- 首次 execute 在未指定索引时取当前列表末尾，并保存索引。
- 每次 execute 从 `clip_data` 重建 Clip；Clip 数据（包括 id、rect、transition_duration）在 redo 后保持一致。
- undo 删除该索引前先用当前 Clip 的 `asdict()` 刷新 `clip_data`，确保创建后已调整的矩形等字段可在 redo 后恢复。
- 命令依赖现有 LIFO undo 栈保证索引有效。

`TimelineWidget.add_clip(track_index, clip) -> Clip` 将命令推入 `_push_undo()`，再将新 Clip 设为当前选中项。`MainWindow` 使用返回对象设置 `_editing_zoom_clip` 并显示 `ZoomOverlay`。

undo 删除缩放块时，现有 `clips_changed → _on_clips_changed()` 会同步 compositor，并在编辑对象已不存在时隐藏 Overlay；redo 恢复 Clip 数据。选择和 Overlay 属于瞬态 UI，不写入 Project。

移动、边缘裁剪和删除继续分别复用 `MoveClipCommand`、`MoveClipCommand` 和 `DeleteClipCommand`。

## 5. 接口与模型变更

### 5.1 内部接口

| 位置 | 接口 | 输入 | 输出/事件 | 失败或无目标 |
|------|------|------|-----------|-------------|
| `MainWindow` | 编辑器 Space `QShortcut` | Space | 调用 `_on_play_toggle()` | 守卫失败或无帧时无操作 |
| `TimelineWidget` | `status_message` | `str` | MainWindow 状态栏文案 | 无异常传播 |
| `TimelineWidget` | `zoom_add_requested` | `time_s: float` | 请求创建缩放 Clip | 非缩放轨/命中 Clip 时不提供动作 |
| `TimelineWidget` | `add_clip(track_index, clip)` | 轨道索引、Clip | 返回实际插入的 Clip | 无效索引按现有内部编程错误处理，不新增用户错误码 |
| `AddClipCommand` | `execute/undo` | timeline | 插入/删除 Clip | 依赖命令栈 LIFO 约束 |

本功能是本地桌面 UI 交互，不新增 HTTP API、IPC 协议或错误码。

### 5.2 数据模型

不新增模型和字段。继续复用：

- `Track.type == "video"` / `"zoom"`；
- `Clip.start/end/source_start/source_end/speed`；
- `Clip.rect`；
- `Clip.transition_duration`，默认值已为 0.4。

`project.json` 结构和向后兼容策略不变。

## 6. 预计影响文件

| 文件 | 变更 |
|------|------|
| `app/main_window.py` | Space 快捷键及焦点守卫；连接新增 Timeline 信号；缩放创建改走命令栈 |
| `ui/timeline.py` | X 查询与状态信号；8px 吸附和对齐线；右键缩放入口；`add_clip()` |
| `core/commands.py` | 新增 `AddClipCommand` |
| `tests/test_timeline.py` | X、吸附、对齐线、右键菜单、AddClip undo/redo |
| `tests/test_main_window.py` | Space 边界、缩放默认值/选中/Overlay、信号连接 |
| `tests/test_preview_widget.py` | 原有 ZoomOverlay 回归；预计无需新增生产代码对应改动 |

不修改 `ui/preview_widget.py`、`core/project.py`、`core/compositor.py` 或导出模块。

## 7. 测试策略

### 7.1 自动化测试

#### Space

- 编辑器页、无输入焦点时触发，验证只调用一次 `_on_play_toggle()`。
- 首页不触发。
- `QLineEdit`、`QTextEdit`、`QPlainTextEdit`、`QAbstractSpinBox`、`QComboBox` 获得焦点时不触发。
- modal dialog 或 popup 活跃时不触发。
- auto-repeat 不产生连续播放状态翻转。
- 复用现有播放逻辑验证暂停后播放头不回退、继续播放从当前帧开始、按钮文字同步。

#### X

- 无需选中 Clip，播放头位于视频 Clip 内部时正确拆分。
- 音频 Clip 覆盖播放头但视频 Clip 不覆盖时不拆分。
- 播放头等于 start/end 时不拆分并发出状态文案。
- 无目标时命令栈不变化。
- X 拆分后的 `source_start/source_end` 与 S 路径一致，undo/redo 正确。
- Timeline 未获焦时由 MainWindow 路由测试确认不会触发 X。

#### 吸附

- 同一视频轨道边缘距离恰好 8px 时吸附，超过 8px 时不吸附。
- 左边缘到目标右边缘、右边缘到目标左边缘两种方向均覆盖。
- 多个候选选择像素距离最近者。
- 不同视频轨道、音频轨道、zoom 轨道均不吸附。
- 吸附时 `_snap_alignment_time` 正确，离开阈值和 mouse release 后清空。
- 鼠标释放只产生一个 `MoveClipCommand`；undo/redo 恢复位置。
- move 前后 `source_start/source_end/speed/content` 不变。

#### 缩放块

- 仅缩放轨道内容区空白位置出现“添加缩放块”。
- 右键动作发出的时间与点击 x 一致并受 duration 限制。
- 默认持续 2 秒、尾部截断、中央矩形宽高比、`transition_duration=0.4`。
- 创建后自动选中并显示 `ZoomOverlay`。
- 一次 undo 删除，一次 redo 恢复全部 Clip 字段；compositor 同步且 undo 后 Overlay 隐藏。
- 现有双击空白创建、双击已有缩放块和单击选中行为继续通过。

### 7.2 验证命令

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py tests/test_main_window.py tests/test_preview_widget.py
QT_QPA_PLATFORM=offscreen pytest -q
git diff --check
```

### 7.3 手工验收

1. 打开项目，在预览和时间线区域分别按 Space，确认播放按钮与实际状态同步。
2. 在设置/导出弹窗及文本输入控件中按 Space，确认不控制播放。
3. 不选 Clip，将播放头放入视频片段后按 X，再执行 undo/redo。
4. 以不同拖动方向靠近同轨片段，观察 8px 吸附与虚线出现/消失。
5. 在缩放轨空白区域右键创建，确认选中、Overlay、保存重开及 undo/redo。

## 8. ADR 兼容性检查

| ADR | 结论 |
|-----|------|
| `005-home-editor-dual-view.md` | Space 以当前 `_editor_interface` 为显式边界，首页不响应，符合双页面架构。 |
| `006-data-persistence-json.md` | 继续使用现有 Track/Clip JSON 序列化，不新增 schema。 |
| `007-project-session-recording-export-controllers.md` | MainWindow 仅增加 UI 快捷键编排并复用现有 handler；不新增业务状态所有权或 Controller。 |
| `2026-07-13-project-management.md` | 不改变项目目录、JSON 或缩略图方案。 |
| `2026-07-17-timeline-trim-source-sync.md` | X 复用 SplitClipCommand；吸附复用 MoveClipCommand，并补齐 move 开始时 source 原值捕获，保持既有 source 同步决策。 |

无冲突 ADR。

## 9. 风险与控制

| 风险 | 控制 |
|------|------|
| Space 抢占输入控件或弹窗按键 | WindowShortcut + 页面/窗口/modal/popup/输入控件守卫；关闭 auto-repeat |
| 高 DPI 或时间轴缩放导致阈值不一致 | 使用 Qt 逻辑像素和浮点时间差计算，不使用整数化 x |
| 多候选吸附抖动 | 始终选最近候选，等距按稳定列表顺序；未命中立即清线 |
| move undo/redo 覆盖 source 字段 | move press 捕获当前 source 原值并写入 MoveClipCommand |
| 缩放创建绕过 compositor 或持久化 | 统一 `_push_undo()` 发出 `clips_changed`，继续由 MainWindow 同步和保存 |
| 尾部缩放块不足 2 秒 | 保持点击位置并截断到项目时长，避免超出有效视频范围 |

## 10. 假设与不确定项

1. 当前有效项目只有一个主视频轨；异常项目存在多视频轨或重叠 Clip 时按轨道/列表顺序选择第一个目标。
2. 8px 为当前时间轴缩放下的逻辑像素，而非固定秒数；未来调整 `_pixels_per_sec` 时阈值仍保持视觉一致。
3. “默认 2 秒”在项目尾部按剩余时长截断，这是对现有双击行为的兼容处理。
4. undo/redo 保证 Clip 数据恢复；选中态和 Overlay 是瞬态 UI，不写入命令或 Project。首次创建必须自动选中并显示 Overlay，redo 不强制自动打开编辑框。
5. 本阶段只输出设计和 Planning PR，不实现上述生产代码或测试代码。
