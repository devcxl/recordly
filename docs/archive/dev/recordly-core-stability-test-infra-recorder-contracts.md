# Recordly 核心稳定性 — T02: test-infra-recorder-contracts

**Project:** Recordly
**Task ID:** T02
**Slug:** test-infra-recorder-contracts
**Issue:** #29
**类型:** test-infra
**Batch:** B0（测试基础设施恢复）
**依赖:** 无

---

## 1. 目标

修复 Recorder 模块新增 `store_path` 参数后测试契约断裂导致的 8 个测试失败。具体三类问题：

1. **FakeScreen 签名不匹配:** `core/recorder.py:46` 中 `start_recording()` 创建 ScreenCapture 时传入 `store_path=store_path`，但测试中的 FakeScreen 不接受此关键字参数 → 6 个测试失败
2. **Mock 注入时机问题:** Recorder 每次 `start_recording()` 都会 `self.screen = ScreenCapture(...)` 替换实例，导致预先 monkeypatch 到 `recorder.screen` 的 mock 在新实例上失效 → 5 个测试失败
3. **Preview.set_fps() mock 缺失:** `core/main_window.py:698` 调用 `self._preview.set_fps()`，但 `test_playback_receives_recorded_audio_and_video_edit_map` 的 mock Preview 没有该方法 → 1 个测试失败

**受影响测试（8 个）:**
- `tests/test_recorder.py` — 6 个失败 (test_target_fps_is_used_for_every_screen_session, test_start_stop, test_double_start, test_record_returns_timing, test_second_recording_uses_fresh_screen_capture, test_recorder_mixes_microphone_and_system_audio)
- `tests/test_recorder.py` — 1 个失败 (test_screen_capture_error_is_propagated_on_stop) — 由 monitor_id 缺失导致
- `tests/test_main_window.py` — 1 个失败 (test_playback_receives_recorded_audio_and_video_edit_map)

---

## 2. 前置条件

- T01 完成（或有 cv2 mock 进展），但本任务不依赖 T01（文件无交集）
- 理解 `core/recorder.py` 中 `start_recording()` 的 ScreenCapture 创建逻辑（L46-50）
- 理解 `_stub_recording_engines()` 的 monkeypatch 机制

---

## 3. TDD 实现步骤

### Red — 确认失败（当前状态）

```bash
pytest tests/test_recorder.py -q
# → 7 failed:
#   test_target_fps_is_used_for_every_screen_session → TypeError: store_path
#   test_start_stop → RuntimeError (screen error propagation)
#   test_double_start → RuntimeError
#   test_record_returns_timing → RuntimeError
#   test_second_recording_uses_fresh_screen_capture → TypeError: store_path
#   test_screen_capture_error_is_propagated_on_stop → AttributeError: monitor_id
#   test_recorder_mixes_microphone_and_system_audio → RuntimeError
```

### Green — 分四步实现

#### Step 1: 修复 FakeScreen 签名（`tests/test_recorder.py`）

每个测试文件中定义的 `FakeScreen` 需要接受 `store_path` 参数。涉及两类 FakeScreen：

**第一类: 简单 FakeScreen（测试 target_fps / second_recording）**

```python
# 当前:
class FakeScreen:
    def __init__(self, monitor_id=1, target_fps=30):
        ...
# 修改为:
class FakeScreen:
    def __init__(self, monitor_id=1, target_fps=30, store_path=None):
        self.store_path = store_path
        ...
```

**第二类: 测试 screen_capture_error_is_propagated_on_stop 的 FakeScreen**

当前问题是 FakeScreen 缺少 `monitor_id` 属性。`core/recorder.py:47` 中读取 `self.screen.monitor_id`（此时 screen 已被替换为新实例），需要 FakeScreen 暴露此属性：

```python
class FakeScreen:
    def __init__(self, monitor_id=1, target_fps=30, store_path=None):
        self.monitor_id = monitor_id
        self.store_path = store_path
        self.all_frames = []
        self.monitor_offset = (0, 0)
        self.error = RuntimeError("capture failed")  # 已有
```

**涉及 FakeScreen 的测试（逐个修复）:**
- `test_target_fps_is_used_for_every_screen_session` (L24-31) → + `store_path=None`
- `test_second_recording_uses_fresh_screen_capture` (L107-115) → + `store_path=None`
- `test_screen_capture_error_is_propagated_on_stop` (L176-190) → + `store_path=None` + 添加 `monitor_id` 属性
- `test_recorder_mixes_microphone_and_system_audio` — 此测试使用 `_stub_recording_engines` mock 而非 FakeScreen patch，问题在 Step 2 解决

**验证:**
```bash
pytest tests/test_recorder.py -q -k "test_target_fps or test_second_recording or test_screen_capture"
# 目标: 这 3 个通过
```

#### Step 2: 修复 mock 注入时机（`tests/test_recorder.py`）

问题根因：`_stub_recording_engines` 在 `start_recording()` 之前 monkeypatch 了 `recorder.screen`，但 `start_recording()` 内部执行 `self.screen = ScreenCapture(...)` 覆盖了 mock 对象。

**解决方案:** `_stub_recording_engines` 需要 monkeypatch `recorder_module.ScreenCapture` 本身（模块级别的类替换），而不是实例里的 `.screen` 属性。

修改 `_stub_recording_engines` 函数（L6-15）：

```python
def _stub_recording_engines(recorder, monkeypatch):
    """Mock 录制引擎为无操作桩，使用模块级 monkeypatch 避免 start_recording 内部替换实例。"""
    import core.recorder as recorder_module
    
    class StubScreen:
        def __init__(self, monitor_id=1, target_fps=30, store_path=None):
            self.monitor_id = monitor_id
            self.target_fps = target_fps
            self.store_path = store_path
            self.all_frames = []
            self.monitor_offset = (0, 0)
            self.error = None
        def clear(self): pass
        def start(self): pass
        def stop(self): pass
    
    monkeypatch.setattr(recorder_module, "ScreenCapture", StubScreen)
    monkeypatch.setattr(recorder.mic, "start", lambda: None)
    monkeypatch.setattr(recorder.mic, "stop", lambda: None)
    monkeypatch.setattr(recorder.system_audio, "start", lambda: False)
    monkeypatch.setattr(recorder.system_audio, "stop", lambda: None)
    monkeypatch.setattr(recorder.pointer, "start", lambda: None)
    monkeypatch.setattr(recorder.pointer, "stop", lambda: None)
```

> **关键:** `monkeypatch.setattr(recorder_module, "ScreenCapture", StubScreen)` 替换模块级引用，这样 `Recorder.start_recording()` 中 `self.screen = ScreenCapture(...)` 创建的是 StubScreen 实例。

**验证:**
```bash
pytest tests/test_recorder.py -q -k "test_start_stop or test_double_start or test_record_returns_timing or test_recorder_mixes"
# 目标: 这 4 个通过
```

#### Step 3: 修复 test_recorder_mixes_microphone_and_system_audio 的额外问题

此测试（L232-269）特殊：它使用 `_stub_recording_engines` 做基本 mock，然后单独替换 `recorder.mic.stop` 和 `recorder.system_audio`。Step 2 的修复（模块级 StubScreen）已解决 `start_recording()` 内部 ScreenCapture 创建问题。但需要确认 `recorder.system_audio = FakeSystem()` 后的 `start()` 方法是否也被 StubScreen 覆盖——不会，因为 StubScreen 只替换 ScreenCapture 类。

**此测试不需要额外修改**，Step 2 的修复应该让它通过。

#### Step 4: 修复 test_playback_receives_recorded_audio_and_video_edit_map（`tests/test_main_window.py`）

**文件:** `tests/test_main_window.py`，测试函数约 L39-68

问题：`_create_playback_controller()` 调用 `self._preview.set_fps(int(self._compositor.fps))`（main_window.py:698），但测试中的 `window._preview = object()` 没有 `set_fps` 方法。

**修复:**

在 FakePlayback 或 window 上添加 set_fps mock：

```python
# 在测试函数内，window 创建之后:
window._preview = SimpleNamespace(set_fps=lambda fps: None)
# 或者用 MagicMock:
from unittest.mock import MagicMock
window._preview = MagicMock()
```

更简洁的做法是修改 `window._preview` 从 `object()` 为 `SimpleNamespace(set_fps=lambda fps: None)`。

> **注意:** `MainWindow._create_playback_controller` 中 `self._preview.set_fps(...)` 调用在 `FakePlayback.__init__` 之后才执行。FakePlayback 的 `__init__` 先被调用（捕获 kwargs），然后 set_fps 被调用。只需确保 `window._preview` 有 `set_fps` 方法，不需要在 FakePlayback 中处理。

**验证:**
```bash
pytest tests/test_main_window.py::test_playback_receives_recorded_audio_and_video_edit_map -q
# 目标: 通过
```

### Refactor — 检查清单

- [ ] `_stub_recording_engines` 使用模块级 `monkeypatch.setattr(recorder_module, "ScreenCapture", ...)` 而非实例级 mock
- [ ] 各测试中的自定义 FakeScreen 签名都与 `ScreenCapture.__init__` 公共签名一致
- [ ] 无新增 skip/xfail

---

## 4. 接口/契约

**无公开接口变更。**

测试契约修复：
- `ScreenCapture.__init__(self, monitor_id=1, target_fps=30, store_path=None)` — 测试 FakeScreen 必须支持 `store_path`
- `Recorder.start_recording(project_dir)` 传入 `store_path=os.path.join(project_dir, "frames.data")` — 测试 mock 不需要处理此路径逻辑
- `_create_playback_controller()` 期望 `self._preview` 有 `set_fps(int)` 方法

---

## 5. 数据模型变化

无。

---

## 6. 测试指引

### 本任务覆盖的测试修复

| 测试文件 | 修复内容 |
|---------|---------|
| `tests/test_recorder.py` | 7 个测试的 FakeScreen + mock 注入时机 |
| `tests/test_main_window.py` | 1 个测试的 set_fps mock |

### 回归验证

```bash
# 逐文件验证
pytest tests/test_recorder.py -q -v
pytest tests/test_main_window.py -q -v

# 全量
pytest -q
```

---

## 7. 验收标准

- [ ] `pytest tests/test_recorder.py -q` 全部通过（当前 7 failed → 0）
- [ ] `pytest tests/test_main_window.py::test_playback_receives_recorded_audio_and_video_edit_map -q` 通过
- [ ] FakeScreen 签名与 ScreenCapture 公共接口一致（接受 `store_path` 参数）
- [ ] `_stub_recording_engines` 使用模块级 monkeypatch，避免实例替换丢失
- [ ] 无新增 skip/xfail

---

## 8. 边界情况与风险

| 场景 | 处理 |
|------|------|
| FakeScreen 有 `store_path=None` 作为默认值 | 允许 `Recorder.start_recording(None)` 时 store_path 为 None |
| 模块级 ScreenCapture mock 影响其他测试 | 仅在函数作用域内 monkeypatch，pytest 自动恢复 |
| `test_recorder_mixes_microphone_and_system_audio` 中 FakeSystem 类不影响 ScreenCapture | FakeSystem 替换 `recorder.system_audio`，StubScreen 替换 ScreenCapture 类，互不影响 |

**风险:** 模块级 `monkeypatch.setattr(recorder_module, "ScreenCapture", ...)` 可能影响同一文件中后续测试的 `import`。缓解：pytest 的 `monkeypatch` fixture 在函数结束后自动恢复；如果手动 `import core.recorder` 在 patch 之前已缓存，不影响。

---

## 9. 任务验证命令

```bash
# 核心验证
pytest tests/test_recorder.py -q -v

# 全量回归
pytest -q

# 确认无残留
grep -rn "store_path" tests/test_recorder.py
# 预期: FakeScreen.__init__ 中出现 store_path 参数
```

---

## 关联文件

| 文件 | 操作 |
|------|------|
| `tests/test_recorder.py` | 修复 7 个测试：FakeScreen 签名 + mock 注入时机 |
| `tests/test_main_window.py` | 修复 1 个测试：添加 set_fps mock |

> **本任务仅修改测试文件，不触碰 `core/` 或 `app/` 业务代码。**
