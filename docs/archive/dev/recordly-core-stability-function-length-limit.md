# 开发文档: T17 — 函数长度限制交叉验证

- **Project:** Recordly 核心稳定性与架构治理
- **Task ID:** T17
- **Slug:** `function-length-limit`
- **Issue:** #44
- **类型:** verify
- **Batch:** B11
- **依赖:** T15 (#42), T16 (#43)
- **预计工时:** 2h
- **涉及文件:** ≤10（交叉验证，不新增文件）

---

## 1. 目标

验证本轮修改的所有新增/修改函数不超过 50 行，对超标的函数进行拆分重构。本任务为交叉验证 pass，不引入新功能。

**前置条件（T15/T16 已完成）：**
- `resources/style.qss` 已提取，`main.py` 仅剩 imports + `_load_stylesheet()` + `main()`
- `core/compositor.py` 和 `core/camera.py` 的光标插值已使用 bisect + 缓存
- T14 logging 已统一

**关键约束：**
- 只检查本轮新增/修改的函数（不在本轮范围的函数不本次处理）
- 拆分不影响既有测试通过
- 语义内聚优先于机械式拆分

---

## 2. 验证范围

### 本轮修改的文件清单（按 Batch 汇总）

| Batch | 任务 | 文件 | 变更类型 |
|-------|------|------|---------|
| B8 | T13 | `app/main_window.py` | 修改（1245 → ≤800） |
| B9 | T14 | `main.py` | 修改 |
| B9 | T14 | `core/exporter.py` | 修改 |
| B9 | T14 | `core/compositor.py` | 修改 |
| B9 | T14 | `core/recorder.py` | 修改 |
| B10 | T15 | `main.py`, `resources/style.qss` (新) | QSS 提取 |
| B10 | T16 | `core/compositor.py` | 光标优化 |
| B10 | T16 | `core/camera.py` | 光标优化 |
| B11 | T17 | 以上所有文件 | **交叉验证本 pass** |

### 不在验证范围的文件

以下文件虽在本轮修改，但只做微调（单行/数行替换），函数长度无明显变化，跳过检查：

| 排除文件 | 原因 |
|---------|------|
| `resources/style.qss` | 非 Python 文件，无函数概念 |
| `tests/*` | 测试函数长度不强制 ≤50 行（可酌情放宽） |

### 新增文件（本开发文档之外）

| 文件 | 预计函数数 | 预计超标风险 |
|------|-----------|-------------|
| `app/project_session.py` | ~8 个方法 | 低（每个方法职责单一） |
| `app/recording_controller.py` | ~8 个方法 | 低 |
| `app/export_controller.py` | ~6 个方法 | 低 |

---

## 3. 实施步骤

### 步骤 1: 基线扫描 — 识别超标函数

**1a. 使用 pylint/radon 或手动脚本扫描:**

```bash
# 方法 1: 使用 Python ast 模块扫描函数行数
.venv/bin/python -c "
import ast
import sys

files = [
    'app/main_window.py',
    'app/project_session.py',
    'app/recording_controller.py',
    'app/export_controller.py',
    'main.py',
    'core/exporter.py',
    'core/compositor.py',
    'core/camera.py',
    'core/recorder.py',
]

for f in files:
    try:
        with open(f) as fp:
            source = fp.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = node.end_lineno or 0
                start = node.lineno
                length = end - start + 1
                if length > 50:
                    print(f'OVER: {f}:{start}: {node.name} ({length} lines)')
    except Exception as e:
        print(f'ERROR: {f}: {e}')
"
```

**1b. 输出示例:**

```
OVER: app/main_window.py:xxx: _on_export (72 lines)
OVER: app/main_window.py:yyy: _populate_timeline (55 lines)
OVER: core/exporter.py:zzz: run (80 lines)
```

**1c. 记录基线:** 列出所有超过 50 行的本轮修改函数，标记文件路径、行号、函数名。

---

### 步骤 2: 超标函数拆分策略

#### 原则

1. **语义内聚优先:** 不机械式地按行数切割，按逻辑边界拆分
2. **提取 helper 方法:** 将可命名的逻辑块提取为私有方法
3. **不引入新类:** 提取方法到当前类，不创建新类（除非逻辑跨多个方法且明显独立）
4. **保持测试通过:** 每拆分一个函数后运行相关测试

#### 常见拆分模式

| 场景 | 策略 | 示例 |
|------|------|------|
| try/except 块过大 | 提取 except 处理逻辑为 `_handle_xxx_error()` | `ExportWorker.run()` 的异常处理 |
| if-elif-else 链过长 | 提取每个分支为独立方法 | 状态机切换逻辑 |
| 数据收集 → 写入两个阶段 | 拆分为 `_collect_xxx_data()` + `_save_xxx_data()` | 录制数据收集 |
| UI 控件的批量配置 | 提取 `_setup_xxx()` 方法（如按钮、菜单） | 工具栏/菜单初始化 |
| 信号连接过多 | 提取 `_connect_xxx_signals()` 方法 | MainWindow.__init__ 信号绑定 |

#### 拆分检查清单

对每个被拆分的函数:
1. 原始函数是否可读（拆后调用链是否清晰）
2. 提取的方法名称是否自解释
3. 参数是否合理（不超过 5 个，否则考虑封装为 dataclass）
4. 拆分后原函数是否仍完整通过原有测试
5. 拆分是否引入了循环调用

---

### 步骤 3: 逐文件拆分实施

#### 3a. `app/main_window.py` — 最高风险

T13 目标是从 1245 行缩减到 ≤800 行，其中很多大函数（如 `__init__`）在 T10-T13 的委托过程中已被削减。剩余大函数可能包括:

| 潜在超标函数 | 预期拆分策略 |
|-------------|------------|
| `__init__` | 提取 `_init_controllers()`、`_init_ui_components()`、`_connect_signals()` |
| `_on_export` | 已在 T12 委托 ExportController，本函数应是薄调用层 |
| `_populate_timeline` | 提取 `_create_audio_tracks()`、`_create_video_tracks()` |
| `_on_open_project` | 提取 `_validate_project_session()`、`_load_into_compositor()` |
| `_collect_project_state` | 提取 `_collect_compositor_state()`、`_collect_timeline_state()` |

**示例拆分（`_populate_timeline`）：**

```python
def _populate_timeline(self):
    """填充时间线轨道。"""
    self._timeline.clear()
    self._populate_audio_tracks()
    self._populate_video_tracks()
    self._populate_cursor_tracks()

def _populate_audio_tracks(self):
    """创建麦克风和系统音频轨道。"""
    if not self._recorded_data:
        return
    audio = self._recorded_data.get("audio", {})
    # ... （原 _populate_timeline 的音频部分）
```

#### 3b. `core/exporter.py` — 中风险

**ExportWorker.run()** 当前约 80 行（含 try/except/finally）。T09 的鲁棒性重构可能已拆分，检查是否可以进一步提取:

```python
def run(self):
    """导出入口。"""
    self._cancelled = False
    try:
        result = self._execute_export()
    except Exception as exc:
        result = ExportResult(False, self.settings.output_path, error=f"导出异常: {exc}")
    finally:
        self._cleanup_resources(result)
        self.finished.emit(result)

def _execute_export(self) -> ExportResult:
    """核心导出逻辑（MP4/GIF 分发）。"""
    ...

def _cleanup_resources(self, result: ExportResult) -> None:
    """统一资源清理（进程终止、临时文件删除、不完整输出删除）。"""
    ...
```

#### 3c. `core/compositor.py` — 低风险

T16 修改涉及 `_interpolate_cursor_raw`（委托或删除）、`_interpolate_cursor`（缓存优化）。这些方法原本较简短，修改后不会超 50 行。

#### 3d. `core/camera.py` — 低风险

T16 修改涉及 `_interpolate`（重写为 bisect），该方法原本约 20 行，重写后约 15 行，不超 50 行。

#### 3e. `main.py` — 极低风险

T14 添加了 `_load_stylesheet()`（约 12 行），T15 删除了 228 行的 `DARK_STYLESHEET`。总代码行数约 30 行，无 50 行函数。

#### 3f. `core/recorder.py` — 极低风险

T14 仅替换 `print` 为 `logger.info`。原始函数长度未变。

---

### 步骤 4: 验证（Green — 全量回归）

```bash
# 1. 确认无超过 50 行的本轮修改函数
.venv/bin/python -c "..."   # 步骤 1a 的扫描脚本

# 2. 全量测试
.venv/bin/python -m pytest -q

# 3. 确保拆分不影响覆盖率（可选）
.venv/bin/python -m pytest --cov=app --cov=core --cov-report=term-missing
```

---

## 4. 接口/契约

本任务为验证 pass，不新增或修改公开接口。拆分的方法均为私有方法（`_` 前缀）。

### 拆分规范

- 提取的方法命名: `_verb_noun` 格式（如 `_execute_export`、`_cleanup_resources`）
- 参数数量: ≤5 个
- 不修改方法签名（公开方法的外部调用者不受影响）
- 如拆出方法需返回多个值，返回 tuple 而非 dict（性能一致，类型更明确）

---

## 5. 完整验收标准

- [ ] 本轮所有新增函数 ≤50 行
- [ ] 本轮所有修改函数 ≤50 行
- [ ] 拆分重构不影响 `pytest -q` 全量通过
- [ ] 无新引入的死代码（拆分后原函数中无多余 pass/return）
- [ ] 提取的私有方法有合理的 docstring 或名称自解释
- [ ] 最终审查无违规

**验收命令:**
```bash
# 扫描本轮修改文件中的超标函数
for f in app/main_window.py app/project_session.py app/recording_controller.py app/export_controller.py main.py core/exporter.py core/compositor.py core/camera.py core/recorder.py; do
    [ -f "$f" ] || continue
    echo "=== $f ==="
    .venv/bin/python -c "
import ast
with open('$f') as fp: tree = ast.parse(fp.read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        length = (node.end_lineno or 0) - node.lineno + 1
        if length > 50:
            print(f'  OVER: {node.name} ({length} lines)')
"
done

# 全量测试
.venv/bin/python -m pytest -q
```

---

## 6. 边界情况和风险

### 边界情况

1. **T10-T12 新增的 Controller 文件函数已超 50 行** → 如果 `project_session.py`、`recording_controller.py`、`export_controller.py` 中的方法超过 50 行，需要回头通知 T10/T11/T12 修复（但本任务是交叉验证 pass，T17 执行者可以自行拆分）

2. **拆分后函数调用栈加深** → 嵌套 2-3 层可接受（`run()` → `_execute_export()` → `_build_ffmpeg_command()`），超过 3 层需考虑合并

3. **拆分函数的参数传递过多** → 如果 `_collect_compositor_state` 需要 6+ 个参数，考虑创建轻量 dataclass 或 namedtuple 封装

### 风险

| 风险 | 缓解 |
|------|------|
| 拆分 `ExportWorker.run()` 破坏 T09 的鲁棒性契约 | 拆分后运行 T09 的鲁棒性测试套件：取消/FFmpeg 不存在/BrokenPipe/异常 4 路径 |
| 拆分 MainWindow 方法导致信号连接断裂 | 拆分仅在 MainWindow 内部提取私有方法，不改变公开方法签名，信号连接不受影响 |
| AST 扫描遗漏 lambda 和嵌套函数 | 手动复查扫描结果 |
| 拆分过度导致函数碎片化 | 只拆分明显超过 50 行的函数，40-50 行的函数不做强制拆分 |

---

## 7. 任务级验证命令

```bash
# 完整验证脚本
#!/bin/bash
set -e

echo "=== 步骤 1: 函数长度扫描 ==="
OVERFLOW=0
for f in app/main_window.py app/project_session.py app/recording_controller.py app/export_controller.py main.py core/exporter.py core/compositor.py core/camera.py core/recorder.py; do
    [ -f "$f" ] || continue
    RESULT=$(.venv/bin/python -c "
import ast
with open('$f') as fp:
    tree = ast.parse(fp.read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        length = (node.end_lineno or 0) - node.lineno + 1
        if length > 50:
            print(f'{node.name}:{length}')
            exit(1)
    " 2>&1) || {
        echo "OVER in $f: $RESULT"
        OVERFLOW=1
    }
done

if [ $OVERFLOW -eq 1 ]; then
    echo "FAIL: 存在超过 50 行的函数"
    exit 1
fi
echo "PASS: 所有函数 ≤50 行"

echo "=== 步骤 2: 全量测试 ==="
.venv/bin/python -m pytest -q

echo "=== 全部通过 ==="
```

---

## 8. 技术方案参考

- PRD F25: 新增或修改的函数原则上不超过 50 行
- 技术方案 §7.2: 编码规范
- 任务图 T17: `function-length-limit` Batch B11
