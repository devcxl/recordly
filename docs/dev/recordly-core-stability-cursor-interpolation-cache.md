# 开发文档: T16 — 光标插值收敛与时间缓存

- **Project:** Recordly 核心稳定性与架构治理
- **Task ID:** T16
- **Slug:** `cursor-interpolation-cache`
- **Issue:** #43
- **类型:** perf
- **Batch:** B10
- **依赖:** T14 (#41)
- **预计工时:** 2h
- **涉及文件:** 4

---

## 1. 目标

统一光标插值实现并缓存时间索引，消除重复的线性扫描版本。覆盖 `core/compositor.py` 和 `core/camera.py` 两个模块。

**前置条件（T14 已完成）：**
- `logging` 模块已统一，`core/compositor.py` 中的 `__import__` 已替换为 `import time`
- `core/compositor.py` 已有 `logger` 实例

**关键约束：**
- 光标位置和相机缩放与之前完全一致（不引入行为变更）
- 使用 `bisect` 模块进行二分查找（Python 标准库，非新依赖）
- 缓存时间数组避免逐帧重复扫描

---

## 2. 当前状态审计

### `core/compositor.py` — 两套光标插值实现

#### 实现 A: `_interpolate_cursor()`（二分查找，行 220）

```python
def _interpolate_cursor(self, ts: float) -> tuple[int, int]:
    """..."""
    if not self._cursor_events:
        return (0, 0)
    starts = [ev[0] for ev in self._cursor_events]  # ← 每次调用重新构建 starts
    i = bisect.bisect_right(starts, ts) - 1
    ...
```

**问题:** 每次调用都重建 `starts` 列表（O(n) 扫描）。已有 `bisect` 二分查找，但缺少时间缓存。

#### 实现 B: `_interpolate_cursor_raw()`（线性扫描，行 249）

```python
def _interpolate_cursor_raw(self, rel_ts: float) -> tuple[int, int]:
    """..."""
    best_match = (0, 0)
    timestamp = 0.0
    for ev in self._cursor_events:  # ← 线性 O(n) 扫描
        ...
```

**问题:** 与 `_interpolate_cursor` 逻辑重复但使用线性扫描。应统一到一个二分实现。

#### 帧时间缓存: `_frame_times` 已存在（行 56）

```python
self._frame_times: list[float] = []
```

`load_frames_data()` 中已构建 `_frame_times`（行 68），但未被 `_interpolate_cursor` 利用。

---

### `core/camera.py` — 线性扫描插值

#### `_interpolate()`（行 59）

```python
def _interpolate(self, ts: float) -> tuple[float, float]:
    """..."""
    if not self.events:
        return self._prev_pos
    # 线性扫描找 timestamp <= ts 的最近事件
    best = self.events[0]
    p_prev = self.events[0]
    for event in self.events:  # ← 线性 O(n) 扫描
        ...
```

**问题:** 每次调用的 O(n) 线性扫描。应用 `bisect` + 预计算时间数组替代。

#### `_calc_speed()`（行 80）

```python
def _calc_speed(self, ts: float) -> float:
    t0 = max(ts - 0.05, 0)
    t1 = ts
    if not self.events:
        return 1.0  # ← 注意：Camera 的 events 是 list，不是 list of tuples
    p0 = self._interpolate(t0)
    p1 = self._interpolate(t1)
    ...
```

**问题:** 每次调用两次 `_interpolate()`（各做 O(n) 扫描）。

#### `events` 结构

```python
# Camera.events: list[tuple[float, float, float]]  # (timestamp, x, y) 或类似
# 需要在 camera.py 中确认 events 的具体结构
```

---

## 3. 实施步骤（Red → Green → Refactor）

### 步骤 1: `core/compositor.py` — 光标准一 + 时间缓存（Green）

#### 1a. 预计算 `_cursor_start_times` 缓存

**当前（行 68）:**
```python
self._frame_times = [...]
```

**在该行之后新增:**
```python
self._cursor_start_times: list[float] = []
```

在 `load_frames_data()` 加载 cursor_events 之后（行 68 附近）预计算:
```python
self._cursor_start_times = [ev[0] for ev in self._cursor_events]
```

在 `clear_frames()`（T13 新增的 `clear_frames()` 方法）中同时清空:
```python
self._cursor_start_times = []
```

#### 1b. 重写 `_interpolate_cursor_raw()` 复用 `_interpolate_cursor()`

**分析两个方法的调用者:**

通过 grep 确认 `_interpolate_cursor_raw` 的调用者:
```bash
grep -n "_interpolate_cursor_raw" core/compositor.py
```

确认调用者后，将 `_interpolate_cursor_raw` 改为委托 `_interpolate_cursor`:

```python
def _interpolate_cursor_raw(self, rel_ts: float) -> tuple[int, int]:
    """已废弃：委托 _interpolate_cursor 统一实现。
    
    保留此方法以维持向后兼容（如外部调用），内部逻辑与 _interpolate_cursor 一致。
    """
    return self._interpolate_cursor(rel_ts)
```

> **注意:** 如果 `_interpolate_cursor_raw` 的语义与 `_interpolate_cursor` 不同
> （如 ts 含义不同），需先验证。如有语义差异，在 `_interpolate_cursor_raw` 中
> 做参数转换后委托 `_interpolate_cursor`。

#### 1c. 优化 `_interpolate_cursor()` — 使用缓存的 `_cursor_start_times`

**当前（行 220-233）:**
```python
def _interpolate_cursor(self, ts: float) -> tuple[int, int]:
    if not self._cursor_events:
        return (0, 0)
    starts = [ev[0] for ev in self._cursor_events]  # ← 每次重建
    i = bisect.bisect_right(starts, ts) - 1
    ...
```

**替换为:**
```python
def _interpolate_cursor(self, ts: float) -> tuple[int, int]:
    if not self._cursor_start_times:
        return (0, 0)
    i = bisect.bisect_right(self._cursor_start_times, ts) - 1
    if i < 0:
        return self._cursor_events[0][1], self._cursor_events[0][2]
    return self._cursor_events[i][1], self._cursor_events[i][2]
```

**变更:**
- 移除 `starts` 列表重建（O(n) → O(log n) 纯二分）
- 使用缓存的 `self._cursor_start_times`
- 空事件判断改为检查 `self._cursor_start_times`（更高效）

#### 1d. 删除 `_interpolate_cursor_raw` 的线性扫描实现

如果步骤 1b 确认后 `_interpolate_cursor_raw` 无独立语义，直接删除该方法，其调用者改为调用 `_interpolate_cursor`。

---

### 步骤 2: `core/camera.py` — bisect + 时间缓存（Green）

#### 2a. 确认 Camera.events 的数据结构

先阅读 `core/camera.py` 以确认 `self.events` 的类型:
```bash
grep -n "events" core/camera.py | head -20
```

假设 `self.events` 是 `list[tuple[float, float, float]]`（timestamp, x, y），预计算时间索引。

#### 2b. 在 Camera 类中添加 `_event_times` 缓存

```python
class Camera:
    def __init__(self, ...):
        ...
        self.events: list[tuple[float, float, float]] = []  # 假设结构
        self._event_times: list[float] = []  # 新增：预计算时间索引
        ...
```

在 events 设置/更新的地方同步更新 `_event_times`:
```python
def set_events(self, events):
    self.events = events
    self._event_times = [ev[0] for ev in events]  # 同步缓存
```

#### 2c. 重写 `_interpolate()` — 使用 bisect + _event_times

**当前（线性扫描）:**
```python
def _interpolate(self, ts: float) -> tuple[float, float]:
    if not self.events:
        return self._prev_pos
    best = self.events[0]
    for event in self.events:  # O(n) 扫描
        if event[0] <= ts:
            best = event
        else:
            break
    return (best[1], best[2])
```

**替换为:**
```python
import bisect

def _interpolate(self, ts: float) -> tuple[float, float]:
    """二分查找时间戳 <= ts 的最近光标事件。"""
    if not self._event_times:
        return self._prev_pos
    i = bisect.bisect_right(self._event_times, ts) - 1
    if i < 0:
        # 所有事件时间戳 > ts，返回第一个事件
        ev = self.events[0]
        return (ev[1], ev[2])
    ev = self.events[i]
    return (ev[1], ev[2])
```

**变更:**
- 线性扫描 O(n) → 二分查找 O(log n)
- 使用预计算的 `self._event_times`
- 行为保持一致：`bisect_right - 1` 找到最后一个 `<= ts` 的事件（与原逻辑等价）

#### 2d. 优化 `_calc_speed()` — 复用缓存的 _event_times

`_calc_speed()` 内部调用 `_interpolate(t0)` 和 `_interpolate(t1)`，两者都受益于二分查找。不需要额外修改 `_calc_speed()` 本身。

但确认 `_calc_speed()` 返回 `1.0` 的早期返回:
```python
if not self.events:
    return 1.0
```
改为:
```python
if not self._event_times:
    return 1.0
```

（逻辑等价，但使用缓存字段更高效）

---

### 步骤 3: 文件顶部添加 `import bisect`（如缺失）

检查 `core/camera.py` 顶部是否已有 `import bisect`:
```bash
grep "import bisect" core/camera.py
```

如无，添加:
```python
import bisect
```

`core/compositor.py` 已确认有 `import bisect`（行 3）。

---

### 步骤 4: 验证（Green — 行为一致性回归）

#### 4a. 全量测试
```bash
.venv/bin/python -m pytest tests/test_compositor.py -q
.venv/bin/python -m pytest tests/test_camera.py -q
```

#### 4b. 光标位置对比（可选）
```python
# 用已知数据集验证新旧实现输出一致
# 确认 _interpolate_cursor 和 _interpolate_cursor_raw 返回相同值（如果 raw 被保留）
```

#### 4c. 性能验证（可选）
```python
import timeit

# 对比优化前后的 _interpolate_cursor 耗时
# 预期优化后针对 1000+ 事件列表有明显加速
```

---

## 5. 接口/契约

### Compositor 变更

| 方法 | 变更 | 复杂度 |
|------|------|--------|
| `_interpolate_cursor(ts)` | 使用 `self._cursor_start_times` 缓存，O(log n) | 行为不变 |
| `_interpolate_cursor_raw(ts)` | 委托 `_interpolate_cursor` 或删除 | 行为不变（如保留委托） |
| `load_frames_data()` | 新增 `self._cursor_start_times` 预计算 | 新增副作用 |
| `clear_frames()` (T13 新增) | 清空 `_cursor_start_times` | 新增 |

### Camera 变更

| 方法 | 变更 | 复杂度 |
|------|------|--------|
| `_interpolate(ts)` | O(log n) bisect 替代 O(n) 线性扫描 | 行为不变 |
| `_calc_speed(ts)` | 使用 `self._event_times` > 0 判空 | 行为不变 |
| `set_events(events)` | 同步更新 `self._event_times` | 新增副作用 |

### 新增属性

- `Compositor._cursor_start_times: list[float]` — 光标事件的时间戳数组（缓存）
- `Camera._event_times: list[float]` — 相机事件的时间戳数组（缓存）

---

## 6. 单元/集成测试指引

### 需要新增的测试

**`tests/test_compositor.py`:**
```python
def test_interpolate_cursor_empty_events():
    """空事件列表时返回 (0, 0)"""
    ...

def test_interpolate_cursor_single_event():
    """单个事件时返回该事件的坐标"""
    ...

def test_interpolate_cursor_before_first():
    """ts 在所有事件之前时返回第一个事件的坐标"""
    ...

def test_interpolate_cursor_after_last():
    """ts 在所有事件之后时返回最后一个事件的坐标"""
    ...

def test_interpolate_cursor_match_previous_implementation():
    """二分版本与线性扫描版本输出一致"""
    import random
    events = [(random.random() * 100, random.randint(0, 1920), random.randint(0, 1080)) for _ in range(1000)]
    events.sort()
    for ts in [random.random() * 100 for _ in range(100)]:
        assert old_impl(events, ts) == new_impl(events, ts)
```

**`tests/test_camera.py`:**
```python
def test_interpolate_with_bisect():
    """验证 bisect 版本的 _interpolate 与原线性扫描输出一致"""
    ...

def test_interpolate_empty_events():
    """空事件时返回 _prev_pos"""
    ...

def test_event_times_cached():
    """验证 _event_times 与 events 同步更新"""
    ...
```

### 需要更新的现有测试

- 现有测试如果直接设置了 `compositor._cursor_events` 的值，在步骤 1a 后需要同时设置 `compositor._cursor_start_times`（或 mock `load_frames_data()` 来设置两者）
- 现有测试如果通过 `compositor._cursor_events = [...]` 设置，改为使用 `compositor.load_frames_data()` 或同时设置 `_cursor_start_times`

---

## 7. 完整验收标准

- [ ] `_interpolate_cursor_raw()` 使用二分查找（与 `_interpolate_cursor()` 逻辑一致）或已删除
- [ ] `_interpolate_cursor()` 使用缓存的 `_cursor_start_times`，不再每调用重建 starts 列表
- [ ] `camera._interpolate()` 使用 `bisect` + 预计算的 `_event_times` 数组
- [ ] `camera._calc_speed()` 使用 `_event_times` 判空
- [ ] `pytest tests/test_compositor.py -q` 全部通过
- [ ] `pytest tests/test_camera.py -q` 全部通过
- [ ] `pytest -q` 全量通过
- [ ] 光标位置和相机缩放与之前完全一致（不引入行为变更）
- [ ] 无新增依赖（仅使用 Python 标准库 `bisect`）
- [ ] `clear_frames()`（T13 新增的方法）同步清空 `_cursor_start_times`

---

## 8. 边界情况和风险

### 边界情况

1. **空事件列表** → `_interpolate_cursor` 返回 `(0, 0)`，`_interpolate` 返回 `_prev_pos`
2. **单个事件** → `bisect_right` 后 `i=0`，返回第一个事件坐标
3. **ts < 第一个事件时间** → `bisect_right` 返回 0，`i=-1`，fallback 返回第一个事件
4. **ts > 最后一个事件时间** → `bisect_right` 返回 `len - 1`（注意 `-1` 后是最后一个）
5. **events 更新但 `_event_times` 未刷新** → 使用 `set_events()` 方法统一设置入口
6. **`clear_frames()` 后 `_cursor_start_times` 为空** → 下次 `load_frames_data()` 重新填充

### 风险

| 风险 | 缓解 |
|------|------|
| `_interpolate_cursor_raw` 删除后影响其他模块的直接调用 | 步骤 1d 前 grep 全量搜索 `_interpolate_cursor_raw` 引用 |
| `Camera.events` 的数据结构与假设 `(timestamp, x, y)` 不同 | 步骤 2a 中先确认数据结构再编码 |
| 缓存与 events 不同步（events 直接赋值而不经过 set_events） | 全局搜索 `self.events =` 在 camera.py 中，确保所有赋值点同步更新 `_event_times` |
| `_cursor_start_times` 内存占用 | 10000 个浮点数约 80KB，可忽略 |

---

## 9. 任务级验证命令

```bash
# 1. bisect 使用确认
grep -n "bisect" core/compositor.py core/camera.py
# compositor.py 应至少有 2 处使用 bisect
# camera.py 应至少有 1 处使用 bisect

# 2. _cursor_start_times 缓存确认
grep -n "_cursor_start_times" core/compositor.py
# 应在 __init__、load_frames_data()、clear_frames() 中

# 3. _event_times 缓存确认
grep -n "_event_times" core/camera.py
# 应在 __init__、set_events()、_interpolate()、_calc_speed() 中

# 4. 线性扫描残留检查
grep -n "_interpolate_cursor_raw" core/compositor.py
# 如果保留委托版本：确认不是线性扫描
# 如果删除：确认无残留引用

# 5. 全量测试
.venv/bin/python -m pytest tests/test_compositor.py tests/test_camera.py -q
.venv/bin/python -m pytest -q

# 6. 行为一致性验证
.venv/bin/python -c "
from core.compositor import Compositor
# 构造测试数据验证新旧输出一致
print('PASS: 行为一致性')
"
```

---

## 10. 技术方案参考

- 技术方案 §3.2.4: `core/compositor.py` — 统一二分插值 + 缓存 `_frame_times`
- 技术方案 §3.2.5: `core/camera.py` — bisect + `_event_times` 缓存
- 任务图 T16: `cursor-interpolation-cache` Batch B10
- PRD F20
