# ADR: 时间线交互的快捷键路由、吸附坐标与缩放块建模

**日期:** 2026-07-19
**状态:** Proposed
**关联:** Issue #78 / `docs/dev/specs/recordly-timeline-interaction-enhancements.md`

---

## 背景

时间线交互增强同时涉及应用级播放控制、Timeline 焦点内编辑命令、像素阈值吸附和缩放块创建。如果所有按键都放入 `TimelineWidget`，Space 无法覆盖预览区域；如果使用无边界的 ApplicationShortcut，又可能抢占输入框和弹窗。吸附还必须明确“8px”属于哪个坐标系，避免高 DPI 和整数取整导致行为漂移。缩放块创建则需要进入 undo/redo，但现有持久化已经使用通用 `Clip`。

## 决策

### 决策 1：Space 由 MainWindow 路由，X 留在 TimelineWidget

- Space 使用 `MainWindow` 持有的 `QShortcut`，上下文为 `Qt.WindowShortcut`，关闭 auto-repeat。
- Space 仅在编辑器页、主窗口活跃、无 modal/popup、焦点不在输入控件时调用现有 `_on_play_toggle()`。
- X 继续由 `TimelineWidget.keyPressEvent()` 处理，只有 Timeline 获得焦点时生效。
- X 按严格开区间 `clip.start < playhead < clip.end` 查找视频 Clip，并复用 `SplitClipCommand`；无目标时发状态信号，不弹窗。

### 决策 2：吸附阈值使用时间线 widget 的逻辑像素语义

- 8px 指 Qt widget 坐标中的逻辑像素，不乘设备像素比。
- 使用 `abs(candidate_time - target_time) * _pixels_per_sec` 比较浮点距离，不使用 `_time_to_x()` 的整数结果。
- 只比较当前视频轨道内“移动 Clip 左 ↔ 目标右”和“移动 Clip 右 ↔ 目标左”两类边缘。
- 多候选选择距离最近者，等距保持 Clip 列表顺序。
- 对齐线只保存目标时间 `_snap_alignment_time`，绘制时再转换为 x；它是瞬态 UI，不进入 Project 或命令栈。
- 最终位置仍由 `MoveClipCommand` 记录，吸附不新增命令类型。

### 决策 3：缩放块继续复用 Clip，并新增最小 AddClipCommand

- 手动缩放继续使用 `Track(type="zoom")` 下的 `Clip(type="zoom")`，沿用 `rect` 和 `transition_duration`。
- 不创建 ZoomBlock、关键帧或曲线模型，不修改 project.json schema。
- 右键入口发出创建请求，由 `MainWindow` 使用项目画面尺寸构造默认 Clip；现有双击入口保持不变并复用同一创建流程。
- 新增 `AddClipCommand` 负责固定索引插入/删除 Clip；undo 前回写当前 Clip 数据，使创建后调整过的字段可在 redo 后恢复。
- Timeline 在命令执行后自动选中新 Clip，MainWindow 继续负责显示现有 `ZoomOverlay`。

## 理由

1. `MainWindow` 已拥有 `_on_play_toggle()` 和工具栏状态，Space 复用该入口可以避免第二套播放状态机；X 属于纯时间线编辑命令，保留焦点边界更安全。
2. `Qt.WindowShortcut` 已覆盖当前窗口内的预览和时间线，并天然排除其他顶层窗口；显式守卫进一步保护首页、输入控件和弹窗。
3. 逻辑像素与 PRD 的视觉阈值一致，浮点时间差可避免整数 x 取整造成临界值跳变。
4. 吸附只是 move 的位置修正，不值得引入 SnapCommand；`MoveClipCommand` 已具备正确撤销语义。
5. 现有 Clip 已完整表达缩放块并可 JSON 序列化；新增领域模型会制造迁移和双模型同步问题。
6. 创建是现有命令集合唯一缺失的逆操作，`AddClipCommand` 是满足 undo/redo 的最小补充。

## 备选方案

### Space 使用 Qt.ApplicationShortcut

拒绝。它在应用任一窗口活跃时参与匹配，需要处理更多顶层窗口和未来面板，误触面大于 WindowShortcut。

### Space 与 X 都放在 TimelineWidget.keyPressEvent

拒绝。预览区域或其他编辑器区域拥有焦点时 Space 不可靠，不满足编辑器范围播放控制。

### 在 MainWindow 安装全局 eventFilter

拒绝。eventFilter 能精确截获按键，但侵入所有键盘事件；单个 QShortcut 加守卫更简单、可测试。

### 用秒数作为固定吸附阈值

拒绝。时间轴缩放后视觉距离会改变，无法满足固定 8px 体验。

### 使用整数 x 坐标比较吸附距离

拒绝。`_time_to_x()` 会截断，临界 8px 可能因取整提前或延后触发。

### 新建 ZoomBlock 模型或关键帧模型

拒绝。现有 `Clip(type="zoom")` 已满足本轮全部字段和持久化需求，且 PRD 明确排除关键帧与曲线。

### 创建时直接 append，再用特殊逻辑撤销

拒绝。会绕过统一 `_push_undo()`、`clips_changed` 和 compositor 同步路径，形成第二套编辑协议。

## 影响

- `app/main_window.py`：增加 Space 快捷键守卫，缩放创建改走 Timeline 命令入口。
- `ui/timeline.py`：增加 X 查询、状态/缩放请求信号、同轨吸附、对齐线和 add_clip 入口。
- `core/commands.py`：增加 `AddClipCommand`。
- `core/project.py`、`ui/preview_widget.py`、项目 JSON 和导出接口不变。

## 与既有 ADR 的关系

- 兼容 ADR-005：编辑器页是 Space 的显式边界，首页不响应。
- 兼容 ADR-006：继续使用现有 Clip JSON 持久化。
- 兼容 ADR-007：MainWindow 只承担 UI 编排并复用既有播放入口，不新增业务状态所有权。
- 兼容 `2026-07-17-timeline-trim-source-sync.md`：X 复用 SplitClipCommand，吸附复用 MoveClipCommand 并保留 source 字段。

## 后果

### 正向

- 播放与时间线编辑的快捷键边界清晰。
- 8px 吸附在高 DPI 和未来时间轴缩放下保持视觉一致。
- 缩放创建获得统一 undo/redo、变更通知和持久化路径。
- 无 schema 迁移、无新依赖、无新领域模型。

### 代价

- MainWindow 需要维护一组明确的焦点守卫。
- AddClipCommand 继续使用现有索引型命令语义，依赖 undo 栈 LIFO 顺序。
- 项目尾部创建的缩放块可能短于默认 2 秒。
