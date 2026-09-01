# 开发文档: T14 — logging 统一

- **Project:** Recordly 核心稳定性与架构治理
- **Task ID:** T14
- **Slug:** `logging-unified`
- **Issue:** #41
- **类型:** polish
- **Batch:** B9
- **依赖:** T13 (#40)
- **预计工时:** 1.5h
- **涉及文件:** 4

---

## 1. 目标

将 Recordly 所有 debug/stderr 输出统一为 Python `logging` 模块。默认 WARNING 级别，`RECORDLY_DEBUG=1` 环境变量启用 DEBUG 级别输出到 stderr。同时移除 `__import__` 动态导入。

**前置条件（T13 已完成）：**
- MainWindow 已缩减到 ≤800 行
- 全量测试通过，无架构冲突

**关键约束：**
- 默认 WARNING 级别（静默模式，与当前 `_DEBUG=True` 的 exporter 相反）
- `RECORDLY_DEBUG=1` 时 DEBUG 输出到 stderr
- 不输出完整用户内容或音频数据到日志
- 移除 `_DEBUG` 常量和 `__import__` 动态导入

---

## 2. 当前状态审计

| 文件 | 当前日志方式 | 问题 |
|------|------------|------|
| `main.py` | 无 logging 配置 | 无统一入口 |
| `core/exporter.py:20` | `_DEBUG = True` 常量 | 永久开启 debug |
| `core/exporter.py:32-33` | `if _DEBUG: print(file=sys.stderr)` | 条件式 stderr |
| `core/exporter.py:183-184` | `print(file=sys.stderr)` | 无条件 stderr |
| `core/exporter.py:197-198` | `if _DEBUG: print(file=sys.stderr)` | 条件式 stderr |
| `core/exporter.py:409` | `print(file=sys.stderr)` (无线程安全) | 非 logger 输出 |
| `core/compositor.py:364-365` | `print(file=sys.stderr)` | 黑帧兜底无条件 stderr |
| `core/compositor.py:438` | `__import__('time').perf_counter()` | 动态导入 |
| `core/compositor.py:440-446` | `__import__('sys').stderr.write` | 动态导入 + 每 60 帧无条件输出 |
| `core/recorder.py:69,79` | `print()` 用到 stdout | 无条件 stdout |

---

## 3. 实施步骤（Red → Green → Refactor）

### 步骤 1: `main.py` — 添加 logging 基础设施（Green）

**目标文件:** `main.py`

**操作:**

在 `import` 区域添加 `logging` 和 `os` 导入（`os` 大概率已存在），在 `QApplication` 创建之前添加 `logging.basicConfig` 配置：

```python
import logging
import os
import sys

# 在 app = QApplication(sys.argv) 之前
_log_level = logging.DEBUG if os.environ.get("RECORDLY_DEBUG") == "1" else logging.WARNING
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
```

**要点:**
- `stream=sys.stderr` 确保日志输出到 stderr（不与 stdout 混淆；现有 print 使用 `file=sys.stderr`）
- 格式包含时间、模块名、级别，方便诊断
- 不输出完整帧数据或音频数据到日志（`format` 不含大体积上下文）

**验证:**
```bash
# 默认不输出 debug
.venv/bin/python -c "import logging; logging.getLogger('test').debug('hidden')"

# RECORDLY_DEBUG=1 时输出 debug
RECORDLY_DEBUG=1 .venv/bin/python -c "import logging; logging.getLogger('test').debug('visible')"
```

---

### 步骤 2: `core/exporter.py` — 替换 _DEBUG 和 print（Green）

**目标文件:** `core/exporter.py`

**操作清单:**

#### 2a. 添加模块 logger

在文件顶部（import 之后，`_DEBUG` 之前）:

```python
import logging
logger = logging.getLogger(__name__)
```

#### 2b. 删除 `_DEBUG = True`（行 20）

直接删除该行。

#### 2c. 替换 `_start_stderr_reader` 中的 stderr 输出

行 32-33（当前）:
```python
if _DEBUG:
    print(f"[ffmpeg] {text.rstrip()}", file=sys.stderr, flush=True)
```

替换为:
```python
logger.debug("[ffmpeg] %s", text.rstrip())
```

> **理由:** ffmpeg stderr 是大体积数据（编码进度、参数等）。在 DEBUG 级别输出，默认 WARNING 时静默。

#### 2d. 替换 run() 中的 print 语句

行 183-184（无条件 stderr）:
```python
print(f"[exporter] ffmpeg {' '.join(cmd)}", file=sys.stderr, flush=True)
print(f"[exporter] 帧数={total} 尺寸={w}x{h} fps={s.fps}", file=sys.stderr, flush=True)
```

替换为:
```python
logger.debug("[exporter] ffmpeg %s", " ".join(cmd))
logger.debug("[exporter] 帧数=%d 尺寸=%dx%d fps=%d", total, w, h, s.fps)
```

行 197-198（条件式 stderr）:
```python
if i == 0 and _DEBUG:
    print(f"[exporter] 首帧 {frame.size} {frame.mode} {len(data)} bytes", file=sys.stderr, flush=True)
```

替换为:
```python
if i == 0:
    logger.debug("[exporter] 首帧 %s %s %d bytes", frame.size, frame.mode, len(data))
```

> **注意:** 移除 `_DEBUG` 条件后，`i == 0` 在 DEBUG 级别下会输出一条日志。默认 WARNING 时静默。

#### 2e. 替换音频混合失败的 print

行 409:
```python
print(f"[exporter] 音频混合失败: {stderr.strip()}")
```

替换为:
```python
logger.error("[exporter] 音频混合失败: %s", stderr.strip() if stderr else "unknown")
```

> **理由:** 音频混合失败是 Error 级别，默认 WARNING 时可见。

#### 2f. 移除 `sys` import 中的 stderr 引用检查

替换完成后检查 `sys` 是否仍被使用。如果 `sys` 仅在 `print(file=sys.stderr)` 中使用，可移除 `import sys`（但大概率其他代码需要 `sys`，不做此清理）。

**不修改的日志语句：**
- `core/audio_capture.py:62` 的 `print(f"[mic] {status}", file=sys.stderr)` **不在本任务范围**。`audio_capture.py` 独立的子进程 stderr 输出不经过主进程 logger。留待后续统一。

---

### 步骤 3: `core/compositor.py` — 替换 print 和 __import__（Green）

**目标文件:** `core/compositor.py`

**操作清单:**

#### 3a. 添加模块 logger

```python
import logging
logger = logging.getLogger(__name__)
```

#### 3b. 替换黑帧兜底输出（行 364-365）

当前:
```python
print(f"[compositor] 帧 {frame.index} 解码失败，使用黑帧兜底",
      file=sys.stderr, flush=True)
```

替换为:
```python
logger.warning("[compositor] 帧 %d 解码失败，使用黑帧兜底", frame.index)
```

> **理由:** 解码失败是 Warning 级别，默认可见。使用 `%d` 避免 `frame.index` 的 f-string 开销。

#### 3c. 替换 FPS debug 输出和 __import__（行 438-446）

当前:
```python
if self._fps_t0 is None:
    self._fps_t0 = __import__('time').perf_counter()
...
if frame_count > 0 and frame_count % 60 == 0:
    elapsed = __import__('time').perf_counter() - self._fps_t0
    self._fps_t0 = __import__('time').perf_counter()
    __import__('sys').stderr.write(
        f"FPS={60/elapsed:.1f} (t={line_time:.3f})\n")
    __import__('sys').stderr.flush()
```

**操作:**

1. 文件顶部添加 `import time`（替代 `__import__('time')`）
2. 将 `__import__('time').perf_counter()` 替换为 `time.perf_counter()`
3. 将 stderr 输出替换为 `logger.debug`:

```python
if self._fps_t0 is None:
    self._fps_t0 = time.perf_counter()
...
if frame_count > 0 and frame_count % 60 == 0:
    elapsed = time.perf_counter() - self._fps_t0
    self._fps_t0 = time.perf_counter()
    logger.debug("FPS=%.1f (t=%.3f)", 60 / elapsed, line_time)
```

> **注意:** FPS 统计只在 DEBUG 级别输出，默认 WARNING 时静默。`line_time` 变量需确认在当前作用域中可用；如果不能，使用 `time.perf_counter()` 替代。

**验证:** 确认 `time` 已在文件顶部 import 或已通过其他 import 引入。搜索 `import time` 是否存在。

---

### 步骤 4: `core/recorder.py` — 替换 print（Green）

**目标文件:** `core/recorder.py`

**操作:**

#### 4a. 添加模块 logger

```python
import logging
logger = logging.getLogger(__name__)
```

#### 4b. 替换行 69 和 79 的 print

行 69:
```python
print("[recorder] 录制开始")
```
替换为:
```python
logger.info("[recorder] 录制开始")
```

行 79:
```python
print(f"[recorder] 录制结束")
```
替换为:
```python
logger.info("[recorder] 录制结束")
```

> **理由:** 录制开始/结束是用户可感知的动作，使用 INFO 级别。但注意：默认 WARNING 时不会显示。如果不希望默认隐藏（影响用户体验），可提升为 WARNING。但根据规格"默认 WARNING，仅 Warning/Error 输出"，录制开始/结束不是 Warning/Error，保持 INFO 是正确的。用户通过 `RECORDLY_DEBUG=1` 可看到。

---

### 步骤 5: 验证（Green — 回归测试 + 手动验证）

**5a. 全量测试:**
```bash
.venv/bin/python -m pytest -q
```

**5b. 验证 _DEBUG 不存在:**
```bash
grep -n "_DEBUG" core/exporter.py
# 应返回空（或仅在注释中）
```

**5c. 验证 __import__ 不存在:**
```bash
grep -rn "__import__" core/exporter.py core/compositor.py
# 应返回空（排除注释）
```

**5d. 验证 RECORDLY_DEBUG 行为:**
```bash
# 默认不输出 debug
.venv/bin/python main.py 2>&1 | head -5
# 不应看到 FPS=... 或 [exporter] 等 debug 输出

# RECORDLY_DEBUG=1 时输出 debug
RECORDLY_DEBUG=1 .venv/bin/python main.py 2>&1 | grep -c "DEBUG"
# 应看到 DEBUG 日志
```

**5e. 磁盘写入验证:**
```bash
# 日志不写入文件，只输出到 stderr
# 项目目录下不应有 .log 文件
find ~/Recordly/projects/ -name "*.log" 2>/dev/null
# 应返回空
```

---

## 4. 接口/契约

### 日志级别约定

| 级别 | 触发条件 | 示例 |
|------|---------|------|
| `DEBUG` | FPS 统计、ffmpeg stderr、首帧详情、录制状态变更 | `RECORDLY_DEBUG=1` 时可见 |
| `INFO` | 录制开始/结束 | 默认隐藏（可通过 `RECORDLY_DEBUG=1` 或修改 level 看到） |
| `WARNING` | 帧解码失败兜底 | 默认可见 |
| `ERROR` | 音频混合失败 | 默认可见 |

### 环境变量

```
RECORDLY_DEBUG=1  → logging.basicConfig(level=DEBUG, stream=sys.stderr)
RECORDLY_DEBUG 未设置或 != "1" → logging.basicConfig(level=WARNING, stream=sys.stderr)
```

### 日志格式

```
HH:MM:SS [module_name] LEVEL: message
```

---

## 5. 单元/集成测试指引

### 可选的单元测试

本任务为纯替换任务（不做行为变更），不需要新增大量测试。但以下场景值得覆盖：

**`tests/test_logging.py`（新增，可选）：**
```python
import logging
import os
import pytest
from unittest.mock import patch

def test_logging_default_level():
    """验证默认 WARNING 级别"""
    with patch.dict(os.environ, {}, clear=True):
        import importlib
        # 重新加载 main 模块以重置 logging 配置
        ...

def test_logging_debug_level():
    """验证 RECORDLY_DEBUG=1 时 DEBUG 级别"""
    with patch.dict(os.environ, {"RECORDLY_DEBUG": "1"}):
        ...
```

**注意:** 由于 `logging.basicConfig` 是全局单次调用，测试中对 logging 级别的验证较为棘手。如时间不足，可手验证代。

---

## 6. 完整验收标准

- [ ] `RECORDLY_DEBUG=1 .venv/bin/python main.py 2>&1 | grep "DEBUG"` 有输出
- [ ] `.venv/bin/python main.py 2>&1 | grep "DEBUG"` 无输出（默认 WARNING，静默）
- [ ] `grep "_DEBUG" core/exporter.py` 无结果（`_DEBUG` 常量已移除）
- [ ] `grep -rn "__import__" core/exporter.py core/compositor.py` 无结果（排除注释）
- [ ] `grep -n "print(file=sys.stderr)" core/exporter.py` 无结果
- [ ] `grep -n "print.*stderr" core/compositor.py` 无结果（排除异常处理中的 print）
- [ ] `grep -n "print" core/recorder.py` 无结果（排除注释）
- [ ] `grep "import logging" main.py core/exporter.py core/compositor.py core/recorder.py` 4 个文件都包含
- [ ] `pytest -q` 全量通过
- [ ] 不输出完整用户帧数据或音频内容到日志
- [ ] 不在项目目录创建 .log 文件

---

## 7. 边界情况和风险

### 边界情况

1. **`RECORDLY_DEBUG=""`** 或 `RECORDLY_DEBUG=0` → 按 WARNING 处理（只有 `"1"` 触发 DEBUG）
2. **`logging.basicConfig` 重复调用** → 第二次调用被忽略（Python logging 特性，不影响功能）
3. **Exporter 的 stderr reader 线程** → logger 是线程安全的（Python logging 模块内置锁），不影响并发

### 风险

| 风险 | 缓解 |
|------|------|
| `core/effects.py:86` 的 `print()` 和 `core/audio_capture.py:62` 的 stderr print 未纳入范围 | 这些是独立模块/子进程的输出，不经过主进程 logger。后续统一时处理 |
| 移除 `__import__` 后 `time` 模块未 import | 步骤 3c 中检查 `import time` 是否存在 |
| `logger.debug` 中 f-string 改为 `%` 格式后变量作用域问题 | 逐项确认 `line_time`、`frame.index` 等变量可用 |
| 日志中包含 `crop_x` 等帧数据 | 只记录帧计数和尺寸，不记录像素数据 |

---

## 8. 任务级验证命令

```bash
# 1. RECORDLY_DEBUG=1 验证
RECORDLY_DEBUG=1 .venv/bin/python main.py 2>&1 | head -20
# 应看到 DEBUG 级别日志（含模块名和时间戳）

# 2. 默认静默验证
.venv/bin/python -c "
import os
# 清除环境变量
os.environ.pop('RECORDLY_DEBUG', None)
import logging
logging.basicConfig(level=logging.WARNING, format='%(name)s: %(message)s')
logger = logging.getLogger('test')
logger.debug('should_not_appear')
logger.warning('should_appear')
" 2>&1
# 只应看到 'should_appear'，不应看到 'should_not_appear'

# 3. __import__ 消除验证
! grep -rn "__import__" core/exporter.py core/compositor.py

# 4. _DEBUG 消除验证
! grep "_DEBUG" core/exporter.py

# 5. 全量测试
.venv/bin/python -m pytest -q
```

---

## 9. 技术方案参考

- 技术方案 §3.2.2: `core/exporter.py` — `_DEBUG → logging`
- 技术方案 §3.2.4: `core/compositor.py` — `print → logger.debug`
- 技术方案 §3.2.8: `main.py` — `logging.basicConfig`
- 任务图 T14: `logging-unified` Batch B9
- PRD F21, F22
