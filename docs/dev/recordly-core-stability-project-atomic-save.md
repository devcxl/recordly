# Recordly 核心稳定性 — T06: project-atomic-save

**Project:** Recordly
**Task ID:** T06
**Slug:** project-atomic-save
**Issue:** #33
**类型:** fix
**Batch:** B2（P0 录制基础 + 原子保存）
**依赖:** T04 (#31)

---

## 1. 目标

实现 `Project.save()` 的原子写入，防止进程中断或磁盘写失败时损坏唯一的项目元数据文件 `project.json`。

**方案:** `tempfile.mkstemp` 创建同目录临时文件 → 写入完整 JSON → `os.replace()` 原子替换。写入失败时原文件不受影响。

> **参考:** `ProjectManager.rename_project()`（L136-144）已使用相同的原子写入模式。

---

## 2. 前置条件

- T03 完成（Project.load() schema 验证已就绪）
- T04 完成（路径规范化，`_current_project_path` 是正确的目录路径）
- 理解当前 `Project.save()` 的简单实现（L203-227）— 直接 `open(path, "w")` 写入

---

## 3. TDD 实现步骤

### Red — 确认当前非原子行为

当前 `Project.save()` 直接覆盖写入文件：
```python
def save(self, path: str):
    data = {...}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    self.filepath = path
```

**问题:** 如果在 `json.dump` 过程中进程被 kill 或磁盘满，可能导致 `project.json` 只写了一半，原始完整数据丢失。

### Green — 分三步实现

#### Step 1: 实现原子写入（`core/project.py`）

修改 `Project.save()`：

```python
import tempfile

def save(self, path: str):
    """原子保存 project.json：写临时文件 → os.replace 原子替换。
    
    写入失败时原 project.json 不受影响。
    """
    data = {
        "version": self.version,
        "created_at": self.created_at,
        "name": self.name,
        "modified_at": datetime.now().isoformat(),
        "duration": self.duration,
        "thumbnail_path": self.thumbnail_path,
        "source": asdict(self.source) if self.source else None,
        "timeline": [asdict(t) for t in self.timeline],
        "cursor": asdict(self.cursor),
        "frame_style": self._serialize_frame_style(),
        "annotations": [asdict(a) for a in self.annotations],
        "audio_regions": [asdict(a) for a in self.audio_regions],
        "crop_region": asdict(self.crop_region) if self.crop_region else None,
        "aspect_ratio": self.aspect_ratio,
        "cursor_events": self.cursor_events,
        "click_events": self.click_events,
        "monitor_offset": self.monitor_offset,
        "frame_count": getattr(self, "_frame_count", 0),
    }
    
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)
    
    # 原子写入：临时文件 → os.replace
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".project-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # 确保数据落盘
        os.replace(tmp_path, path)
    except Exception:
        # 写入失败 → 清理临时文件，原 project.json 不受影响
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    
    self.filepath = path
```

**关键细节:**
- `tempfile.mkstemp(dir=dir_path)` — 临时文件在目标目录创建，确保 `os.replace` 在同一文件系统（保证原子性）
- `prefix=".project-"` — 隐藏文件前缀，避免被目录扫描误识别
- `f.flush()` + `os.fsync()` — 确保数据完全写入磁盘后再执行 replace
- `except` 块中 `os.unlink(tmp_path)` — 确保临时文件不残留
- 原 `project.json` 在 `os.replace` 之前未被修改

#### Step 2: 提取 `_serialize_frame_style()` 辅助方法

保持干净的主体逻辑：

```python
def _serialize_frame_style(self) -> dict:
    """序列化 FrameStyle，处理 bg_color 的 tuple→#RRGGBB 编码。"""
    d = asdict(self.frame_style)
    bg = self.frame_style.bg_color
    if isinstance(bg, tuple) and len(bg) == 3:
        d["bg_color"] = f"#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}"
    return d
```

#### Step 3: 编写测试（`tests/test_project.py`）

**新增测试:**

```python
import os
import tempfile
import json


class TestAtomicSave:
    """Project.save() 原子写入"""

    def test_atomic_save_success(self):
        """正常原子保存成功，project.json 可读"""
        p = Project()
        p.name = "atomic_test"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "project.json")
            p.save(path)
            
            # 验证文件存在且内容完整
            assert os.path.isfile(path)
            with open(path) as f:
                data = json.load(f)
            assert data["name"] == "atomic_test"
            
            # 验证无残留临时文件
            tmp_files = [f for f in os.listdir(tmpdir) if f.startswith(".project-")]
            assert len(tmp_files) == 0

    def test_atomic_save_preserves_original_on_failure(self, monkeypatch):
        """写入失败时原 project.json 保持完整"""
        p = Project()
        p.name = "original"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "project.json")
            
            # 先保存一个原始版本
            p.save(path)
            with open(path) as f:
                original_content = f.read()
            
            # 修改 project 数据
            p.name = "modified"
            
            # 模拟 json.dump 中途失败（如磁盘满）
            import core.project as project_module
            original_dump = json.dump
            
            def failing_dump(*args, **kwargs):
                raise OSError("模拟磁盘写入失败")
            
            monkeypatch.setattr(json, "dump", failing_dump)
            
            try:
                p.save(path)
            except OSError:
                pass  # 预期失败
            
            # 验证原文件内容不变
            with open(path) as f:
                recovered_content = f.read()
            assert recovered_content == original_content
            
            # 验证无残留临时文件
            tmp_files = [f for f in os.listdir(tmpdir) if f.startswith(".project-")]
            assert len(tmp_files) == 0
            
            # 恢复 json.dump
            monkeypatch.setattr(json, "dump", original_dump)

    def test_atomic_save_removes_tempfile_on_error(self):
        """异常时清理临时文件 .project-*.tmp"""
        p = Project()
        p.name = "test"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "project.json")
            
            # 使用无写入权限的目录模拟失败
            # 更简单的方案：传入一个目录路径作为文件路径
            try:
                p.save(tmpdir)  # tmpdir 是目录不是文件，os.replace 会失败
            except (OSError, IsADirectoryError):
                pass
            
            # 验证临时文件被清理
            tmp_files = [f for f in os.listdir(tmpdir) if f.startswith(".project-")]
            assert len(tmp_files) == 0

    def test_atomic_save_preserves_bg_color_encoding(self):
        """原子保存时 bg_color 正确编码为 #RRGGBB"""
        p = Project()
        p.frame_style.bg_color = (10, 20, 30)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "project.json")
            p.save(path)
            
            with open(path) as f:
                data = json.load(f)
            assert data["frame_style"]["bg_color"] == "#0a141e"
```

### Refactor — 检查清单

- [ ] `Project.save()` 使用 `tempfile.mkstemp` + `os.replace`
- [ ] 无 `open(path, "w")` 直接写入（在 save 方法中）
- [ ] 所有调用 `Project.save()` 的位置（`MainWindow._finalize_project`、`_on_save_project`）行为不变——只需 API 兼容
- [ ] `_serialize_frame_style()` 提取为独立方法

---

## 4. 接口/契约

### Project.save() 契约（修改后）

```python
def save(self, path: str) -> None:
    """原子保存 project.json。
    
    - 使用 tempfile.mkstemp + os.replace 保证写入原子性
    - 写入失败时原 project.json 不受影响
    - 正常流程不残留 .project-*.tmp 文件
    - 异常流程 best-effort 清理临时文件
    
    Args:
        path: project.json 文件的完整路径
    
    Raises:
        OSError: 目录创建失败或磁盘写入失败
        Exception: json 序列化过程中的异常
    """
```

---

## 5. 数据模型变化

无新增字段或模型变更。

---

## 6. 测试指引

### 新增测试

| 文件 | 测试 | 场景 |
|------|------|------|
| `tests/test_project.py` | `test_atomic_save_success` | 正常保存 + 无残留临时文件 |
| `tests/test_project.py` | `test_atomic_save_preserves_original_on_failure` | 写入失败原文件完整 |
| `tests/test_project.py` | `test_atomic_save_removes_tempfile_on_error` | 异常清理临时文件 |
| `tests/test_project.py` | `test_atomic_save_preserves_bg_color_encoding` | 与 T03 bg_color 编码兼容 |

### 回归测试

```bash
pytest tests/test_project.py -q -v
pytest tests/test_data_persistence.py -q -v
```

---

## 7. 验收标准

- [ ] `Project.save()` 使用 `tempfile.mkstemp` + `os.replace` 原子替换（非直接 open 写入）
- [ ] 写入过程中模拟磁盘满/权限错误 → 原 `project.json` 内容不变
- [ ] `pytest tests/test_project.py -q` 全部通过
- [ ] 新增测试 4 个（原子保存成功、失败后文件完整、临时文件清理、bg_color 编码）
- [ ] 项目目录中不残留 `.project-*.tmp` 文件（正常流程和异常流程）
- [ ] 所有现有调用 `Project.save()` 的代码不报错（保持 API 兼容）

---

## 8. 边界情况与风险

| 场景 | 处理 |
|------|------|
| 目标目录不存在 | `os.makedirs(dir_path, exist_ok=True)` 创建 |
| 目标路径是目录而非文件 | `os.replace` 失败 → 抛异常，临时文件被清理 |
| 目标文件正在被其他进程读取 | `os.replace` 原子替换，读进程看到旧内容或新内容，不会看到半写状态 |
| 磁盘空间不足 | `json.dump` 中途失败 → 临时文件被清理，原文件完整 |
| 进程在 `os.replace` 之前被 kill | 临时文件残留（下次保存时 `mkstemp` 使用随机后缀，不会冲突） |
| 进程在 `os.replace` 过程中被 kill | `os.replace` 是 POSIX 原子操作，不会出现中间状态 |
| 文件系统不支持原子 rename（如 FAT32） | 非目标平台（Linux+NTFS），但 `os.replace` 在 FAT32 上仍执行非原子 rename |
| `fsync` 在某些文件系统上无保证 | `fsync` 是 best-effort；`os.replace` 本身保证原子性 |

**风险:** 临时文件前缀 `.project-` 可能与用户手动创建的隐藏文件冲突。可能性极低（`mkstemp` 使用随机后缀）。

---

## 9. 任务验证命令

```bash
# 原子保存测试
pytest tests/test_project.py::TestAtomicSave -q -v

# 确认实现不使用直接 open 写入
grep -n "open.*path.*w" core/project.py
# 在 save() 方法内应无输出（使用 fdopen + os.replace）

# 全量项目测试
pytest tests/test_project.py tests/test_data_persistence.py -q -v

# 全量回归（B2 完成时应 0 failed）
pytest -q
```

---

## 关联文件

| 文件 | 操作 |
|------|------|
| `core/project.py` | `Project.save()` 改为原子写入 + 提取 `_serialize_frame_style()` |
| `tests/test_project.py` | 新增 `TestAtomicSave` 类（4 个测试） |
