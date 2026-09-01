# Recordly 核心稳定性 — T04: project-input-normalization

**Project:** Recordly
**Task ID:** T04
**Slug:** project-input-normalization
**Issue:** #31
**类型:** fix
**Batch:** B1（P0 路径规范化）
**依赖:** T01 (#28), T02 (#29), T03 (#30)

---

## 1. 目标

解决项目路径歧义——当前 `MainWindow._on_open_project()` 将 `QFileDialog` 返回的 `project.json` **文件路径**直接传给 `ProjectManager.open_project()`，后者拼接 `/project.json` 导致路径 `.../project.json/project.json`（双重 `.json`）。

**核心修复:** 在任何进入 `ProjectManager.open_project()` 之前，统一将输入的路径规范化为**项目目录路径**：
- 如果路径以 `project.json` 结尾 → `os.path.dirname()` 取父目录
- 所有内部变量（`_current_project_path`）始终存储目录路径，不含 `.json` 后缀

---

## 2. 前置条件

- B0（T01+T02+T03）完成，全量测试 0 failed
- 理解 `MainWindow._on_open_project()` 的当前流程（L1065-1163）
- 理解 `ProjectManager.open_project(project_path)` 期望接收**目录路径**（L101-106）
- 理解 `MainWindow._on_home_open_project()` 使用 `QFileDialog.getOpenFileName` 返回文件路径

---

## 3. TDD 实现步骤

### Red — 确认问题

```bash
# 当前代码行为：
# QFileDialog 选 project.json → path = "/home/user/.../project.json"
# → ProjectManager.open_project(path) → Path(path) / "project.json"
# → 实际查找 "/home/user/.../project.json/project.json" ← 错误！
```

不存在针对此场景的测试，需要先编写。

### Green — 分三步实现

#### Step 1: 添加路径规范化辅助函数 + 单元测试

**文件:** `core/project.py`（或 `app/main_window.py` 作为静态方法）

根据技术方案 §4.5，路径规范化逻辑属于 `MainWindow` 或未来的 `ProjectSession`。P0 阶段直接在 `MainWindow` 中实现：

```python
# app/main_window.py 中添加静态方法

@staticmethod
def _normalize_project_path(input_path: str) -> str:
    """将输入路径规范化为项目目录路径。
    
    - 如果 input_path 以 'project.json' 结尾 → 返回其父目录
    - 否则 → 返回 input_path（假定已是目录路径）
    - 如果路径不存在 → 仍返回规范化结果（由调用方检查）
    
    Args:
        input_path: 文件路径或目录路径
    
    Returns:
        项目目录的绝对路径（不含 project.json 后缀）
    """
    path = os.path.abspath(input_path)
    if os.path.basename(path) == "project.json":
        return os.path.dirname(path)
    return path
```

**测试（`tests/test_main_window.py` 新增）:**

```python
import os
import tempfile
from app.main_window import MainWindow


class TestProjectPathNormalization:
    """路径规范化：文件路径 → 目录路径"""

    def test_project_json_path_returns_parent_dir(self):
        path = "/home/user/projects/my_project/project.json"
        result = MainWindow._normalize_project_path(path)
        assert result == "/home/user/projects/my_project"
        assert not result.endswith(".json")

    def test_directory_path_is_unchanged(self):
        path = "/home/user/projects/my_project"
        result = MainWindow._normalize_project_path(path)
        assert result == os.path.abspath(path)
        assert not result.endswith(".json")

    def test_path_without_project_json_is_unchanged(self):
        path = "/home/user/projects/my_project/frames.data"
        result = MainWindow._normalize_project_path(path)
        assert not result.endswith(".json")

    def test_relative_path_is_absolute(self):
        result = MainWindow._normalize_project_path("my_project/project.json")
        assert os.path.isabs(result)
        assert not result.endswith(".json")
```

#### Step 2: 修改 `_on_home_open_project()` 使用规范化

**文件:** `app/main_window.py`，约 L446-453

```python
def _on_home_open_project(self):
    """首页点击'打开项目' → 文件选择器 → 规范化路径 → 打开"""
    path, _ = QFileDialog.getOpenFileName(
        self, "选择项目文件", self.config.projects_dir,
        "Recordly 项目 (project.json)",
    )
    if path:
        # 规范化：将 project.json 文件路径转为项目目录路径
        normalized = self._normalize_project_path(path)
        self._on_open_project(normalized)
```

#### Step 3: 修改 `_on_open_project()` 确保 `_current_project_path` 始终是目录

**文件:** `app/main_window.py`，约 L1065-1085

当前代码：
```python
def _on_open_project(self, path: str):
    # ...清理旧状态...
    try:
        project = self._project_manager.open_project(path)
    except Exception as exc:
        self._show_notification("打开项目失败", str(exc), "error")
        return
    
    self._current_project_path = path  # ← 这里可能存了文件路径！
```

修改为：
```python
def _on_open_project(self, path: str):
    """打开项目 → 加载到 compositor → 切换到编辑器界面"""
    # ── 路径规范化 + 存在性校验 ──
    project_dir = self._normalize_project_path(path)
    
    if not os.path.isdir(project_dir):
        self._show_notification(
            "打开项目失败",
            f"项目目录不存在: {project_dir}",
            "error",
        )
        return
    
    proj_file = os.path.join(project_dir, "project.json")
    if not os.path.isfile(proj_file):
        self._show_notification(
            "打开项目失败",
            f"项目文件不存在: {proj_file}",
            "error",
        )
        return
    
    # ── 安全打开：先校验新项目再清理旧状态 ──
    try:
        new_project = Project.load(proj_file)  # 独立加载，校验 schema
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        self._show_notification(
            "打开项目失败",
            f"项目文件格式无效: {exc}",
            "error",
        )
        return
    
    # 校验通过 → 清理旧状态
    self._recorded_data = None
    self._playback = None
    # ... 其余清理 ...
    
    self._current_project_path = project_dir  # ← 始终是目录路径
    
    # 使用已加载的 new_project，不再调用 ProjectManager.open_project()
    project = new_project
    # ... 后续加载逻辑不变 ...
```

> **关键变更:** 
> 1. `_current_project_path` 始终是目录路径（不会有 `.json` 后缀）
> 2. 改用 `Project.load()` 直读（跳过 `ProjectManager.open_project()` 的文件定位，因为路径已规范化为目录）
> 3. 打开前先校验 schema，校验失败不破坏当前状态

### Refactor — 检查清单

- [ ] `_current_project_path` 的任何赋值点都确认存储的是目录路径
- [ ] `_auto_create_project()` 中 `self._current_project_path = project_dir` 已是目录路径（L428）→ 无需修改
- [ ] `_finalize_project()` 中使用 `str(Path(self._current_project_path) / "project.json")` → 依赖目录路径，行为正确
- [ ] `_on_save_project()` 中使用 `str(Path(self._current_project_path) / "project.json")` → 同上

---

## 4. 接口/契约

### MainWindow._normalize_project_path()

```python
@staticmethod
def _normalize_project_path(input_path: str) -> str:
    """返回输入路径对应的项目目录绝对路径。"""
```

**契约:**
- 输入 `"~/projects/test/project.json"` → 返回 `"/home/user/projects/test"`
- 输入 `"~/projects/test"` → 返回 `"/home/user/projects/test"`
- 路径始终是绝对路径
- 不做存在性检查（由调用方负责）

### ProjectManager.open_project() 调用变更

**旧:** `self._project_manager.open_project(path)` — path 可能是文件或目录
**新:** 不再通过 ProjectManager.open_project() 打开（改用 `Project.load(proj_file)` 直读）

> 可选保留 ProjectManager.open_project() 的兼容性，但本任务不做此改动。

---

## 5. 数据模型变化

无。

---

## 6. 测试指引

### 新增测试（`tests/test_main_window.py`）

| 测试 | 场景 |
|------|------|
| `test_project_json_path_returns_parent_dir` | 选择 project.json 文件 → 规范化为目录 |
| `test_directory_path_is_unchanged` | 选择目录路径 → 保持目录路径 |
| `test_relative_path_is_absolute` | 相对路径 → 转为绝对路径 |

### 修改已有测试

**验证 `_on_open_project` 调用 `_normalize_project_path`:**

由于 `_on_open_project` 的 Qt 依赖较重（QFileDialog、QStackedWidget 等），建议使用集成测试或在已有测试中添加路径规范化逻辑验证。

### 回归测试

```bash
pytest tests/test_main_window.py -q -v
pytest tests/test_project.py -q -v
```

---

## 7. 验收标准

- [ ] 首页"打开项目"按钮 → 选择 `project.json` 文件 → 项目成功加载
- [ ] 首页项目卡片 → 点击卡片 → 项目成功加载（卡片存储的是目录路径）
- [ ] 选择不存在的路径 → 错误提示，当前状态不变
- [ ] 选择目录但 project.json 不存在 → 错误提示
- [ ] `_current_project_path` 始终是目录路径（无 `.json` 后缀）
- [ ] `pytest tests/test_main_window.py -q -k "open_project"` 通过
- [ ] 新增测试覆盖：文件路径 → 目录规范化 → 加载成功

---

## 8. 边界情况与风险

| 场景 | 处理 |
|------|------|
| 用户选择 `project.json` 文件（文件选择器） | `os.path.dirname()` 取父目录 → 正确 |
| 用户点击首页项目卡片 | 卡片已存储目录路径 → 不变 |
| 用户输入不存在的路径 | `os.path.isdir()` 检查 → 错误提示 |
| 目录存在但 project.json 损坏/不存在 | schema 验证失败 → 错误提示，当前状态不变 |
| `_current_project_path` 为 None 时调用 `_on_save_project` | 已有检查（L1183-1185）→ 提示"没有打开项目" |
| 路径包含符号链接 | `os.path.abspath()` 处理，但不 resolve symlink |
| 路径包含 `..` | `os.path.abspath()` 规范化 |

**风险:** `_normalize_project_path` 假设 `project.json` 是子目录下唯一的 `.json` 文件且文件名固定为 `project.json`。如果未来支持自定义文件名，需要调整逻辑。当前版本无此需求。

---

## 9. 任务验证命令

```bash
# 路径规范化单元测试
pytest tests/test_main_window.py -q -k "normalization" -v

# 项目打开流程测试
pytest tests/test_main_window.py -q -k "open_project" -v

# 全量回归
pytest -q

# 手动验证（可选）
echo "在 UI 中选择 project.json 文件 → 确认项目正确打开"
```

---

## 关联文件

| 文件 | 操作 |
|------|------|
| `app/main_window.py` | 添加 `_normalize_project_path()` + 修改 `_on_home_open_project()` + `_on_open_project()` |
| `core/project_manager.py` | 无需修改（接口保持兼容） |
| `tests/test_main_window.py` | 新增 `TestProjectPathNormalization` 类 |
