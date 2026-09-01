# Recordly 核心稳定性 — T05: recording-unified-recovery

**Project:** Recordly
**Task ID:** T05
**Slug:** recording-unified-recovery
**Issue:** #32
**类型:** fix
**Batch:** B2（P0 录制基础 + 原子保存）
**依赖:** T04 (#31)

---

## 1. 目标

统一录制入口并实现完整的启动/停止失败恢复。当前三个录制路径（首页按钮、托盘菜单、`_toggle_record`）各有不同的启动/错误处理逻辑，导致录制失败时窗口不恢复、占位项目残留、异常被吞没。

**P0 阶段（本任务）:** 在 MainWindow 内部合并入口 + 修复 Recorder.finally 清理。
**P1 阶段（T11）:** 提取 RecordingController 状态机。

---

## 2. 前置条件

- T04 完成（路径规范化），`_current_project_path` 语义清晰
- 理解 `core/recorder.py` 中 `start_recording()` 和 `stop_recording()` 的当前实现（L41-101）
- 理解 `MainWindow` 中三个录制入口（L412-437 首页；L457-464 toggle；L394-396 托盘）

---

## 3. TDD 实现步骤

### Red — 确认当前问题

当前录制启动失败场景：
1. 首页录制 L412-437：先 `showMinimized()` → `QTimer.singleShot(500, start)` → 异常无法被 try/except 捕获，窗口已最小化且无恢复逻辑
2. 托盘录制 L394-396：直接调用 `_toggle_record` → `_on_recording_started` → 异常时 `set_recording_state(False)` 但窗口不恢复
3. `core/recorder.py` L61-68: finally 块无条件停止已启动资源，可能覆盖原始异常（如果 mic.stop() 或 screen.stop() 也抛异常）

### Green — 分六步实现

#### Step 1: 修复 `core/recorder.py` 的启动失败清理（L55-68）

**当前代码:**
```python
try:
    self.screen.start()
    self._screen_session_started = True
    self.mic.start()
    self.system_audio.start()
    self.pointer.start()
except Exception:
    self._recording = False
    try:
        self.mic.stop()
    finally:
        self.system_audio.stop()
        self.screen.stop()
    raise
```

**问题分析:**
1. `mic.stop()` 可能抛异常 → 在 finally 的前一个 try 中，如果 mic.stop() 抛异常，会跳过后面的 `system_audio.stop()` 和 `screen.stop()`
2. 没有清理 `pointer` 资源（pointer 在 finally 之前未启动）
3. 原始异常可能被清理过程中的异常覆盖

**修复:**
```python
try:
    self.screen.start()
    self._screen_session_started = True
    self.mic.start()
    self.system_audio.start()
    self.pointer.start()
except Exception:
    self._recording = False
    # 逆序 best-effort 清理已启动资源，不覆盖原始异常
    resources = [
        ("pointer", self.pointer),
        ("system_audio", self.system_audio),
        ("mic", self.mic),
        ("screen", self.screen),
    ]
    for name, resource in resources:
        try:
            if hasattr(resource, 'stop'):
                resource.stop()
        except Exception:
            # 资源已停止或从未启动，忽略清理异常
            pass
    raise  # 重新抛出原始异常
```

> **改进点:**
> - 使用资源列表逆序清理（先启动的后停止）
> - 每个资源的 stop() 独立 try/except，互不影响
> - 所有清理异常被吞没，原始异常被正确传播

#### Step 2: 合并首页和托盘录制入口（`app/main_window.py`）

**目标:** 消除三条独立路径，统一为 `_on_home_record()` 和 `_on_tray_record()` → 共用 `_start_unified_recording(project_dir=None)`。

**新增方法:**
```python
def _start_unified_recording(self, project_dir: str | None = None):
    """统一录制启动 — 创建项目目录 → 启动 Recorder → 成功/失败处理
    
    Args:
        project_dir: 项目目录路径。None 时自动创建。
    """
    # 1. 确保有项目目录
    if project_dir is None:
        name = f"录制 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = str(Path(self.config.projects_dir) / f"{timestamp}_{name}")
        os.makedirs(project_dir, exist_ok=True)
        self._current_project_path = project_dir
        self._project_name = name
        
        # 保存占位 project.json
        placeholder = Project()
        placeholder.name = name
        placeholder.save(str(Path(project_dir) / "project.json"))
    
    # 2. 最小化窗口
    self.showMinimized()
    
    # 3. 同步启动录制（不再使用 QTimer 延迟）
    try:
        self._recorder.start_recording(project_dir)
        self._is_recording = True
        self.recording_started.emit()
        self._update_ui_state()
        self.update_status("● 录制中...")
    except Exception as exc:
        # 4. 启动失败 — 检查是否有可恢复的帧数据
        self._is_recording = False
        self._update_ui_state()
        
        has_frames = (
            hasattr(self._recorder.screen, 'all_frames') 
            and len(self._recorder.screen.all_frames) > 0
        )
        
        if has_frames:
            # 有可读帧 → 保留项目（RECOVERY）
            self._show_notification(
                "录制部分失败",
                f"录制启动时发生错误，但部分帧已保存。\n{exc}",
                "warning",
            )
        else:
            # 无帧 → 删除占位项目 + 恢复窗口
            self._current_project_path = None
            try:
                if os.path.isdir(project_dir):
                    shutil.rmtree(project_dir, ignore_errors=True)
            except Exception:
                pass
            self._show_notification("录制启动失败", str(exc), "error")
        
        self.showNormal()
        self.raise_()
        return
    
    # 成功状态已在 try 块中设置
```

**首页录制入口（修改 `_on_home_record`）:**
```python
def _on_home_record(self):
    """首页点击'开始录制' → 确认弹窗 → 创建项目 → 开始录制"""
    reply = QMessageBox.question(
        self, "开始录制",
        "将开始屏幕录制。录制时窗口会最小化到系统托盘，"
        "你可以通过托盘图标停止录制。\n\n确定开始？",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
    )
    if reply != QMessageBox.Yes:
        return
    
    self._start_unified_recording()  # project_dir=None → 自动创建
```

**托盘录制入口（修改 `_toggle_record` / 托盘菜单）:**

托盘录制不应复用当前 `_current_project_path`。修改托盘录制动作为：
```python
# 在 _setup_tray 中:
self._tray_record_act = menu.addAction(
    "⬤ 开始录制", lambda: self._start_unified_recording()
)
```

删除旧的 `_toggle_record` 中用于启动的分支。保留 `_toggle_record` 仅用于停止（或直接使用 `_stop_unified_recording`）。

#### Step 3: 统一录制停止 + 恢复（`app/main_window.py`）

```python
def _stop_unified_recording(self):
    """统一录制停止 — 收集数据 → 保存项目 → 切换编辑器"""
    if not self._is_recording:
        return
    
    self._is_recording = False
    self.recording_stopped.emit()
    self._update_ui_state()
    
    try:
        self._recorded_data = self._recorder.stop_recording()
    except Exception as exc:
        self._recorded_data = None
        self.set_recording_state(False)
        
        # 检查是否有可读帧
        has_frames = (
            hasattr(self._recorder.screen, 'all_frames') 
            and len(self._recorder.screen.all_frames) > 0
        )
        
        if has_frames:
            # 有帧 → 尝试恢复
            self._recorded_data = {
                "frames": self._recorder.screen.all_frames,
                "audio": None,
                "cursor_events": [],
                "clicks": [],
                "monitor_offset": getattr(self._recorder.screen, 'monitor_offset', (0, 0)),
            }
            self._show_notification(
                "录制部分失败",
                f"录制停止时发生错误，但帧数据已保留。\n{exc}",
                "warning",
            )
        else:
            # 无帧 → 清理项目
            self.update_status("● 录制失败")
            self._show_notification("录制失败", str(exc), "error")
            if self._current_project_path and os.path.isdir(self._current_project_path):
                try:
                    shutil.rmtree(self._current_project_path, ignore_errors=True)
                except Exception:
                    pass
                self._current_project_path = None
            self.showNormal()
            self.raise_()
            return
    
    # 成功路径 — 复制自 _on_recording_stopped 的原有逻辑
    if self._recorded_data and self._recorded_data.get("frames"):
        self._compositor.load_frames(self._recorded_data["frames"])
        # ... 其余原有逻辑（加载光标事件、创建播放控制器等）
    
    self.update_status("● 录制完成")
    self._finalize_project()
    self._switch_to_editor()
    self.showNormal()
    self.raise_()
```

**`_toggle_record` 简化为:**
```python
def _toggle_record(self):
    if self._is_recording:
        self._stop_unified_recording()
    else:
        self._start_unified_recording()
```

#### Step 4: 确保托盘录制创建独立项目

托盘录制通过 `_start_unified_recording(project_dir=None)` 自动创建新项目，不修改 `_current_project_path`（如果已有打开的项目，录制完成后切换编辑器但旧项目状态由 `_on_open_project` 管理）。

> **注意:** 如果用户正在编辑已有项目然后托盘录制，当前设计是录制完成后切换到新项目。这符合 PRD 要求：托盘录制创建独立项目。

#### Step 5: 修复 `_update_ui_state` 的状态同步

需要确保 `_update_ui_state` 反映通过统一入口设置的状态。当前逻辑（L641-648）通过 `self._is_recording` 驱动，统一入口已正确设置此标志。

```python
def _update_ui_state(self):
    rec = self._is_recording
    self._btn_stop_rec.setEnabled(rec)
    self._btn_export.setEnabled(not rec and bool(self._compositor._frames))
    self._tray_record_act.setEnabled(not rec)
    self._tray_stop_act.setEnabled(rec)
    # 状态文本由 update_status() 单独设置，不在此处重复
```

#### Step 6: 编写测试

**文件:** `tests/test_recorder.py`（新增测试）
```python
class TestRecorderStartRecovery:
    """启动失败恢复"""

    def test_start_failure_cleans_up_started_resources(self, monkeypatch):
        """启动失败时逆序清理已启动资源，不覆盖原始异常"""
        import core.recorder as recorder_module
        
        stopped = []
        class FakeScreen:
            def __init__(self, monitor_id=1, target_fps=30, store_path=None):
                self.monitor_id = monitor_id
                self.all_frames = []
                self.monitor_offset = (0, 0)
                self.error = None
            def clear(self): pass
            def start(self): stopped.append("screen"); pass
            def stop(self): stopped.append("screen_stop")
        
        class FakeMic:
            def start(self): stopped.append("mic"); pass
            def stop(self): stopped.append("mic_stop")
        
        class FakeSystem:
            def start(self): raise RuntimeError("system audio failed")
            def stop(self): stopped.append("system_stop")
        
        class FakePointer:
            def start(self): pass
            def stop(self): stopped.append("pointer_stop")
        
        monkeypatch.setattr(recorder_module, "ScreenCapture", FakeScreen)
        monkeypatch.setattr(recorder_module, "MicrophoneCapture", FakeMic)
        monkeypatch.setattr(recorder_module, "SystemAudioCapture", FakeSystem)
        monkeypatch.setattr(recorder_module, "PointerTracker", FakePointer)
        
        recorder = recorder_module.Recorder()
        with pytest.raises(RuntimeError, match="system audio failed"):
            recorder.start_recording()
        
        # 验证已启动的资源被逆序清理
        assert "screen_stop" in stopped
        assert "mic_stop" in stopped


class TestRecorderStopRecovery:
    """停止失败恢复"""
    
    def test_stop_error_with_frames_preserves_data(self, monkeypatch):
        """停止失败但有帧时保留数据"""
        # 模拟 screen.error 非空但有 all_frames
        ...
    
    def test_stop_error_without_frames_cleans_up(self, monkeypatch):
        """停止失败且无帧时清理项目"""
        ...
```

**文件:** `tests/test_main_window.py`（新增测试）
```python
class TestUnifiedRecording:
    """统一录制入口"""
    
    def test_tray_recording_creates_new_project_not_overwrites_current(self):
        """托盘录制创建新项目，不覆盖已有打开项目"""
        ...
    
    def test_start_failure_restores_window_and_cleans_placeholder(self):
        """录制启动失败 → 窗口恢复 + 占位项目清理"""
        ...
```

### Refactor — 检查清单

- [ ] `_start_recording_from_home` 方法被完全移除（由 `_start_unified_recording` 替代）
- [ ] `_on_recording_started` 信号槽被移除（统一入口不通过信号驱动录制启动）
- [ ] `_on_recording_stopped` 信号槽被移除（统一入口直接处理停止逻辑）
- [ ] `_toggle_record` 简化为委托入口
- [ ] Recorder.finally 清理不覆盖原始异常

---

## 4. 接口/契约

### 新增方法

```python
def _start_unified_recording(self, project_dir: str | None = None) -> None:
    """统一录制启动。project_dir=None 时自动创建项目目录。"""

def _stop_unified_recording(self) -> None:
    """统一录制停止。收集数据 → 恢复/清理 → 切换编辑器。"""
```

### Recorder.start_recording() 契约（修复后）

**异常语义:**
- 抛出异常时，`self._recording` 已被设为 `False`
- 已启动的资源（screen/mic/system_audio/pointer）已被 best-effort 逆序清理
- 原始异常被正确传播（不被清理异常覆盖）

---

## 5. 数据模型变化

无。

---

## 6. 测试指引

### 新增测试

| 文件 | 测试 | 场景 |
|------|------|------|
| `tests/test_recorder.py` | `test_start_failure_cleans_up_resources` | 启动失败逆序清理 |
| `tests/test_recorder.py` | `test_start_failure_propagates_original_exception` | 原始异常传播 |
| `tests/test_main_window.py` | `test_tray_recording_independent_project` | 托盘录制独立项目 |
| `tests/test_main_window.py` | `test_start_failure_window_restore` | 启动失败窗口恢复 |
| `tests/test_main_window.py` | `test_stop_failure_with_frames_recovery` | 停止失败帧恢复 |
| `tests/test_main_window.py` | `test_stop_failure_without_frames_cleanup` | 停止失败清理 |

### 回归测试

```bash
pytest tests/test_recorder.py -q -v
pytest tests/test_main_window.py -q -v
```

---

## 7. 验收标准

- [ ] 首页录制启动失败 → 窗口恢复、状态栏提示错误、占位项目被清理
- [ ] 屏幕采集停止时失败 → 窗口恢复、有帧时项目保留
- [ ] 托盘录制创建新项目且不修改当前已打开项目
- [ ] `_start_unified_recording` 和 `_stop_unified_recording` 为所有录制路径的唯一入口
- [ ] `pytest tests/test_recorder.py -q` 全部通过（包含 T02 修复后的回归）
- [ ] 新增测试：启动失败恢复 × 2 场景、停止失败恢复 × 2 场景
- [ ] `core/recorder.py` 中 finally 块逆序清理 + 保留原始异常

---

## 8. 边界情况与风险

| 场景 | 处理 |
|------|------|
| 录制启动前项目目录已存在 | `os.makedirs(exist_ok=True)` 不报错 |
| 项目目录创建成功但 recorder 启动失败 | 无帧时 `shutil.rmtree` 删除目录 |
| recorder 启动时 screen 失败但 mic 已启动 | 逆序清理：先停 pointer → system_audio → mic → screen |
| 停止时 screen.error 非空但帧可读 | 保留帧数据，创建 RECOVERY 项目 |
| 录制中用户关闭应用 | 由 `closeEvent` 处理（当前最小化到托盘，不退出） |
| 托盘录制时窗口处于编辑状态 | 当前编辑项目保持打开，录制完成切换到新项目编辑器 |

**风险:** `_start_unified_recording` 中 `showMinimized()` 后立即同步调用 `start_recording()`，如果录制启动耗时长（如等待屏幕采集初始化），可能导致窗口最小化后短暂无响应。缓解：`ScreenCapture.start()` 是异步的（线程），`start_recording()` 返回很快。

---

## 9. 任务验证命令

```bash
# Recorder 清理逻辑测试
pytest tests/test_recorder.py -q -v

# MainWindow 录制流程测试
pytest tests/test_main_window.py -q -v -k "record or tray"

# 全量回归（B2 完成时应 0 failed）
pytest -q
```

---

## 关联文件

| 文件 | 操作 |
|------|------|
| `core/recorder.py` | 修复 finally 块清理逻辑（L55-68） |
| `app/main_window.py` | 合并录制入口（`_start_unified_recording` / `_stop_unified_recording`）+ 移除旧入口 |
| `tests/test_recorder.py` | 新增启动/停止失败恢复测试 |
| `tests/test_main_window.py` | 新增统一录制 + 托盘独立项目测试 |
