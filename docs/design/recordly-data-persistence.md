# 技术方案: 录制数据持久化与编辑器工具栏精简

**日期:** 2026-07-15
**状态:** Draft

## 1. 技术栈

| 层级 | 技术选型 | 理由 |
|------|---------|------|
| 数据持久化 | JSON (dataclass + asdict) | 沿用现有 Project 序列化方案 |
| 数据转换 | numpy → list | cursor_events 等 numpy 数据转 Python 原生类型 |

## 2. 架构设计

### 2.1 数据流

```
录制完成
  │
  ▼
compositor 状态（cursor_events, click_events, camera, timeline, ...）
  │
  ▼
MainWindow._collect_project_state(project)  ← 新增方法
  │  写入 project.timeline, project.crop_region, project.audio_regions
  │  写入 project._cursor_events (新字段), project._click_events (新字段)
  │  写入 project._monitor_offset (新字段)
  ▼
project.save(proj_file)  ← 已有
```

### 2.2 模块修改

| 模块 | 改动 | 说明 |
|------|------|------|
| `core/project.py` | 新增字段 | cursor_events, click_events, monitor_offset |
| `app/main_window.py` | 新增方法 + 修改 | _collect_project_state, 重写 _on_save_project, 改 _auto_create_project, _on_open_project |
| `app/main_window.py` | 工具栏 | 删除录制/停止按钮 |

## 3. 数据模型变更

### 3.1 Project 新增字段

```python
@dataclass
class Project:
    # ... 现有字段不变 ...
    
    # 新增：录制原始数据
    cursor_events: list[list[float]] = field(default_factory=list)
    click_events: list[list[float]] = field(default_factory=list)
    monitor_offset: list[int] = field(default_factory=lambda: [0, 0])
```

保存时序列化为 JSON 数组。

### 3.2 数据精简策略

cursor_events 可能包含数千条记录（60fps × N秒），全部保存会膨胀 project.json。采用**采样策略**：
- 保存时每 N 帧取 1 个点（如每 3 帧）
- 加载时插值还原

## 4. 关键方法设计

### 4.1 _collect_project_state

```python
def _collect_project_state(self, project: Project) -> None:
    """将当前 compositor 和编辑器状态收集到 Project 对象"""
    comp = self._compositor
    
    # 录制原始数据
    project.cursor_events = [[c.x, c.y, c.t] for c in comp._cursor_events]
    project.click_events = [[c[0], c[1], c[2]] for c in comp._click_events]
    project.monitor_offset = [comp._monitor_left, comp._monitor_top]
    
    # 编辑状态
    project.timeline = self._timeline.to_tracks()
    project.crop_region = comp._crop_region
    project.audio_regions = self._audio_regions[:]
```

### 4.2 _on_save_project（重写）

```python
def _on_save_project(self):
    """保存当前项目"""
    project = self._project_manager.load_project(self._current_project_path)
    self._collect_project_state(project)
    project.save(self._current_project_path)
    self.update_status("✓ 项目已保存")
```

### 4.3 _auto_create_project 修改

```python
# 创建项目后立即收集 compositor 状态
self._collect_project_state(project)
# project.save 已在 create_project 内部调用 → 需改为在 _collect 之后 save
```

### 4.4 _on_open_project 增强

```python
# 恢复 cursor_events
comp._cursor_events = project.cursor_events
comp._click_events = project.click_events
comp.set_monitor_offset(*project.monitor_offset)
# 重建 camera（如有 auto zoom clips）
if project.timeline has zoom track:
    comp.load_manual_zoom_clips(...)
```

## 5. 关键决策

| 决策 | 方案 | 理由 |
|------|------|------|
| 数据格式 | 纯 JSON（list[list]） | 可读性好，兼容性高，无需额外依赖 |
| cursor_events 存储 | 直接存到 Project 字段 | 数据量不大（数千条 × ~40B ≈ 几百KB），可接受 |
| 保存触发 | 录完自动保存 + 手动保存 | 不引入 autosave，保持简单 |
| 向后兼容 | 旧 project.json 缺少新字段 → 默认空列表 | 不破坏已有项目 |

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| cursor_events 过多导致 project.json 过大 | 采样（每 3 帧一存），后续可按需调整 |
| numpy 类型序列化失败 | `asdict` 前转为 Python 原生类型（int/float/list） |
| 旧版 project.json 加载无新字段 | `data.get("cursor_events", [])` 提供默认值 |

## 7. DAG 任务拆解

### Batch 1（可并行）
- T1: toolbar-cleanup — 编辑器工具栏移除录制/停止按钮
- T2: project-model — Project 模型新增 cursor_events/click_events/monitor_offset 字段

### Batch 2（依赖 T1, T2）
- T3: data-persistence — 实现 _collect_project_state / _on_save_project / _auto_create_project / _on_open_project 完整保存恢复链路
