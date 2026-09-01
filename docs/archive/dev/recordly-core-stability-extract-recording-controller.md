# T11: extract-recording-controller — 提取 RecordingController

**Project:** Recordly  
**Task ID:** T11  
**Slug:** extract-recording-controller  
**Issue:** #38  
**类型:** refactor  
**Batch:** B6  
**依赖:** T05 (#32), T10 (#37)

---

## 1. 目标

从 `MainWindow` 提取 `RecordingController`（ADR-007 §3.2，技术方案 §3.1.2），拥有录制生命周期状态机。所有录制入口（首页按钮、托盘菜单）通过 RecordingController 统一调度，复用 T05 建立的统一录制逻辑，内部使用 T10 的 `ProjectSession.create()` 创建项目目录。

---

## 2. 前置条件

- [x] T05 完成：录制入口已统一为单一方法，启动/停止失败恢复逻辑已就绪
- [x] T10 完成：`ProjectSession.create()` / `.load()` / `.save_audio()` 可用
- [x] `Recorder` 支持 `start_recording(project_dir)` 和 `stop_recording() → dict`

---

## 3. 当前状态

```
MainWindow 中录制相关方法:
├── _start_recording_from_home()        # 首页录制入口
├── _on_home_record()                   # 确认弹窗 → 最小化 → QTimer
├── _on_tray_record()                   # 托盘录制入口
├── _on_recording_started()             # 录制成功回调
├── _on_recording_error()               # （部分场景）错误回调
├── _finalize_project()                 # 录制完成 → 保存
├── _recorder.start_recording()         # 直接调用
├── _recorder.stop_recording()          # 直接调用
└── _switch_to_editor()                 # 录制后 UI 切换
```

这些问题导致：
- 首页录制通过 `QTimer.singleShot(500, ...)` 绕过 try/except
- 托盘录制可能覆盖已有项目
- 停止失败后窗口不恢复

---

## 4. Red → Green → Refactor 实施步骤

### 🔴 RED — 编写 RecordingController 单元测试

#### Step 1: `tests/test_recording_controller.py` — **新增文件**

```python
"""RecordingController 状态机单元测试 — 纯 Python，不依赖 Qt"""

class TestRecordingStateMachine:
    """状态转换: IDLE → STARTING → RECORDING → STOPPING → IDLE"""
    
    def test_initial_state_is_idle(self):
        """新建 controller → state = IDLE"""
    
    def test_start_transitions_to_recording(self):
        """start() 成功 → state = RECORDING"""
    
    def test_start_failure_transitions_to_failed(self):
        """start() 中 Recorder 抛异常 → state = FAILED + on_error 回调"""
    
    def test_stop_transitions_to_idle(self):
        """stop() 成功 → state = IDLE"""
    
    def test_stop_failure_with_recoverable_frames(self):
        """stop() 异常但有可读帧 → state = RECOVERY"""
    
    def test_stop_failure_without_frames(self):
        """stop() 异常且无帧 → state = FAILED, 项目目录被删除"""

class TestRecordingControllerStart:
    def test_start_creates_project_session(self, tmp_path):
        """start() 无 project_dir → 自动创建 ProjectSession"""
    
    def test_start_with_existing_project_dir(self, tmp_path):
        """start(project_dir=...) → 使用指定目录"""
    
    def test_start_while_recording_raises(self):
        """已有录制进行中 → start() → RuntimeError"""
    
    def test_start_failure_cleans_up_project_dir(self, tmp_path):
        """启动失败且无帧 → 删除占位项目目录"""
    
    def test_start_failure_with_frames_preserves_project(self, tmp_path):
        """启动失败但有可读帧 → 保留项目目录（RECOVERY）"""

class TestRecordingControllerStop:
    def test_stop_returns_recorded_data(self):
        """stop() → 返回 dict 含 frames, mic_audio, system_audio, ..."""
    
    def test_stop_saves_audio_via_project_session(self):
        """stop() 中调用 ProjectSession.save_audio()"""
    
    def test_stop_saves_project_via_project_session(self):
        """stop() 中调用 ProjectSession.save()"""
    
    def test_stop_failure_window_recovery(self):
        """stop() 异常 → on_error 回调含 recoverable 标记"""

class TestRecordingControllerCallbacks:
    def test_state_changed_callback_invoked(self):
        """状态变更时 on_state_changed 被调用"""
    
    def test_error_callback_invoked_on_start_failure(self):
        """start() 失败 → on_error(msg, recoverable=True/False) 被调用"""
    
    def test_error_callback_invoked_on_stop_failure(self):
        """stop() 失败 → on_error(msg, recoverable=True/False) 被调用"""

class TestRecordingControllerCleanup:
    def test_cleanup_stops_recorder_and_removes_resources(self):
        """cleanup() → recorder 停止 + 资源释放"""
    
    def test_cleanup_when_idle_is_safe(self):
        """IDLE 状态 cleanup() → 不抛异常"""
```

**验证命令:** `pytest tests/test_recording_controller.py -q` → 预期全部 FAIL

---

### 🟢 GREEN — 实现 RecordingController

#### Step 2: `app/recording_controller.py` — **新增 ~200 行**

**完整接口（源自技术方案 §3.1.2）:**

```python
"""录制控制器 — 纯 Python 对象，拥有录制生命周期状态机"""

from enum import Enum
from typing import Callable

from app.project_session import ProjectSession
from core.recorder import Recorder
from app.config import AppConfig


class RecordingState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    STOPPING = "stopping"
    FAILED = "failed"
    RECOVERY = "recovery"


class RecordingError(Exception):
    """录制错误"""
    def __init__(self, message: str, recoverable: bool = False):
        super().__init__(message)
        self.recoverable = recoverable


class RecordingController:
    """录制控制器 — 纯 Python 对象，不依赖 Qt"""

    def __init__(self, config: AppConfig):
        self._config = config
        self._recorder = Recorder(target_fps=config.default_fps)
        self._state = RecordingState.IDLE
        self._project_session: ProjectSession | None = None
        self._on_state_changed: Callable[[RecordingState], None] | None = None
        self._on_error: Callable[[str, bool], None] | None = None

    # ── 属性 ────────────────────────────────────────────
    @property
    def state(self) -> RecordingState:
        return self._state

    @property
    def project_session(self) -> ProjectSession | None:
        return self._project_session

    # ── 回调注册 ─────────────────────────────────────────
    def set_callbacks(self,
                      on_state_changed: Callable[[RecordingState], None] | None = None,
                      on_error: Callable[[str, bool], None] | None = None):
        self._on_state_changed = on_state_changed
        self._on_error = on_error

    # ── 状态转换 ─────────────────────────────────────────
    def _transition(self, new_state: RecordingState):
        self._state = new_state
        if self._on_state_changed:
            try:
                self._on_state_changed(new_state)
            except Exception:
                pass  # 回调不应影响状态机

    def _notify_error(self, message: str, recoverable: bool = False):
        if self._on_error:
            try:
                self._on_error(message, recoverable)
            except Exception:
                pass

    # ── 录制生命周期 ────────────────────────────────────
    def start(self, project_dir: str | None = None) -> ProjectSession:
        """启动录制。
        - project_dir=None → 自动创建 ProjectSession
        - 返回创建的 ProjectSession
        Raises:
            RuntimeError: 已在录制中
            RecordingError: 启动失败 (含 recoverable 标记)
        """
        if self._state not in (RecordingState.IDLE,):
            raise RuntimeError(f"录制进行中，当前状态: {self._state.value}")

        self._transition(RecordingState.STARTING)

        # 创建或使用项目目录
        if project_dir:
            try:
                self._project_session = ProjectSession.load(project_dir)
            except (ValueError, FileNotFoundError):
                self._project_session = ProjectSession.create(
                    self._config.projects_dir,
                    name=f"录制_{project_dir}"
                )
        else:
            self._project_session = ProjectSession.create(
                self._config.projects_dir, name="快速录制"
            )

        # 启动录制
        try:
            self._recorder.start_recording(self._project_session.project_dir)
        except Exception as exc:
            self._transition(RecordingState.FAILED)
            # 检查是否有可恢复的帧数据
            has_frames = False
            try:
                frames = self._recorder.screen.get_frames()
                has_frames = len(frames) > 0
            except Exception:
                pass

            if not has_frames:
                # 无帧 → 清理项目
                self.cleanup()
                self._notify_error(f"录制启动失败: {exc}", recoverable=False)
                raise RecordingError(f"录制启动失败: {exc}", recoverable=False)
            else:
                # 有帧 → 保留项目
                self._transition(RecordingState.RECOVERY)
                self._notify_error(f"录制启动异常，但已有 {len(frames)} 帧保留", recoverable=True)
                raise RecordingError(f"录制启动失败（部分数据已保留）: {exc}", recoverable=True)

        self._transition(RecordingState.RECORDING)
        return self._project_session

    def stop(self) -> dict:
        """停止录制，返回 recorded_data dict。
        Raises:
            RuntimeError: 未在录制中
            RecordingError: 停止异常 (含可恢复帧标记)
        """
        if self._state not in (RecordingState.RECORDING,):
            raise RuntimeError(f"未在录制中，当前状态: {self._state.value}")

        self._transition(RecordingState.STOPPING)
        recorded_data = None

        try:
            recorded_data = self._recorder.stop_recording()
        except Exception as exc:
            # 检查是否有可恢复的帧数据
            has_frames = False
            if recorded_data and recorded_data.get("frames"):
                has_frames = True

            if has_frames:
                self._transition(RecordingState.RECOVERY)
                self._notify_error(f"录制停止异常，但帧数据已保留: {exc}", recoverable=True)
                # 继续保存可恢复的数据
            else:
                self._transition(RecordingState.FAILED)
                self._notify_error(f"录制停止失败: {exc}", recoverable=False)
                self.cleanup()
                raise RecordingError(f"录制停止失败: {exc}", recoverable=False)

        # 持久化
        if recorded_data and recorded_data.get("frames") and self._project_session:
            mic = recorded_data.get("mic_audio")
            sys = recorded_data.get("system_audio")
            sr = 44100
            if recorded_data.get("audio"):
                sr = recorded_data["audio"].samplerate if hasattr(recorded_data["audio"], "samplerate") else 44100
            self._project_session.save_audio(mic, sys, sr)
            self._project_session.save(
                cursor_events=recorded_data.get("cursor_events", []),
                click_events=recorded_data.get("clicks", []),
                monitor_offset=list(recorded_data.get("monitor_offset", (0, 0))),
            )

        self._transition(RecordingState.IDLE)
        return recorded_data

    def cleanup(self):
        """强制清理录制资源和项目占位目录"""
        try:
            if self._recorder._recording:
                self._recorder.stop_recording()
        except Exception:
            pass
        
        # 删除占位项目目录（如果处于 FAILED 且无有效数据）
        if self._state in (RecordingState.FAILED,) and self._project_session:
            import shutil
            try:
                shutil.rmtree(self._project_session.project_dir, ignore_errors=True)
            except Exception:
                pass
        
        self._project_session = None
        self._transition(RecordingState.IDLE)
```

---

#### Step 3: `app/main_window.py` — 替换录制入口为 RecordingController

**在 `MainWindow.__init__` 中创建 RecordingController:**

```python
from app.recording_controller import RecordingController

class MainWindow(QMainWindow):
    def __init__(self, ...):
        # ... 现有初始化 ...
        self._recording_ctrl = RecordingController(self.config)
        self._recording_ctrl.set_callbacks(
            on_state_changed=self._on_recording_state_changed,
            on_error=self._on_recording_error,
        )
```

**替换录制入口:**

```python
# _on_home_record() → 替换为:
def _on_home_record(self):
    # 确认弹窗
    reply = QMessageBox.question(self, "开始录制", "是否开始录制？")
    if reply != QMessageBox.Yes:
        return
    self.showMinimized()
    try:
        session = self._recording_ctrl.start()
        self._switch_to_editor()  # 录制成功后的 UI 切换
    except RecordingError as e:
        self.showNormal()
        self.raise_()
        self._show_notification("录制失败", str(e), "error")

# _on_tray_record() → 替换为:
def _on_tray_record(self):
    try:
        session = self._recording_ctrl.start()
        self._switch_to_editor()
    except RecordingError as e:
        self.showNormal()
        self.raise_()
        self._show_notification("录制失败", str(e), "error")

# _on_recording_state_changed → 新增:
def _on_recording_state_changed(self, state: RecordingState):
    if state == RecordingState.RECORDING:
        self.update_status("● 录制中...")
    elif state == RecordingState.IDLE:
        self.update_status("● 就绪")
    elif state == RecordingState.FAILED:
        self.update_status("● 录制失败")

# _on_recording_error → 新增:
def _on_recording_error(self, message: str, recoverable: bool):
    self._show_notification(
        "录制警告" if recoverable else "录制错误",
        message,
        "warning" if recoverable else "error",
    )
```

---

### 🔵 REFACTOR — 移除冗余录制代码

#### Step 4: 移除 MainWindow 中的旧录制入口

移除或重构以下方法（其逻辑已迁移到 RecordingController）：
- `_start_recording_from_home()` — 逻辑已在 `RecordingController.start()`
- `_on_home_record()` 中的 `QTimer.singleShot(500, ...)` — 改为直接调用 controller
- `_on_recording_started()` — 由 `_on_recording_state_changed` 替代

#### Step 5: `_finalize_project()` 委托给 RecordingController

`_finalize_project()` 中的 `self._project_session.save_audio(...)` 和 `self._project_session.save(...)` 调用保留，但音频保存逻辑确认由 `RecordingController.stop()` 中已完成（消除重复写入）。

---

## 5. 接口/契约

### RecordingController 公开接口（完整签名）

```python
class RecordingState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    STOPPING = "stopping"
    FAILED = "failed"
    RECOVERY = "recovery"

class RecordingError(Exception):
    message: str
    recoverable: bool

class RecordingController:
    __init__(config: AppConfig)

    state: RecordingState                                    # 只读
    project_session: ProjectSession | None                   # 只读

    start(project_dir: str | None = None) -> ProjectSession  # raises RuntimeError, RecordingError
    stop() -> dict                                           # raises RuntimeError, RecordingError
    set_callbacks(on_state_changed=None, on_error=None) -> None
    cleanup() -> None
```

### 状态机转换

```
IDLE ──start()──▶ STARTING ──成功──▶ RECORDING ──stop()──▶ STOPPING ──成功──▶ IDLE
                      │                    │                    │
                      └──异常──▶ FAILED    └──异常──▶ RECOVERY  └──异常──▶ FAILED
```

### 回调契约

- `on_state_changed(state: RecordingState)`: 状态变更时调用，用于 MainWindow 更新 UI
- `on_error(message: str, recoverable: bool)`: 错误发生时调用，用于 MainWindow 显示通知

---

## 6. 数据模型变化

**无数据模型变化。** RecordingController 使用 ProjectSession 进行持久化，不新增字段/类。

---

## 7. 测试指引

### 单元测试 (test_recording_controller.py)

状态机全覆盖（至少 15 个测试用例）：

| 测试维度 | 用例数 | 场景 |
|---------|--------|------|
| 状态转换 | 6 | IDLE→STARTING, STARTING→RECORDING, STARTING→FAILED, RECORDING→STOPPING, STOPPING→IDLE, STOPPING→RECOVERY |
| start() | 4 | 自动创建项目、指定项目目录、录制中再次 start、失败清理 |
| stop() | 3 | 成功、失败有帧、失败无帧 |
| 回调 | 3 | state_changed、error recoverable、error non-recoverable |
| cleanup | 2 | 正常清理、IDLE 状态清理安全 |

### Mock 策略

```python
@pytest.fixture
def mock_recorder():
    """返回 mock Recorder，可控制 start_recording/stop_recording 的行为"""
    with patch('app.recording_controller.Recorder') as mock:
        recorder = MagicMock()
        recorder._recording = False
        recorder.screen = MagicMock()
        recorder.screen.get_frames.return_value = []
        mock.return_value = recorder
        yield recorder

@pytest.fixture
def mock_project_session():
    with patch('app.recording_controller.ProjectSession') as mock:
        yield mock
```

### 测试 (test_main_window.py) — 确认无回归

```python
def test_home_record_uses_recording_controller(qtbot):
    """首页录制按钮 → RecordingController.start() 被调用"""

def test_tray_record_uses_recording_controller(qtbot):
    """托盘录制 → RecordingController.start() 被调用"""

def test_recording_failure_shows_notification(qtbot):
    """录制失败 → 通知弹出 + 窗口恢复"""
```

---

## 8. 验收标准

- [ ] `app/recording_controller.py` 通过全部单元测试（≥15 个测试用例）
- [ ] 状态机覆盖 5 种状态 × 3 种异常路径
- [ ] 首页录制、托盘录制均通过 `RecordingController.start()` 统一入口
- [ ] 启动失败 → `FAILED` 状态 + `on_error(msg, recoverable=False)` 回调 + 项目清理与 T05 行为一致
- [ ] 停止失败 → `RECOVERY` 状态 + 有帧时保留项目
- [ ] `pytest tests/test_recording_controller.py -q` 全部通过
- [ ] `pytest tests/test_main_window.py -q` 全部通过（不退化）
- [ ] RecordingController 纯 Python（非 QObject），可独立测试
- [ ] 全量 `pytest -q` 0 failed

---

## 9. 边界情况与风险

| 边界/风险 | 处理策略 |
|-----------|---------|
| `start()` 中 `ProjectSession.create()` 失败 | 捕获异常 → FAILED, on_error 回调, 不创建 Recorder |
| `stop()` 在 `STARTING` 状态调用 | `_state` 检查，抛 `RuntimeError` |
| 回调函数抛异常 | `_transition`/`_notify_error` 中用 try/except 包裹回调调用 |
| `cleanup()` 中 `shutil.rmtree` 失败 | `ignore_errors=True` |
| T05 中已实现的录制恢复逻辑与 RecordingController 重复 | RecordingController 整合 T05 的所有恢复路径，MainWindow 中移除直接恢复逻辑 |
| 托盘录制不依赖 MainWindow._switch_to_editor() | RecordingController 不做 UI 切换；MainWindow 通过 `on_state_changed` 回调自行判断并切换 |

---

## 10. 任务级验证命令

```bash
# Step 1 (Red): 编写新测试
pytest tests/test_recording_controller.py -q  # 预期 FAIL

# Step 2-3 (Green): 实现 + MainWindow 集成
pytest tests/test_recording_controller.py -q  # 预期 PASS
pytest tests/test_main_window.py -q           # 预期 PASS

# Step 4-5 (Refactor): 移除冗余代码
pytest tests/ -q                              # 0 failed

# 行数检查
wc -l app/recording_controller.py             # 预期 ~200 行
```

---

## 11. TDD 切片汇总

| 切片 | 步骤 | 验证 |
|------|------|------|
| 🔴 Red | Step 1 编写状态机全覆盖测试 | `pytest tests/test_recording_controller.py -q` → FAIL |
| 🟢 Green | Step 2-3 实现 RecordingController + MainWindow 入口替换 | `pytest tests/test_recording_controller.py -q` → PASS |
| 🔵 Refactor | Step 4-5 移除旧录制入口 | `pytest tests/ -q` → 0 failed |

---

*本文档由 @architect 基于技术方案 v1.0 §3.1.2、任务图 T11、ADR-007、T05 录制恢复逻辑和现有代码 `core/recorder.py:41-92`, `app/main_window.py:428-548` 编写。*
