# T09: export-robustness — 导出鲁棒性修复

**Project:** Recordly  
**Task ID:** T09  
**Slug:** export-robustness  
**Issue:** #36  
**类型:** fix  
**Batch:** B5  
**依赖:** T08 (#35)

---

## 1. 目标

修复导出进程鲁棒性问题，确保所有执行路径（成功、失败、取消、异常）统一清理资源且恰好发出一次 `finished` 信号：

- **F10:** `ExportWorker.run()` 用 try/except/finally 包裹，确保所有路径恰好一次 `finished` 信号
- **F11:** GIF 路径复用 `_start_stderr_reader()` 替换阻塞的 `process.stderr.read()`
- **F12:** 取消路径完整清理临时 WAV + 不完整输出文件
- **F13:** `tempfile.mktemp()` → `tempfile.mkstemp()`

---

## 2. 前置条件

- [x] T08 完成：`_export_mp4()` / `_export_gif()` 正确性已验证
- [x] T08 完成：`compositor.fps` 统一使用

---

## 3. 当前状态

### F10 — 无统一异常处理

```python
# ExportWorker.run() (line 92-96)
def run(self):
    if self._settings.format == "gif":
        self._export_gif()
    else:
        self._export_mp4()
# ❌ 如果 _export_mp4() 或 _export_gif() 中抛出未捕获异常，
#    finished 信号永远不会发出 → UI 进度框永久挂起
```

### F11 — GIF stderr 阻塞读

```python
# _export_gif() line 302: BrokenPipe 时
stderr = process.stderr.read().decode("utf-8", errors="replace")

# _export_gif() line 315: 正常完成后
stderr = process.stderr.read().decode("utf-8", errors="replace")
# ❌ process.stderr.read() 会阻塞直到 FFmpeg 关闭 stderr 管道
#    大量输出（如长 GIF 的调色板生成日志）导致缓冲区满 → 死锁
```

对比 `_export_mp4()` 已正确使用 `_start_stderr_reader()` (line 179)。

### F12 — 取消路径不清理输出文件

```python
# _export_mp4() line 187-191: 取消时
if self._cancelled:
    self._process.terminate()
    self.finished.emit(ExportResult(False, s.output_path, error="已取消"))
    return
# ❌ 不删除临时 WAV 文件 (_temp_paths)
# ❌ 不删除不完整输出文件 (s.output_path)
```

### F13 — mktemp 竞态

```python
# line 403: out_path = tempfile.mktemp(suffix='_mixed.wav')
# line 453: path = tempfile.mktemp(suffix=".wav")
# ❌ 竞态条件：文件名可被其他进程抢占
```

---

## 4. Red → Green → Refactor 实施步骤

### 🔴 RED — 编写失败测试

#### Step 1: `tests/test_exporter.py` — finished 信号测试

```python
class TestExportWorkerFinishedGuarantee:
    def test_finished_emitted_on_success(self):
        """正常导出完成 → finished 信号恰好发出一次"""
    
    def test_finished_emitted_when_ffmpeg_missing(self):
        """
        Red: FFmpeg 不存在 → _export_mp4() 中 run_async 抛 FileNotFoundError
        → 当前: 未捕获 → finished 不发出 → 测试超时
        """
    
    def test_finished_emitted_on_broken_pipe(self):
        """
        Red: 渲染过程中 stdin.write 抛 BrokenPipeError
        → 当前 MP4 路径已处理但 GIF 路径未处理
        """
    
    def test_finished_emitted_on_unexpected_exception(self):
        """
        Red: 任意未预期异常 → finished 应发出
        → 当前: 异常传播到 QThread → 无声失败
        """
    
    def test_finished_emits_exactly_once(self):
        """
        验证所有路径下 finished 恰好发出一次，不重复
        用 mock signal + counter 验证
        """
```

#### Step 2: `tests/test_exporter.py` — 取消清理测试

```python
class TestExportCancelCleanup:
    def test_cancel_removes_temp_wav_files(self):
        """取消导出后临时 WAV 文件不存在"""
    
    def test_cancel_removes_incomplete_output(self):
        """取消导出后不完整的 output_path 被删除"""
    
    def test_cancel_when_no_process_running(self):
        """进程尚未启动时取消 → 不崩溃，finished 仍发出"""
```

#### Step 3: `tests/test_exporter.py` — GIF stderr 测试

```python
def test_gif_large_stderr_does_not_deadlock():
    """
    Red: GIF 路径大量 stderr 输出 → 不死锁
    模拟: process.stderr 返回大量数据
    当前: process.stderr.read() 阻塞 → 测试超时
    """
```

**验证命令:** `pytest tests/test_exporter.py -q -k "finished or cancel or deadlock"` → 预期 FAIL/TIMEOUT

---

### 🟢 GREEN — 最小实现

#### Step 4: `core/exporter.py` — F10: `run()` 统一 try/except/finally

**文件:** `core/exporter.py`  
**方法:** `run()` (line 92-96) — 完全重写

```python
def run(self):
    """所有路径恰好发出一次 finished 信号。"""
    s = self._settings
    result = None
    try:
        if s.format == "gif":
            result = self._export_gif()
        else:
            result = self._export_mp4()
    except Exception as exc:
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                pass
        result = ExportResult(False, s.output_path, error=f"导出异常: {exc}")
    finally:
        if result is not None:
            self.finished.emit(result)
        else:
            self.finished.emit(ExportResult(
                False, s.output_path, error="导出意外终止"))
```

**对应修改 `_export_mp4()` 和 `_export_gif()` 返回 `ExportResult` 而非直接 emit:**

```python
def _export_mp4(self) -> ExportResult:
    """返回 ExportResult，由 run() 统一 emit。"""
    ...
    # 所有 self.finished.emit(...) 替换为 return ExportResult(...)
    # 所有 return（无声 finished）替换为 return ExportResult(...)
```

**影响范围:** `_export_mp4()` 中所有 5 处 `self.finished.emit(...)` + `_export_gif()` 中所有 3 处 `self.finished.emit(...)`。

---

#### Step 5: `core/exporter.py` — F11: GIF 路径 stderr drain 统一

**文件:** `core/exporter.py`  
**方法:** `_export_gif()` — 添加 `_start_stderr_reader()` 调用，移除阻塞 `process.stderr.read()`

```python
def _export_gif(self) -> ExportResult:
    ...
    process = self._build_gif_output(w, h).run_async(
        pipe_stdin=True, pipe_stderr=True)
    self._process = process
    
    # 新增: 后台线程消费 stderr
    stderr_thread, stderr_chunks = _start_stderr_reader(process)
    
    try:
        for i, frame in enumerate(c.render_all()):
            if self._cancelled:
                process.terminate()
                return ExportResult(False, s.output_path, error="已取消")
            ...
            try:
                process.stdin.write(frame.tobytes())
            except BrokenPipeError:
                process.stdin.close()
                stderr_thread.join(timeout=3)
                stderr_text = "".join(stderr_chunks).strip()
                return ExportResult(False, s.output_path,
                    error=f"FFmpeg GIF 管道断开: {stderr_text}")
        
        process.stdin.close()
        returncode = process.wait()
        stderr_thread.join(timeout=5)
        stderr_text = "".join(stderr_chunks).strip()
        self._process = None
        
        if returncode != 0 or not os.path.exists(s.output_path):
            return ExportResult(False, s.output_path,
                error=f"FFmpeg GIF 导出失败 (exit={returncode}):\n{stderr_text}")
        
        return ExportResult(success=True, path=s.output_path,
            size_bytes=os.path.getsize(s.output_path),
            duration=total / c.fps)
    finally:
        # 确保 stderr 线程结束
        if stderr_thread and stderr_thread.is_alive():
            stderr_thread.join(timeout=3)
```

---

#### Step 6: `core/exporter.py` — F12: 取消路径完整清理

**统一清理逻辑在 `run()` 的 `finally` 块中:**

```python
def run(self):
    s = self._settings
    process = None
    temp_paths = []
    result = None
    try:
        # ... 设置 process, temp_paths ...
    except Exception as exc:
        result = ExportResult(False, s.output_path, error=f"导出异常: {exc}")
    finally:
        # 统一进程终止
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        
        # 统一清理临时文件
        for p in getattr(self, '_temp_paths', []):
            try:
                os.remove(p)
            except OSError:
                pass
        
        # 取消时删除不完整输出
        if self._cancelled and os.path.exists(s.output_path):
            try:
                os.remove(s.output_path)
            except OSError:
                pass
        
        # 确保恰好一次 finished
        if not hasattr(self, '_finished_emitted'):
            self._finished_emitted = True
            self.finished.emit(result or ExportResult(
                False, s.output_path, error="导出意外终止"))
```

**`_export_mp4()` 和 `_export_gif()` 中将临时路径收集到 `self._temp_paths`:**

```python
# _export_mp4() 开头:
self._temp_paths = []

# 每处创建临时 WAV 后:
self._temp_paths.append(out_path)
```

---

#### Step 7: `core/exporter.py` — F13: mktemp → mkstemp

**文件:** `core/exporter.py`  
**位置:** line 403 (`_build_audio_filtergraph`) 和 line 453 (`_save_temp_wav`)

```python
# line 403 — 当前:
out_path = tempfile.mktemp(suffix='_mixed.wav')

# 修改为:
fd, out_path = tempfile.mkstemp(suffix='_mixed.wav')
os.close(fd)  # 立即关闭 fd，ffmpeg 会自己打开写入

# line 453 — 当前:
path = tempfile.mktemp(suffix=".wav")

# 修改为:
fd, path = tempfile.mkstemp(suffix=".wav")
os.close(fd)  # wave.open 会重新打开
```

---

### 🔵 REFACTOR — 无行为变更的清理

#### Step 8: 统一 stderr 错误文本获取

**文件:** `core/exporter.py`

将 `_export_mp4()` 中多处 `"".join(stderr_chunks).strip()` 提取为一个 helper：

```python
def _get_stderr_text(self, stderr_chunks: list[str]) -> str:
    text = "".join(stderr_chunks).strip()
    return text or "(ffmpeg 无 stderr 输出)"
```

MP4 和 GIF 路径均使用此 helper。

---

#### Step 9: `_export_mp4()` 也改为返回 `ExportResult`

确保 `_export_mp4()` 中所有 5 处 `self.finished.emit(...)` 改为 `return ExportResult(...)`，移除 `_export_mp4()` 内的所有 `self.finished.emit` 调用。

---

## 5. 接口/契约

### ExportWorker.run() 契约

```
run() 保证:
  - finished 信号在所有路径恰好发出一次
  - 进程终止后所有临时文件被删除
  - _cancelled=True 时输出文件被删除
  - 任何异常都不会导致 finished 信号不发出
```

### 临时文件生命周期

```
创建: tempfile.mkstemp()（安全，无竞态）
使用: ExportWorker 内部或 ffmpeg 子进程
清理: run() finally 块中统一 os.remove()
      + 取消时 os.remove(output_path)
```

---

## 6. 数据模型变化

**无数据模型变化。**

---

## 7. 测试指引

### 单元测试 (test_exporter.py) — 新增 test class

```python
class TestExportWorkerRobustness:
    """F10: finished 信号保证"""
    def test_finished_emitted_on_ffmpeg_not_found():
        """mock subprocess.Popen 抛 FileNotFoundError → finished 信号发出"""
    
    def test_finished_emitted_on_broken_pipe_gif():
        """GIF 路径 BrokenPipe → finished 信号发出且不含阻塞 stderr.read"""
    
    def test_finished_emitted_on_unexpected_exception():
        """mock c.render_all 抛 RuntimeError → finished 信号发出"""
    
    def test_finished_emits_exactly_once_on_success():
        """正常路径 finished 恰好一次"""
    
    def test_finished_emits_exactly_once_on_failure():
        """失败路径 finished 恰好一次"""

class TestExportCancelCleanup:
    """F12: 取消清理"""
    def test_cancel_cleans_temp_wav():
        """取消后临时 WAV 文件被删除"""
    
    def test_cancel_cleans_incomplete_output():
        """取消后不完整输出文件被删除"""
    
    def test_cancel_no_process_is_safe():
        """进程未启动时取消 → 不崩溃"""

class TestStderrDrain:
    """F11: GIF stderr"""
    def test_gif_uses_stderr_reader_not_blocking_read():
        """验证 _export_gif 调用 _start_stderr_reader 而非 process.stderr.read"""

class TestMkstemp:
    """F13: mktemp → mkstemp"""
    def test_no_mktemp_in_exporter():
        """grep 确认 exporter.py 中无 tempfile.mktemp 调用"""
```

### 测试 mock 策略

```python
# Mock ffmpeg pipeline
@pytest.fixture
def mock_ffmpeg_process():
    """返回 mock subprocess.Popen 对象，support stdin.write, poll, wait, terminate"""
    with patch('subprocess.Popen') as mock:
        process = MagicMock()
        process.poll.return_value = None
        process.stdin = MagicMock()
        process.stderr = io.BytesIO(b"mock stderr output\n")
        mock.return_value = process
        yield mock, process
```

---

## 8. 验收标准

- [ ] FFmpeg 不存在时 → worker 发出 `finished(ExportResult(False, ...))`，线程退出，UI 不挂死
- [ ] 渲染过程中 BrokenPipe → finished 信号发出，临时文件清理完整
- [ ] 任意未预期异常 → finished 信号发出，不挂死 UI
- [ ] 所有路径 finished 信号恰好发出一次
- [ ] GIF 大量 stderr 输出 → 不死锁，导出正常完成
- [ ] GIF 导出使用 `_start_stderr_reader()`，不存在 `process.stderr.read()` 阻塞调用
- [ ] 取消导出 → 无残留 FFmpeg 进程、临时 WAV、不完整输出文件
- [ ] `core/exporter.py` 中无 `tempfile.mktemp` 引用
- [ ] `pytest tests/test_exporter.py -q` 全部通过
- [ ] 全量 `pytest -q` 0 failed

---

## 9. 边界情况与风险

| 边界/风险 | 处理策略 |
|-----------|---------|
| `run()` finally 块抛异常 | finally 块本身不抛异常（所有清理操作 try/except 包裹） |
| `process.terminate()` 后 `wait(timeout=5)` 超时 | `process.kill()` fallback |
| `stderr_thread.join(timeout=3)` 超时 | 不阻塞主流程，thread 是 daemon |
| `os.remove()` 失败（权限/不存在） | `except OSError: pass` 吞掉 |
| `_finished_emitted` 标记竞态 | ExportWorker 在 QThread 中单线程运行，无竞态 |
| 现有导出测试依赖 `self.finished.emit` 在 `_export_mp4`/`_export_gif` 中 | T08 已覆盖这些测试；T09 重构 `emit` 位置后需同步更新测试 mock |
| GIF 和 MP4 共享 `_temp_paths` | 在各自方法中设为 `self._temp_paths = []`，方法返回前填充 |

---

## 10. 任务级验证命令

```bash
# Step 1-3 (Red): 确认新增测试失败/超时
pytest tests/test_exporter.py -q -k "finished or cancel or mkstemp" --timeout=30

# Step 4-7 (Green): 实现后验证
pytest tests/test_exporter.py -q

# Step 8-9 (Refactor): 全量回归
pytest tests/ -q

# 手动验收
python main.py
# 1. 导出 → 取消 → 检查 output_path 和 /tmp 无残留
# 2. 导出长 GIF → 确认不挂死
# 3. 模拟 FFmpeg 不存在 → 确认错误提示出现
```

---

## 11. TDD 切片汇总

| 切片 | 步骤 | 验证 |
|------|------|------|
| 🔴 Red | Step 1-3 编写失败测试 | `pytest -q -k "finished or cancel"` → FAIL/TIMEOUT |
| 🟢 Green | Step 4-7 实现 F10+F11+F12+F13 | `pytest -q -k "finished or cancel or mkstemp"` → PASS |
| 🔵 Refactor | Step 8-9 统一 stderr helper + emit 收敛 | `pytest tests/ -q` → 0 failed |

---

*本文档由 @architect 基于技术方案 v1.0 §3.2.2、任务图 T09、ADR-007 和现有代码 `core/exporter.py:92-96,302,315,403,453` 编写。*
