# T12: extract-export-controller — 提取 ExportController

**Project:** Recordly  
**Task ID:** T12  
**Slug:** extract-export-controller  
**Issue:** #39  
**类型:** refactor  
**Batch:** B7  
**依赖:** T09 (#36), T10 (#37), T11 (#38)

---

## 1. 目标

从 `MainWindow` 提取 `ExportController`（ADR-007 §3.3，技术方案 §3.1.3），拥有 QThread + ExportWorker 生命周期管理，确保 finished 信号在所有路径恰好发出一次（复用 T09 的鲁棒性保证），统一取消/清理协议。通过 T10 的 `ProjectSession` 获取音频数据路径和项目 FPS。

---

## 2. 前置条件

- [x] T09 完成：`ExportWorker.run()` try/except/finally 保证 finished 恰好一次
- [x] T10 完成：`ProjectSession` 可用，提供 `load_audio()`、`project.fps` 等接口
- [x] T11 完成：`RecordingController` 已提取，MainWindow 结构已简化
- [x] `ExportWorker` 可接受 `audio_data: np.ndarray | None` 参数

---

## 3. 当前状态

```
MainWindow 中导出相关方法:
├── _on_export()                        # 参数收集 + QThread 创建 + 信号绑定 + 进度框
├── _cancel_export()                    # worker.cancel()
├── _on_export_finished(result)         # 进度框关闭 + 通知 + 线程清理
├── self._export_worker                 # 实例变量
├── self._export_thread                 # 实例变量
├── self._progress                      # QProgressDialog 实例变量
└── self._btn_export                    # 导出按钮（需在导出中禁用）
```

问题：
- QThread 创建/清理分布在 3 个方法中
- `_on_export_finished` 中手动 `_export_thread = None` / `_export_worker = None`
- 无导出状态防护（可能重复点击导出）
- 进度框在 `_on_export` 中创建，在 `_on_export_finished` 中关闭

---

## 4. Red → Green → Refactor 实施步骤

### 🔴 RED — 编写 ExportController 单元测试

#### Step 1: `tests/test_export_controller.py` — **新增文件**

```python
"""ExportController 单元测试"""

class TestExportControllerInit:
    def test_initial_state_not_exporting(self):
        """新建 controller → is_exporting = False"""

class TestExportControllerStartExport:
    def test_start_export_creates_thread_and_worker(self):
        """start_export() → QThread 创建 + worker.moveToThread"""
    
    def test_start_export_sets_exporting_flag(self):
        """start_export() → is_exporting = True"""
    
    def test_start_export_while_exporting_raises(self):
        """已有导出进行中 → RuntimeError"""
    
    def test_start_export_passes_correct_settings(self):
        """ExportWorker 收到的 settings 与传入一致"""
    
    def test_start_export_uses_project_session_fps(self):
        """settings.fps 使用 project_session.project 的 fps"""

class TestExportControllerFinished:
    def test_export_finished_signal_emitted(self):
        """worker finished → ExportController.export_finished 信号发出"""
    
    def test_export_finished_emits_exactly_once_on_success(self, qtbot):
        """成功导出 → export_finished 恰好发出一次"""
    
    def test_export_finished_emits_exactly_once_on_failure(self, qtbot):
        """导出失败 → export_finished 恰好发出一次"""
    
    def test_export_finished_emits_exactly_once_on_cancel(self, qtbot):
        """取消导出 → export_finished 恰好发出一次"""
    
    def test_export_finished_resets_exporting_flag(self):
        """finished → is_exporting = False"""
    
    def test_export_finished_cleans_thread(self):
        """finished → QThread.quit + deleteLater"""

class TestExportControllerCancel:
    def test_cancel_calls_worker_cancel(self):
        """cancel() → worker.cancel() 被调用"""
    
    def test_cancel_while_not_exporting_is_safe(self):
        """未在导出 → cancel() 不抛异常"""
    
    def test_cancel_cleans_temp_files(self):
        """cancel() → 临时文件被删除"""
    
    def test_cancel_removes_incomplete_output(self):
        """cancel() → 不完整输出文件被删除"""

class TestExportControllerCleanup:
    def test_cleanup_on_destroy(self):
        """controller 销毁 → 线程终止 + 资源释放"""
```

**验证命令:** `pytest tests/test_export_controller.py -q` → 预期全部 FAIL

---

### 🟢 GREEN — 实现 ExportController

#### Step 2: `app/export_controller.py` — **新增 ~180 行**

**完整接口（源自技术方案 §3.1.3）:**

```python
"""导出控制器 — QObject，管理 QThread + ExportWorker 生命周期"""

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from core.exporter import ExportWorker, ExportSettings, ExportResult
from core.compositor import Compositor
from app.project_session import ProjectSession


class ExportController(QObject):
    """导出控制器 — 唯一 QObject Controller"""

    export_progress = pyqtSignal(int)          # 0-100
    export_finished = pyqtSignal(ExportResult)  # 所有路径恰好一次

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: ExportWorker | None = None
        self._thread: QThread | None = None
        self._exporting = False

    @property
    def is_exporting(self) -> bool:
        return self._exporting

    def start_export(self, compositor: Compositor,
                     project_session: ProjectSession,
                     settings: ExportSettings) -> None:
        """启动导出线程。
        - 从 project_session 获取音频数据
        - 创建 ExportWorker + QThread
        - 绑定 finished → quit → deleteLater
        Raises:
            RuntimeError: 已有导出进行中
        """
        if self._exporting:
            raise RuntimeError("已有导出进行中")

        self._exporting = True

        # 从 ProjectSession 获取音频数据
        audio_data = None
        audio_info = project_session.load_audio()
        if audio_info:
            audio_data = audio_info.get("mixed") or audio_info.get("mic") or audio_info.get("system")
            settings.samplerate = audio_info.get("samplerate", 44100)

        # 确保 fps 使用 compositor.fps（T08 修复）
        settings.fps = compositor.fps

        # 创建 worker 和线程
        self._worker = ExportWorker(compositor, audio_data, settings)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)

        # 信号绑定
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.export_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, '_thread', None))

        self._thread.start()

    def cancel(self) -> None:
        """取消当前导出。触发 worker.cancel() → terminate → wait → 清理"""
        if self._worker and self._exporting:
            self._worker.cancel()

    def _on_worker_finished(self, result: ExportResult):
        """worker finished 回调 — 所有路径恰好调用一次"""
        self._exporting = False
        self._worker = None
        self.export_finished.emit(result)

    def cleanup(self):
        """强制清理 — 用于应用退出"""
        if self._worker and self._exporting:
            self._worker.cancel()
        if self._thread and self._thread.isRunning():
            try:
                self._thread.quit()
                self._thread.wait(3000)
            except Exception:
                pass
```

---

#### Step 3: `app/main_window.py` — 替换导出入口为 ExportController

**在 `MainWindow.__init__` 中创建 ExportController:**

```python
from app.export_controller import ExportController

class MainWindow(QMainWindow):
    def __init__(self, ...):
        # ... 现有初始化 ...
        self._export_ctrl = ExportController(self)
        self._export_ctrl.export_progress.connect(self._on_export_progress)
        self._export_ctrl.export_finished.connect(self._on_export_finished)
```

**替换 `_on_export()`:**

```python
def _on_export(self):
    """简化后的导出入口 — 委托给 ExportController"""
    has_frames = self._compositor._frames is not None
    has_project = self._project_session is not None
    if not has_frames and not has_project:
        self._show_notification("无法导出", "请先录制或打开一个项目", "warning")
        return

    dialog = ExportDialog(self, self.config.recordings_dir, self.config.default_fps)
    if dialog.exec_() != ExportDialog.Accepted:
        return
    if not dialog.output_path:
        self._show_notification("未选择保存路径", "请选择文件保存位置", "warning")
        return

    is_gif = dialog.export_format == "gif"
    crop_region = self._compositor._crop_region if self._crop_active else None

    settings = ExportSettings(
        output_path=dialog.output_path,
        format=dialog.export_format,
        aspect_ratio=dialog.aspect_ratio,
        quality=dialog.quality,
        fps=self._compositor.fps,
        bitrate=self.config.default_bitrate,
        loop=dialog.gif_loop_value,
        width=export_width,
        height=export_height,
        max_height=export_max_height,
        extra_audio=self._audio_regions if self._audio_regions else None,
        crop_region=crop_region,
    )

    self._btn_export.setEnabled(False)

    # 创建进度对话框
    self._progress = QProgressDialog("正在导出视频...", "取消", 0, 100, self)
    self._progress.setWindowTitle("导出")
    self._progress.setWindowModality(Qt.WindowModal)
    self._progress.canceled.connect(self._export_ctrl.cancel)

    try:
        self._export_ctrl.start_export(
            self._compositor, self._project_session, settings
        )
    except RuntimeError as e:
        self._show_notification("导出错误", str(e), "error")
        self._btn_export.setEnabled(True)
```

**替换 `_on_export_finished()`:**

```python
def _on_export_finished(self, result: ExportResult):
    """简化为通知 + UI 恢复（线程清理由 ExportController 处理）"""
    if self._progress:
        self._progress.close()
        self._progress = None
    self._btn_export.setEnabled(True)

    if result.success:
        self.update_status("● 导出完成")
        self._show_notification(
            "导出完成",
            f"视频已保存到:\n{result.path}\n({result.size_bytes/1024/1024:.1f}MB)",
            "success",
        )
    else:
        self.update_status("● 导出失败")
        self._show_notification(
            "导出失败",
            result.error or "未知错误",
            "error",
        )
```

**新增 `_on_export_progress`:**

```python
def _on_export_progress(self, value: int):
    if self._progress:
        self._progress.setValue(value)
```

**移除 `_cancel_export()`:**

删除原 `_cancel_export()` 方法（line 948-950），替换为 `self._export_ctrl.cancel` 直接绑定到进度框。

---

### 🔵 REFACTOR — 清理 MainWindow 导出残留

#### Step 4: 移除 MainWindow 中的导出实例变量

移除或转为局部变量：
- `self._export_worker` → 由 ExportController 管理
- `self._export_thread` → 由 ExportController 管理
- `self._progress` → 保留，但改为局部变量或在 `_on_export` 中创建

#### Step 5: 导出按钮状态管理收敛

`self._btn_export.setEnabled(False/True)` 保留在 MainWindow（UI 层），但改为根据 `self._export_ctrl.is_exporting` 判断：

```python
@property
def _can_export(self) -> bool:
    return not self._export_ctrl.is_exporting
```

---

## 5. 接口/契约

### ExportController 公开接口（完整签名）

```python
class ExportController(QObject):
    export_progress = pyqtSignal(int)            # 0-100
    export_finished = pyqtSignal(ExportResult)    # 所有路径恰好一次

    __init__(parent=None)

    start_export(compositor: Compositor, 
                 project_session: ProjectSession,
                 settings: ExportSettings) -> None  # raises RuntimeError
    cancel() -> None
    cleanup() -> None

    is_exporting: bool  # 只读属性
```

### 信号发出保证

```
export_finished 在所有路径恰好发出一次：
  - 正常导出完成 → success=True
  - FFmpeg 失败 → success=False, error="FFmpeg 导出失败..."
  - 取消导出 → success=False, error="已取消"
  - 异常终止 → success=False, error="导出异常: ..."
  - 线程异常 → success=False, error="导出意外终止"
```

### MainWindow → ExportController 委托映射

| 原 MainWindow 职责 | 委托到 |
|---------------------|--------|
| `_on_export()` 中 QThread 创建 | `ExportController.start_export()` |
| `_on_export()` 中信号绑定 | `ExportController.start_export()` |
| `_cancel_export()` | `ExportController.cancel()` |
| `_on_export_finished()` 中线程清理 | `ExportController._on_worker_finished()` |
| 导出中状态防护 | `ExportController.is_exporting` |

---

## 6. 数据模型变化

**无数据模型变化。**

---

## 7. 测试指引

### 单元测试 (test_export_controller.py)

| 测试类 | 用例数 | 覆盖场景 |
|--------|--------|---------|
| Init | 1 | 初始状态 |
| start_export | 4 | 正常启动、重复启动防护、参数传递、fps 使用 |
| finished 信号 | 5 | 成功/失败/取消各 emit 一次、状态重置、线程清理 |
| cancel | 4 | worker.cancel 调用、非导出状态安全、临时文件清理、输出删除 |
| cleanup | 1 | 销毁清理 |

### Mock 策略

```python
@pytest.fixture
def mock_compositor():
    compositor = MagicMock(spec=Compositor)
    compositor.fps = 30
    compositor.total_output_frames = 90
    compositor.width = 1920
    compositor.height = 1080
    return compositor

@pytest.fixture
def mock_project_session(tmp_path):
    session = MagicMock(spec=ProjectSession)
    session.load_audio.return_value = None
    session.project_dir = str(tmp_path)
    return session

@pytest.fixture
def export_settings():
    return ExportSettings(
        output_path="/tmp/test_output.mp4",
        format="mp4",
        fps=30,
    )
```

### 测试 (test_main_window.py) — 确认无回归

```python
def test_export_btn_creates_export_controller_request(qtbot):
    """点击导出按钮 → ExportController.start_export() 被调用"""

def test_export_cancel_btn_calls_controller_cancel(qtbot):
    """取消导出 → ExportController.cancel() 被调用"""

def test_export_finished_shows_notification(qtbot):
    """导出完成 → 通知弹出"""

def test_export_during_export_shows_error(qtbot):
    """导出进行中再次点击导出 → 错误提示"""
```

---

## 8. 验收标准

- [ ] `app/export_controller.py` 通过全部单元测试
- [ ] `ExportController.export_finished` 在所有路径恰好发出一次
- [ ] `ExportController.cancel()` 完整执行进程终止 + 临时文件清理 + 不完整输出删除
- [ ] `MainWindow._on_export()` 简化为调用 `ExportController.start_export()`
- [ ] `MainWindow._cancel_export()` 移除，替换为 `ExportController.cancel()`
- [ ] `MainWindow._on_export_finished()` 不再包含线程清理代码
- [ ] 导出进行中重复点击导出 → 错误提示（RuntimeError 被捕获）
- [ ] `pytest tests/test_export_controller.py -q` 全部通过
- [ ] `pytest tests/test_exporter.py -q` 全部通过（不退化）
- [ ] `pytest tests/test_main_window.py -q` 全部通过（不退化）
- [ ] 全量 `pytest -q` 0 failed

---

## 9. 边界情况与风险

| 边界/风险 | 处理策略 |
|-----------|---------|
| `start_export()` 被调用但 `project_session.load_audio()` 返回 None | audio_data=None，导出无声视频 |
| 导出完成前用户关闭窗口 | `cleanup()` 被调用 → cancel + thread quit + wait |
| `start_export()` 中 `worker.finished.connect(self._thread.quit)` 信号连接后线程立即结束 | Qt 信号机制保证槽在事件循环中执行，不存在竞态 |
| `cancel()` 在 worker 未启动时调用 | `self._worker` 存在检查 → 安全返回 |
| `_on_worker_finished` 中 `self._worker = None` 后仍有信号到达 | `finished` 只发出一次（T09 保证），之后 `self._worker.finished` 不会再次触发 |
| ExportController 是唯一 QObject | 信号机制依赖 QObject 事件循环，需确保在 GUI 线程创建 |

---

## 10. 任务级验证命令

```bash
# Step 1 (Red): 编写新测试
pytest tests/test_export_controller.py -q  # 预期 FAIL

# Step 2-3 (Green): 实现 + MainWindow 替换
pytest tests/test_export_controller.py -q  # 预期 PASS
pytest tests/test_exporter.py -q           # 预期 PASS
pytest tests/test_main_window.py -q        # 预期 PASS

# Step 4-5 (Refactor): 移除导出残留
pytest tests/ -q                           # 0 failed

# 行数检查
wc -l app/export_controller.py             # 预期 ~180 行
```

---

## 11. TDD 切片汇总

| 切片 | 步骤 | 验证 |
|------|------|------|
| 🔴 Red | Step 1 编写 ExportController 单元测试 | `pytest tests/test_export_controller.py -q` → FAIL |
| 🟢 Green | Step 2-3 实现 ExportController + MainWindow 入口替换 | `pytest tests/test_export_controller.py -q` → PASS |
| 🔵 Refactor | Step 4-5 移除 MainWindow 导出残留 | `pytest tests/ -q` → 0 failed |

---

*本文档由 @architect 基于技术方案 v1.0 §3.1.3、任务图 T12、ADR-007 §3.3、T09 鲁棒性保证和现有代码 `core/exporter.py:68-96`, `app/main_window.py:876-971` 编写。*
