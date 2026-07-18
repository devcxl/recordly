# ADR: 播放头点击行为 — 事件路由与信号设计

**日期:** 2026-07-19
**状态:** Proposed
**关联:** Issue #94 / `docs/dev/specs/recordly-playhead-click-behavior.md`

---

## 背景

`TimelineWidget.mousePressEvent` 当前先移动播放头再判断点击目标，导致点击 clip 时播放头也会跳转，干扰编辑。同时需新增"双击空白区域→跳转+播放"功能。这涉及两个架构问题：

1. `mousePressEvent` 中播放头更新与 clip 交互的判断顺序
2. 双击事件的播放请求如何从 `TimelineWidget` 传递到 `MainWindow`

## 决策

### 决策 1：`mousePressEvent` 先判断点击目标，再决定是否移动播放头

**做法：**
- 将 `_hit_test` 和 `_hit_edge` 提升到播放头更新之前
- 标尺区域（`pos.y() < RULER_HEIGHT`）作为快速路径提前 return，始终移动播放头
- 命中 clip（含边缘 resize 区）→ 进入拖拽模式，跳过播放头更新
- 空白区域 → 移动播放头 + 清除选中

**不选择「先移播放头再用 flag 回滚」方案：**
- 回滚需要撤销已发射的 `playhead_changed` 信号，违反 Qt 信号语义（信号一旦发射无法撤销）
- 即使抑制 `playhead_changed`，`_playhead_s` 的写-回滚仍会在渲染帧中产生闪烁
- 先判断再执行更符合 MVC/MVP 中输入路由的直觉

### 决策 2：新增 `playhead_seek_play` 信号，而非复用 `playhead_changed`

**做法：**
- `TimelineWidget` 新增 `playhead_seek_play = pyqtSignal(float)`
- `MainWindow` 在 `_connect_timeline_signals()` 中连接该信号
- 双击空白区域时：先更新 `_playhead_s` + 发射 `playhead_changed`（维持原有 seek 行为），再发射 `playhead_seek_play`（触发播放）

**为何不复用 `playhead_changed`：**
- `playhead_changed` 是 seek 信号，语义是"播放头位置变了"，消费方（`_on_timeline_seek`）只做 seek，不做播放
- 如果让 `playhead_changed` 在某些条件下额外触发播放，需要额外状态（如 `_pending_play` flag），增加隐式耦合
- 新增独立信号让两件事（seek、play）的意图明确分离，消费方各自处理各自的职责

**为何不选择回调函数：**
- `TimelineWidget` 已在多处使用 `pyqtSignal` 通信（`playhead_changed`、`zoom_double_clicked`、`zoom_clip_selected`、`clips_changed`、`status_message`），新增信号与现有模式一致
- 回调函数需要 `TimelineWidget` 持有对 `MainWindow` 或回调对象的引用，增加组件间耦合
- 信号支持多对多连接，未来如有其他组件需要响应"双击播放"事件，无需修改 `TimelineWidget`

### 决策 3：焦点排除复用 `_on_space_shortcut` 的检查模式

**做法：**
- `_on_playhead_seek_play` 中直接内联与 `_on_space_shortcut` 相同的守卫条件：
  - `activeWindow() is not self` — 不在主窗口
  - `activeModalWidget()` — 有模态弹窗
  - `activePopupWidget()` — 有弹出菜单
  - 焦点在 `QLineEdit/QTextEdit/QPlainTextEdit/QAbstractSpinBox/QComboBox` — 用户正在输入

**为何不抽取公共函数：**
- 两处守卫的语义略有不同：Space 是快捷键（通过 `QShortcut` 触发），双击是鼠标事件（通过信号触发），但排除条件完全相同
- 如果未来需要调整排除条件（如新增控件类型），两处应同步修改。抽取公共函数 `_is_playback_shortcut_allowed()` 是可选的后续重构，但当前两处守卫仅 5 行代码，抽取反而增加跳转层次
- **折中**：本次实现中保持内联，在注释中标注"与 `_on_space_shortcut` 同步维护"。如果后续出现第三处相同检查，再抽取公共方法

### 决策 4：`mouseDoubleClickEvent` 中 zoom 轨道判断优先于空白区域判断

**做法：**
```python
if ti >= 0 and self._tracks[ti].type == "zoom":
    # zoom 双击（现有逻辑）
elif ci < 0 and pos.y() >= RULER_HEIGHT:
    # 空白区域双击（新增逻辑）
```

**理由：**
- zoom 轨道双击有独立语义（创建/选中缩放块），必须不被空白区域逻辑覆盖
- `if/elif` 保证互斥：zoom 判断优先，空白区域为 fallback
- 即使用户在 zoom 轨道的空白区域双击（无 clip），也不会触发播放——这符合设计意图：zoom 轨道的交互应由 zoom 相关逻辑完全接管

## 理由

1. **先判断后执行**比**先执行后回滚**在可读性和正确性上更优。`_playhead_s` 的写入和 `playhead_changed` 的发射应在确认"需要移动"之后进行，而非先做再撤销。
2. **独立信号**保持了 `TimelineWidget` 作为纯 UI 组件的边界——它只关心"用户双击了空白区域"这一事实，不关心"谁来响应"和"如何响应"。播放状态管理是 `MainWindow` 的职责。
3. **复用焦点排除模式**确保所有播放触发入口（Space 键、双击空白区域）的行为一致，避免"按 Space 不播放但双击播放"的矛盾体验。
4. **最小变更**：本次不创建新的命令类（`MoveClipCommand` 已足够）、不修改数据模型（`Clip`/`Track` 不变）、不新增模块。所有变更集中在 `timeline.py` 的事件分发和 `main_window.py` 的信号连接。

## 备选方案

### 在 `MainWindow` 中通过 `eventFilter` 捕获双击事件

拒绝。`eventFilter` 需要在父级（`QScrollArea` 或 `MainWindow`）安装，且需要将 widget 坐标转换到时间线坐标系。侵入性强，违反"事件在目标 widget 内处理"的 Qt 惯例。

### 用 `playhead_changed` + 时间窗口判断是否为双击

拒绝。在 `_on_timeline_seek` 中记录上次调用时间，若两次调用间隔 < `QApplication.doubleClickInterval()` 则触发播放。这种方式将播放逻辑与 seek 逻辑混在一起，且依赖隐式的时间窗口，不可靠（用户快速连续单击空白区域也会触发）。

### 抽取 `_is_playback_shortcut_allowed()` 公共方法

接受作为后续重构。两次检查当前只有 5 行重复，抽取为方法后调用方需要额外跳转阅读。当出现第三次相同检查时（如 JKL 穿梭控制），抽取的价值大于成本。
