# 开发文档: T15 — QSS 提取

- **Project:** Recordly 核心稳定性与架构治理
- **Task ID:** T15
- **Slug:** `qss-extraction`
- **Issue:** #42
- **类型:** polish
- **Batch:** B10
- **依赖:** T14 (#41)
- **预计工时:** 1h
- **涉及文件:** 2（1 新增 + 1 修改）

---

## 1. 目标

将 `main.py` 中内联的 `DARK_STYLESHEET` 常量（228 行 QSS）完整移至 `resources/style.qss` 文件，`main.py` 改为从文件读取。不改变任何样式规则。

**前置条件（T14 已完成）：**
- `logging.basicConfig` 已添加到 `main.py`
- `main.py` 已 import `logging` 和 `os`

**关键约束：**
- 样式规则完全不变（逐字节一致）
- 文件不存在时优雅降级（使用系统默认样式，不崩溃）
- 不引入新的运行时依赖

---

## 2. 当前状态

`main.py` 结构（245 行）:
```
L1-7:   imports
L9-228: DARK_STYLESHEET = """..." (220 行 QSS)
L230-245: main() 函数
```

`resources/` 目录当前内容:
```
resources/icons/
```

---

## 3. 实施步骤（Red → Green → Refactor）

### 步骤 1: 提取 QSS 到文件（Green）

#### 1a. 创建 `resources/style.qss`

将 `main.py:9-228` 的 `DARK_STYLESHEET` 字符串内容提取到新文件。

**操作方法:**

```bash
# 用 sed 提取 L9-228 的内容（不含变量名和引号）
sed -n '10,228p' main.py | sed '$ s/"""$//' > resources/style.qss
```

或手动：复制 `DARK_STYLESHEET = """` 和结尾 `"""` 之间的所有内容到 `resources/style.qss`。

**验证:**
```bash
# 确认行数
wc -l resources/style.qss
# 应约为 218-220 行（等于 DARK_STYLESHEET 内容行数减去开头结尾的 """ 行）

# 确认首行
head -1 resources/style.qss
# QMainWindow, QWidget {
```

#### 1b. 修改 `main.py` — 替换 DARK_STYLESHEET 为文件读取

**删除:** `main.py:9-228` 的 `DARK_STYLESHEET = """..."""` 整个常量定义。

**新增函数**（在 `main()` 之前）:

```python
def _load_stylesheet() -> str:
    """加载 QSS 样式表，文件缺失时返回空字符串（使用系统默认样式）。"""
    # QSS 文件路径：相对于 main.py 所在目录的 resources/style.qss
    qss_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
    try:
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("QSS 文件未找到: %s，使用系统默认样式", qss_path)
        return ""
    except OSError as e:
        logger.warning("QSS 文件读取失败: %s，使用系统默认样式", e)
        return ""
```

**修改 `main()` 函数:**

将:
```python
app.setStyleSheet(DARK_STYLESHEET)
```
替换为:
```python
stylesheet = _load_stylesheet()
if stylesheet:
    app.setStyleSheet(stylesheet)
```

**要点:**
- `_load_stylesheet()` 的 try/except 覆盖 `FileNotFoundError`（文件不存在）和 `OSError`（权限等）
- logger.warning 确保缺失时有提示（默认 WARNING 级别可见）
- 文件编码使用 `utf-8`（与 Python 字符串一致）
- 路径使用 `os.path.join(os.path.dirname(__file__), ...)` 确保相对于 `main.py` 所在目录

---

### 步骤 2: 验证（Green — 视觉回归）

#### 2a. 视觉一致性检查

**方法:**
1. 启动修改前的 Recordly，截图保存 `before.png`
2. 应用修改后启动，截图保存 `after.png`
3. 逐像素对比（或目视对比）

**Python 自动化对比（可选）:**
```python
from PIL import Image
before = Image.open("before.png")
after = Image.open("after.png")
diff = sum(abs(a - b) for a, b in zip(before.tobytes(), after.tobytes()))
assert diff == 0, f"像素差异: {diff}"
```

#### 2b. 优雅降级验证

```bash
# 临时重命名 QSS 文件
mv resources/style.qss resources/style.qss.bak

# 启动应用
.venv/bin/python main.py
# 应看到 WARNING 日志: "QSS 文件未找到: ..."
# 应用正常启动（使用系统默认样式）

# 恢复
mv resources/style.qss.bak resources/style.qss
```

#### 2c. 回归测试

```bash
.venv/bin/python -m pytest -q
# 应全量通过（样式提取不影响业务逻辑）
```

#### 2d. 行数验证

```bash
wc -l main.py
# 应从 245 行减少到 ~30 行（imports + _load_stylesheet + main）
```

---

## 4. 接口/契约

### `_load_stylesheet()` 函数契约

```python
def _load_stylesheet() -> str:
    """
    从 resources/style.qss 加载 QSS 样式表。

    Returns:
        样式表字符串，文件不存在或读取失败时返回空字符串。

    副作用:
        - 文件缺失时 logger.warning 输出
        - 文件读取异常时 logger.warning 输出
    """
```

### 文件路径约定

```
{项目根}/
├── main.py
└── resources/
    └── style.qss   ← 新增
```

路径解析: `os.path.join(os.path.dirname(__file__), "resources", "style.qss")`
→ 相对于 `main.py` 所在目录。

---

## 5. 单元/集成测试指引

### 建议新增测试（`tests/test_stylesheet.py`，可选）

```python
import os
import tempfile
import pytest
from main import _load_stylesheet

def test_load_stylesheet_exists(tmp_path):
    """QSS 文件存在时应正确读取"""
    qss_path = tmp_path / "resources" / "style.qss"
    qss_path.parent.mkdir()
    qss_path.write_text("QWidget { color: red; }", encoding="utf-8")
    # 需要 monkeypatch __file__ 或 mock os.path.dirname
    ...

def test_load_stylesheet_missing():
    """QSS 文件缺失时应返回空字符串"""
    # 临时重命名 resources/style.qss
    ...

def test_load_stylesheet_empty():
    """QSS 文件为空时应返回空字符串"""
    ...
```

**注意:** 本任务为纯移动任务，测试为可选。如时间不足，以手动视觉验证优先。

---

## 6. 完整验收标准

- [ ] `resources/style.qss` 存在，内容与 `DARK_STYLESHEET` 完全一致（逐字节）
- [ ] `main.py` 中不存在 `DARK_STYLESHEET` 常量
- [ ] `main.py` 通过 `_load_stylesheet()` 函数从文件读取 QSS
- [ ] `main.py` 行数从 245 → ~30 行
- [ ] UI 视觉与之前完全一致（启动后截图对比）
- [ ] QSS 文件路径不存在时应用正常启动（使用系统默认样式），输出 WARNING 日志
- [ ] `pytest -q` 全量通过

---

## 7. 边界情况和风险

### 边界情况

1. **文件不存在** → `FileNotFoundError` → 返回 `""`，日志 WARNING
2. **文件存在但空** → 返回 `""`，`app.setStyleSheet("")` 不会崩溃（Qt 允许空 QSS）
3. **文件存在但不可读（权限）** → `OSError` → 返回 `""`，日志 WARNING
4. **文件编码非 UTF-8** → `UnicodeDecodeError` 会传播（未捕获），应确保文件使用 UTF-8 编码
5. **文件路径包含非 ASCII 字符** → `open(..., encoding="utf-8")` 可处理

### 风险

| 风险 | 缓解 |
|------|------|
| 提取时丢失或新增了空白字符导致样式差异 | 使用 `sed` 或脚本精确提取，避免手动复制粘贴 |
| `os.path.dirname(__file__)` 在某些打包场景（如 PyInstaller）中行为不同 | `sys._MEIPASS` 处理不在本轮范围（打包尚未支持） |
| `_load_stylesheet` 在 main.py 中引入新 import → `logger` | T14 已确保 `main.py` 有 `logging` import 和 logger 可用 |

---

## 8. 任务级验证命令

```bash
# 1. 提取 QSS 内容一致性验证
diff <(sed -n '10,228p' main.py | head -n -1) resources/style.qss
# 应无差异

# 2. DARK_STYLESHEET 已移除
! grep "DARK_STYLESHEET" main.py

# 3. 文件读取逻辑存在
grep "_load_stylesheet" main.py
grep "resources/style.qss" main.py

# 4. 优雅降级验证
mv resources/style.qss resources/style.qss.bak
.venv/bin/python main.py 2>&1 | grep "QSS 文件未找到"
mv resources/style.qss.bak resources/style.qss

# 5. 全量测试
.venv/bin/python -m pytest -q

# 6. main.py 行数
wc -l main.py
# 应 ≈ 30 行
```

---

## 9. 技术方案参考

- 技术方案 §3.2.8: `main.py` — QSS 移至 `resources/style.qss`
- 技术方案 §3.2.9: `resources/style.qss` 新增文件
- 任务图 T15: `qss-extraction` Batch B10
- PRD F23
