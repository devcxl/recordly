# 开发文档: T13 — MainWindow 缩减与私有字段访问消除

- **Project:** Recordly 核心稳定性与架构治理
- **Task ID:** T13
- **Slug:** `main-window-slim-down`
- **Issue:** #40
- **类型:** refactor
- **Batch:** B8
- **依赖:** T11 (#38), T12 (#39)
- **预计工时:** 3h
- **涉及文件:** 2

---

## 1. 目标

将 `app/main_window.py` 从当前 **1245 行** 缩减到 **≤800 行**，并消除 MainWindow 中所有跨模块私有字段直接访问。

**前置条件（T11/T12 已完成）：**
- `RecordingController` 已提取，`start()`/`stop()`/`set_callbacks()` 可用
- `ExportController` 已提取，`start_export()`/`cancel()`/`export_finished` 信号可用
- `ProjectSession` 已引入，`project_dir`/`save()`/`save_audio()`/`load_audio()`/`normalize_path()` 可用
- MainWindow 中录制入口和导出入口已通过 Controller 调用（渐进引入阶段）

**注意：** 本任务是渐进式重构的收尾阶段。T10-T12 已逐步将 MainWindow 中的逻辑委托给 Controller，并在 MainWindow 中建立了兼容层。本任务清理残留的兼容层代码和私有字段直接访问。

---

## 2. 实施步骤（Red → Green → Refactor）

### 步骤 1: 审计当前私有字段访问（Red — 基线测量）

**目标:** 确认 15 处私有字段访问的位置。

**操作:**
```bash
# 统计当前行数
wc -l app/main_window.py

# 列出所有跨模块私有字段访问
grep -n '_recorder\.screen\._store\._offsets\|_compositor\._frames\|_compositor\._cursor_events\|_compositor\._click_events\|_compositor\._clips\|_timeline\._tracks\|_playback\._playing\|_playback\._current_frame' app/main_window.py
```

**当前状态（已验证）:**
| 行号 | 访问内容 | 所属上下文 |
|------|---------|-----------|
| 506 | `self._compositor._frames` 取 len | 帧计数器更新 |
| 543 | `self._recorder.screen._store._offsets` | 帧存储偏移量 |
| 571 | `self._compositor._frames` | 帧复制 |
| 637 | `self._compositor._frames` / `self._compositor.fps` | 时长计算 |
| 661 | `self._compositor._frames` 判空 | 导出前置检查 |
| 669-670 | `self._playback._playing` / `_current_frame` | 播放状态 |
| 847 | `self._compositor._frames` 判空 | 保存检查 |
| 877 | `self._compositor._frames` 判空 | 录制数据检查 |
| 1033-1034 | `self._timeline._tracks` 过滤 | 音频轨道 |
| 1055 | `self._timeline._tracks.append` | 音轨添加 |
| 1070-1073 | `_compositor._frames/_cursor_events/_click_events` 赋值 | 项目加载 |

**验证:** 记录当前行数 `1245` 为基线。

---

### 步骤 2: 逐一消除私有字段访问（Green — 逐项修复）

#### 2a. 消除 `_compositor._frames` 访问（6 处）

| 行号 | 当前代码 | 替换方案 |
|------|---------|---------|
| 506 | `len(self._compositor._frames)` | `self._compositor.frame_count`（新增 public property） |
| 571 | `self._compositor._frames` | 通过 `_project_session.save()` 传入（已被 T10 覆盖，检查是否已迁移） |
| 637 | `len(self._compositor._frames) / self._compositor.fps` | `self._compositor.duration`（新增 public property） |
| 661 | `not self._compositor._frames` | `self._compositor.frame_count == 0` |
| 847 | `not self._compositor._frames` | `self._compositor.frame_count == 0` |
| 877 | `not self._compositor._frames` | `self._compositor.frame_count == 0` |
| 1070 | `self._compositor._frames = []` | 检查 T10 是否已通过 `_project_session` 加载替代；如未完成，添加 `_compositor.clear_frames()` |
| 1072-1073 | `.` | 同上，检查是否需要 `_compositor.clear_cursor_events()` / `_compositor.clear_click_events()` |

**实现（在 `core/compositor.py` 中新增，≤10 行）：**

```python
# core/compositor.py — Compositor 类新增
@property
def frame_count(self) -> int:
    return len(self._frames)

@property
def duration(self) -> float:
    if not self._frames:
        return 0.0
    return len(self._frames) / self.fps

def clear_frames(self) -> None:
    self._frames = []
    self._cursor_events = []
    self._click_events = []
```

**关联影响（`app/main_window.py`）：** 将私有字段访问替换为 public property 调用。此变更不引入新依赖，不改业务逻辑。

> **注意：** T10 引入 `ProjectSession` 后，行 571（帧复制到 session.save）和行 1070-1073（项目加载清空）可能已通过 `ProjectSession` 间接处理。先检查 T10/T11 产物状态，仅修复仍遗留的直接访问。

#### 2b. 消除 `_recorder.screen._store._offsets` 访问（1 处）

行 543: `offsets = self._recorder.screen._store._offsets`

**替换方案:** 在 `_CompressedFrameStore`（或 `ScreenCapture`）中暴露 public property。

**实现（`core/screen_capture.py` — `ScreenCapture` 或 `_CompressedFrameStore` 类新增）：**

```python
# 在 ScreenCapture 中暴露 offsets（如果 screen 已暴露为 public）
@property
def frame_offsets(self) -> list[int]:
    """帧数据文件中的字节偏移量"""
    return self._store._offsets
```

MainWindow 中替换为:
```python
offsets = self._recorder.screen.frame_offsets
```

#### 2c. 消除 `_playback._playing` / `_playback._current_frame` 访问（1 处）

行 669-670:
```python
elif not self._playback._playing:
    self._playback.play(self._playback._current_frame)
```

**替换方案:** 在 `PlaybackController`（`ui/preview_widget.py`）暴露 `is_playing` property 和 `resume()` 方法。

> **注意:** 在实施前检查 `PlaybackController` 的实际 public API。如果 `play()` 方法内部已处理 `_playing` 和 `_current_frame` 的默认行为，可直接调用 `self._playback.play()` 无参数。

**实现:**

```python
# ui/preview_widget.py — PlaybackController 类新增
@property
def is_playing(self) -> bool:
    return self._playing

def resume(self) -> None:
    """从当前帧恢复播放"""
    self.play(self._current_frame)
```

MainWindow 中替换为:
```python
elif not self._playback.is_playing:
    self._playback.resume()
```

#### 2d. 消除 `_timeline._tracks` 访问（2 处）

行 1033-1034:
```python
self._timeline._tracks = [t for t in self._timeline._tracks if t.type != "audio_extra"]
```

行 1055:
```python
self._timeline._tracks.append(track)
```

**替换方案:** 在 `Timeline`（`ui/timeline.py`）暴露 `remove_track_by_type()` 和 `add_track()` 方法。

> **注意:** 在实施前确认 `Timeline` 类的实际路径和已有 public API。如果已有 `add_track` 方法，只需添加 `remove_tracks_by_type`。

**实现:**

```python
# ui/timeline.py — Timeline 类新增（≤10 行）
def remove_tracks_by_type(self, track_type: str) -> None:
    """移除所有指定类型的轨道"""
    self._tracks = [t for t in self._tracks if t.type != track_type]

def add_track(self, track) -> None:
    """添加轨道"""
    self._tracks.append(track)
```

---

### 步骤 3: 清理已迁移代码的残留（Refactor — 删除死代码）

**目标:** 删除 T10-T12 渐进引入阶段保留的兼容层和死代码。

检查以下内容是否已在 T10-T12 中被迁移并只保留兼容层:
- `_current_project_path` 直接赋值/读取 → 应通过 `self._project_session.project_dir`
- `_auto_create_project` 方法 → 应通过 `RecordingController`
- `_finalize_project` 方法 → 应通过 `ProjectSession.save()`
- `_cancel_export` 方法 → 应通过 `ExportController.cancel()`
- `_on_export_finished` 中线程清理代码 → 应通过 `ExportController.export_finished` 信号
- QThread 创建/绑定代码 → 已在 `ExportController` 中

**操作流程:**
1. 逐方法确认已委托给 Controller
2. 删除 MainWindow 中冗余方法体（保留方法声明仅 delegate）
3. 删除不再需要的 import（如 `QThread` 相关，如果 ExportController 完全接管）

**预计可删除行数:** 150-250 行（取决于 T10-T12 的渐进程度）

---

### 步骤 4: 验证（Green — 回归测试）

**验证命令:**
```bash
# 1. 行数检查
wc -l app/main_window.py

# 2. 私有字段访问清零检查
grep -n '_recorder\.screen\._store\._offsets\|_compositor\._frames[^_]' app/main_window.py  # 排除 frame_count/duration property 定义
grep -n '_compositor\._cursor_events\|_compositor\._click_events' app/main_window.py
grep -n '_timeline\._tracks' app/main_window.py
grep -n '_playback\._playing\|_playback\._current_frame' app/main_window.py

# 3. 全量测试
pytest tests/test_main_window.py -q
pytest -q
```

**预期结果:**
- `wc -l` ≤ 800
- 所有 grep 返回空（0 matches）
- `pytest` 全量通过

---

## 3. 接口/契约

### MainWindow 内部契约变更

| 旧访问方式 | 新访问方式 | 变更类型 |
|-----------|-----------|---------|
| `self._compositor._frames` 读 | `self._compositor.frame_count` / `.duration` | property 替代 |
| `self._compositor._frames = []` | `self._compositor.clear_frames()` | 方法替代 |
| `self._recorder.screen._store._offsets` | `self._recorder.screen.frame_offsets` | property 替代 |
| `self._playback._playing` | `self._playback.is_playing` | property 替代 |
| `self._playback._current_frame` | `self._playback.resume()` | 方法替代 |
| `self._timeline._tracks` 过滤 | `self._timeline.remove_tracks_by_type("audio_extra")` | 方法替代 |
| `self._timeline._tracks.append(x)` | `self._timeline.add_track(x)` | 方法替代 |

### Compositor 新增 API（`core/compositor.py`）

```python
@property
def frame_count(self) -> int: ...
@property
def duration(self) -> float: ...
def clear_frames(self) -> None: ...
```

### ScreenCapture 新增 API（`core/screen_capture.py`）

```python
@property
def frame_offsets(self) -> list[int]: ...
```

### PlaybackController 新增 API（`ui/preview_widget.py`）

```python
@property
def is_playing(self) -> bool: ...
def resume(self) -> None: ...
```

### Timeline 新增 API（`ui/timeline.py`）

```python
def remove_tracks_by_type(self, track_type: str) -> None: ...
def add_track(self, track) -> None: ...
```

---

## 4. 单元/集成测试指引

### 需要新增的测试

**`tests/test_main_window.py`:**
- `test_frame_count_property_used`: 验证 `_on_update_frame_counter` 使用 `compositor.frame_count` 而非 `_compositor._frames`
- `test_no_private_field_access`: 对 MainWindow 源码做静态 grep 检查（可在测试中通过 `inspect.getsource` 实现）
- `test_main_window_line_count`: `assert len(source_lines) <= 800`

**`tests/test_compositor.py`:**
- `test_frame_count_property`: frame_count == len(_frames)
- `test_duration_property`: 验证 0 帧返回 0.0，N 帧返回正确时长
- `test_clear_frames`: 验证清空 _frames/_cursor_events/_click_events

**`tests/test_screen_capture.py`:**
- `test_frame_offsets_property`: 验证 offsets 可读

### 需要更新的现有测试

- `tests/test_main_window.py`：如果现有测试直接 mock `_compositor._frames`，需要更新为 mock `compositor.frame_count` property

---

## 5. 完整验收标准

- [ ] `wc -l app/main_window.py` ≤ 800 行
- [ ] `grep -n '_recorder\.screen\._store\._offsets' app/main_window.py` 返回空
- [ ] `grep -n '_compositor\._frames' app/main_window.py` 返回空（不含新增的 property 定义行）
- [ ] `grep -n '_compositor\._cursor_events' app/main_window.py` 返回空
- [ ] `grep -n '_compositor\._click_events' app/main_window.py` 返回空
- [ ] `grep -n '_timeline\._tracks' app/main_window.py` 返回空
- [ ] `grep -n '_playback\._playing' app/main_window.py` 返回空
- [ ] `grep -n '_playback\._current_frame' app/main_window.py` 返回空
- [ ] `pytest tests/test_main_window.py -q` 全部通过
- [ ] `pytest -q` 全量通过
- [ ] 不引入新依赖，不改业务行为

---

## 6. 边界情况和风险

### 边界情况

1. **Compositor 无帧时** `duration` 返回 `0.0` 而非除零错误
2. **`clear_frames()` 调用后** `frame_count == 0`，后续逻辑（如导出按钮启用/禁用状态）需正确响应
3. **`_timeline.remove_tracks_by_type()`** 空轨道列表时不抛异常
4. **PlaybackController** 可能不存在 `_playing` 属性（需验证：`play()` 方法被调用时内部状态）

### 风险

| 风险 | 缓解 |
|------|------|
| T10-T12 渐进引入不完整导致本任务被迫回填 T10/T11/T12 逻辑 | 步骤 3 前先完整检查 T10-T12 产物，如发现缺失，暂停并通知 T10/T11/T12 修复 |
| PlaybackController 的 public API 不足以消除私有访问 | 如果 `play()` 已处理内部状态，直接用 `play()` 替代 `play(_current_frame)` |
| MainWindow 的行数减少不到 800（T10-T12 残留过多） | 优先删除已委托的死代码；如仍超标，拆分 `_connect_signals` 等方法 |
| 其他模块测试因 property 替代而断裂 | 在 `conftest.py` 或测试中 mock 新 property 而非旧私有字段 |

---

## 7. 任务级验证命令

```bash
# 1. 行数验证
wc -l app/main_window.py | awk '{if ($1 <= 800) print "PASS: " $1 " lines"; else print "FAIL: " $1 " lines (target ≤ 800)"}'

# 2. 私有字段访问清零
! grep -nE '(\._frames|\._cursor_events|\._click_events|\._tracks|\._playing|\._current_frame|_store\._offsets)' app/main_window.py

# 3. 全量测试
.venv/bin/python -m pytest -q

# 4. MainWindow 专项测试
.venv/bin/python -m pytest tests/test_main_window.py -q
```

---

## 8. 技术方案参考

- 技术方案 §3.2.7: `app/main_window.py` 改动范围
- 技术方案 §2.3: 目标架构（MainWindow ≤800 行）
- ADR-007 §3: 三个 Controller 职责边界
- 任务图 T13: `main-window-slim-down` Batch B8
