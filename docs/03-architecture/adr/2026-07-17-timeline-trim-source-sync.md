# ADR: 时间线边缘拖拽 source 同步与宏命令

**日期:** 2026-07-17
**状态:** Accepted

## 背景

Recordly 的 `TimelineWidget` 已支持 clip 边缘拖拽（`resize_left`/`resize_right`），但 `mouseMoveEvent` 仅更新 `clip.start`/`clip.end`，不同步更新 `clip.source_start`/`clip.source_end`。对于拆分后的 clip（具有显式 `source_end`），音频导出时 `exporter.py:616-618` 使用的 atrim source 范围仍是拆分时的旧值，导致音画长度不匹配。

同时，需要新增"播放头一键裁剪"功能，要求在单个 undo 步内完成裁剪操作。

## 决策

### 决策 1：resize 时 source 更新公式

**采用以下公式**（与 `SplitClipCommand:100` 保持一致）：

```
new_source_start = old_source_start + (new_timeline_start - old_timeline_start) × speed
new_source_end   = old_source_end   + (new_timeline_end   - old_timeline_end)   × speed  (仅当 source_end ≠ None)
```

核心原则：**timeline 位置与 source 位置的映射关系保持不变**，即 `source_pos = source_start + (timeline_pos - start) × speed`。

当用户拖拽左边缘使之右移 Δt 时，原本在 Δt 处读取的 source 内容现在成为 clip 的新起点，故 `source_start` 需前移 `Δt × speed` 个单位。

### 决策 2：一键裁剪使用 CompositeCommand 组合 Split + Delete

**采用方案 B：`CompositeCommand` 包装 `SplitClipCommand` + `DeleteClipCommand`。**

创建通用 `CompositeCommand` 宏命令类，将多个子命令封装为单个可撤销单元。`trim_in`/`trim_out` 方法内部组合 Split + Delete 子命令。

### 决策 3：source 字段纳入 MoveClipCommand 管理

**将 `old_source_start`、`new_source_start`、`old_source_end`、`new_source_end` 作为可选字段加入 `MoveClipCommand`。**

不创建单独的 `ResizeClipCommand`。resize 本质上是 start/end 变化的特例，与 move 共享 undo/redo 模式。新增 source 字段带默认值（`0.0`/`None`），兼容纯 move 操作（source 字段不变）。

## 理由

### 决策 1 理由

- **一致性**：`SplitClipCommand:100` 已使用 `source_start + (time - start) × speed` 计算拆分点对应的 source 位置。resize 本质上是"将 clip 边缘移到新位置"，应使用相同的换算公式，避免拆分后 resize 出现 source 错位。
- **正确性**：对于 speed=2.0 的 clip，时间线上缩短 1 秒意味着跳过了 2 秒的 source 内容，`source_start` 应前移 2 秒。仅移动 1 秒（选项 B）会导致音频与画面时间不同步。
- **增量 vs 绝对**：使用基于 `_drag_orig_source_start` 的绝对计算而非每帧增量累加，避免浮点误差累积。

### 决策 2 理由

- **DRY**：`SplitClipCommand` 和 `DeleteClipCommand` 已经过测试和验证，不重复实现相同逻辑。
- **可组合性**：`CompositeCommand` 是通用工具，未来 Ripple Delete、批量删除等复合操作可直接复用。
- **撤销语义正确**：一次 Ctrl+Z 恢复整个裁剪操作，而非要求用户按两次撤销。

### 决策 3 理由

- **变更最小化**：不引入新的命令类型，复用现有 undo/redo 管道
- **向后兼容**：所有字段有默认值，旧版 project.json 加载不受影响

## 备选方案

### 决策 1 备选

| 方案 | 描述 | 拒绝理由 |
|------|------|---------|
| B: 不更新 source_start | 仅改变 timeline 位置，source 不变 | 导出时 atrim 范围与视觉不一致，这是当前 bug 的根源 |
| 反向换算: `source_start -= dt / speed` | 把速度倒数作为系数 | 与 SplitClipCommand 公式不一致，且语义错误（speed>1 时 timeline 移动对应更大的 source 范围） |

### 决策 2 备选

| 方案 | 描述 | 拒绝理由 |
|------|------|---------|
| A: 创建独立 `TrimClipCommand` | 直接在 command 中修改 start/end + source | 重复实现 SplitClipCommand 的 source 计算逻辑；需要处理 playhead 在 clip 外等边界情况，增加维护面 |
| 分两步 push Split + Delete | 不用 Composite，让用户 undo 两次 | 违反"一次撤销恢复整个裁剪"的需求 |

## 影响

### 代码变更

- `core/commands.py`:
  - `MoveClipCommand` 新增 4 个 source 字段
  - 新增 `CompositeCommand`
- `ui/timeline.py`:
  - `__init__` 新增 `_drag_orig_source_start` / `_drag_orig_source_end`
  - `mousePressEvent` 捕获 source 原始值
  - `mouseMoveEvent` resize 分支更新 source 字段
  - `mouseMoveEvent` 非拖拽分支新增边缘 hover 光标
  - `_make_move_cmd` 捕获 source 变更
  - 新增 `trim_in()` / `trim_out()` 方法
  - `keyPressEvent` 绑定 I/O 键

### 后续设计约束

- 任何新增的命令如果修改了 clip 的时间范围，也必须处理 source 字段
- `CompositeCommand` 的子命令之间不能有隐式索引依赖（如 split 后 delete 右半片依赖 `clip_index + 1`），需要在组合时显式计算索引
