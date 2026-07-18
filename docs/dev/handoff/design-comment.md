# 技术方案：时间线编辑器交互增强

Phase 1 技术设计已完成，完整方案：

- PRD：`docs/prd/recordly-timeline-interaction-enhancements.md`
- Spec：`docs/dev/specs/recordly-timeline-interaction-enhancements.md`
- ADR：`docs/adr/2026-07-19-timeline-interaction-routing-and-snapping.md`

## 核心设计

1. **Space / X 分层路由**
   - Space 由 `MainWindow` 的 `Qt.WindowShortcut` 处理，复用 `_on_play_toggle()`；仅编辑器页、无 modal/popup、焦点不在输入控件时生效。
   - X 留在 `TimelineWidget.keyPressEvent()`；自动查找满足 `clip.start < playhead < clip.end` 的视频 Clip，复用 `SplitClipCommand`。无目标时状态栏提示，不弹窗。

2. **8px 同轨视频吸附**
   - 只在移动视频 Clip 时，比较同一视频轨道的相对边缘。
   - 以 Qt 逻辑像素计算：`distance_px = abs(candidate_time - target_time) * pixels_per_sec`，`<= 8px` 触发。
   - 选择最近候选，临时对齐线保存目标时间；释放后仍由 `MoveClipCommand` 记录最终位置。
   - 不处理跨轨、音频、resize、播放头或刻度吸附。

3. **缩放轨右键创建**
   - 缩放轨空白内容区新增“添加缩放块”，保留现有双击入口。
   - 继续使用 `Clip(type="zoom")` 和现有 `ZoomOverlay`，默认 2 秒、中央同画面宽高比矩形、`transition_duration=0.4`。
   - 新增最小 `AddClipCommand`，统一创建 undo/redo、`clips_changed` 和 compositor 同步；不新增模型或 JSON 字段。

## 兼容性与范围

- 与 ADR-005/006/007、项目管理 ADR、时间线 source 同步 ADR 均兼容，无冲突。
- 不修改 `core/project.py`、`ui/preview_widget.py`、compositor、导出管线或项目 schema。
- 明确排除 JKL、多选、跨轨拖动、播放头吸附、缩放关键帧/曲线、缩放工具栏按钮和 X 音频切割。

## 主要风险控制

- Space 误触：窗口级 shortcut + 页面、窗口、modal/popup、输入焦点守卫，关闭 auto-repeat。
- 高 DPI/缩放阈值漂移：使用逻辑像素和浮点时间差，不用整数化 x。
- source 被 move undo/redo 覆盖：普通 move 开始时同步捕获 source 原值。
- 项目尾部不足 2 秒：保持点击 start，end 截断到项目时长。

本 Planning PR 仅包含需求与设计文档，不包含业务代码实现。
