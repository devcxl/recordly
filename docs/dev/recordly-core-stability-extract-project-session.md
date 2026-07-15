# T10: extract-project-session — 提取 ProjectSession

**Project:** Recordly  
**Task ID:** T10  
**Slug:** extract-project-session  
**Issue:** #37  
**类型:** refactor  
**Batch:** B5  
**依赖:** T06 (#33), T08 (#35)

---

## 1. 目标

从 `MainWindow` 提取 `ProjectSession` 类（ADR-007 §3.1，技术方案 §3.1.1），拥有当前项目目录、Project 模型和媒体资源路径契约。将 P0 阶段分散在 MainWindow 中的项目路径管理、WAV 文件读写、原子 JSON 保存收敛到一个可独立测试的纯 Python 对象。

---

## 2. 前置条件

- [x] T06 完成：`Project.save()` 原子写入可用
- [x] T08 完成：导出正确性已修复
- [x] T03 完成：`Project.load()` schema 验证已实现
- [x] T07 完成：WAV 读写逻辑存在于 MainWindow helper 方法

---

## 3. 当前状态

```
MainWindow 中分散的职责:
├── _current_project_path              # 路径管理（可能指向 file 或 dir）
├── _finalize_project()                # 保存项目 + WAV 写入
├── _on_open_project()                 # 加载项目 + WAV 读取 + 路径规范化
├── _on_save_project()                 # 保存
├── _on_export() → _current_project_path  # 获取音频路径
├── _auto_create_project()             # 创建项目目录
└── home_page.py → project.json 文件路径传递  # 路径契约歧义
```

---

## 4. Red → Green → Refactor 实施步骤

### 🔴 RED — 编写 ProjectSession 单元测试（先写测试，确认新模块接口）

#### Step 1: `tests/test_project_session.py` — **新增文件**

```python
"""ProjectSession 单元测试 — 纯 Python，不依赖 Qt"""

class TestProjectSessionInit:
    def test_init_with_valid_project_dir(self, tmp_path):
        """给定有效项目目录 → 创建 ProjectSession"""
    def test_init_with_missing_dir_raises(self, tmp_path):
        """给定不存在目录 → FileNotFoundError"""
    def test_init_with_corrupt_project_json_raises(self, tmp_path):
        """project.json 损坏 → ValueError"""
    def test_project_file_property(self, tmp_path):
        """project_file 返回 project_dir/project.json"""

class TestProjectSessionCreate:
    def test_create_makes_directory_and_placeholder_json(self, tmp_path):
        """create() 创建项目目录和占位 project.json"""
    def test_create_project_name_in_json(self, tmp_path):
        """project.json 中包含正确的 name 字段"""
    def test_create_returns_valid_project_session(self, tmp_path):
        """返回值可正常读写"""

class TestProjectSessionLoad:
    def test_load_from_dir(self, tmp_path):
        """从目录加载 Project + schema 验证"""
    def test_load_with_unknown_schema_fields_raises(self, tmp_path):
        """旧版/未来 schema → ValueError（复用 T03 验证）"""
    def test_load_with_missing_project_json_raises(self, tmp_path):
        """目录无 project.json → FileNotFoundError"""

class TestProjectSessionSave:
    def test_save_is_atomic(self, tmp_path):
        """save() 使用临时文件 + os.replace"""
    def test_save_failure_preserves_original(self, tmp_path):
        """写入失败 → 原 project.json 内容不变"""
    def test_save_writes_all_fields(self, tmp_path):
        """保存后 load 回来的数据一致"""

class TestProjectSessionAudio:
    def test_save_audio_writes_wav_files(self, tmp_path):
        """save_audio() 在项目目录下创建 audio_mic.wav + audio_system.wav"""
    def test_load_audio_returns_correct_data(self, tmp_path):
        """load_audio() 返回与保存一致的 numpy 数据"""
    def test_save_audio_updates_source_info_paths(self, tmp_path):
        """save_audio() 后 project.source.audio_mic = "audio_mic.wav" """
    def test_save_audio_with_none_data_skips(self, tmp_path):
        """mic_data=None → 不写文件，字段保持 "" """

class TestProjectSessionNormalizePath:
    def test_project_json_file_to_dir(self):
        """project.json 文件路径 → 父目录"""
    def test_directory_path_unchanged(self):
        """目录路径 → 保持不变"""
    def test_non_json_path_normalized(self):
        """不存在的路径 → 原样返回"""
```

**验证命令:** `pytest tests/test_project_session.py -q` → 预期全部 FAIL（文件不存在）

---

### 🟢 GREEN — 实现 ProjectSession

#### Step 2: `app/project_session.py` — **新增 ~180 行**

**完整接口（源自技术方案 §3.1.1）:**

```python
"""项目会话 — 纯 Python 对象，拥有项目目录、Project 模型和媒体资源路径"""

import json
import os
import tempfile
import wave
import numpy as np
from dataclasses import asdict

from core.project import Project
from core.project_manager import ProjectManager  # 用于校验文件存在性


class ProjectSession:
    """当前项目会话 — 纯 Python 对象，非 QObject"""

    def __init__(self, project_dir: str):
        """
        Args:
            project_dir: 项目目录绝对路径（非 project.json 文件路径）
        Raises:
            FileNotFoundError: 项目目录不存在
            ValueError: project.json 损坏或 schema 不兼容
        """
        if not os.path.isdir(project_dir):
            raise FileNotFoundError(f"项目目录不存在: {project_dir}")
        self._project_dir = os.path.abspath(project_dir)
        self._project = Project.load(self.project_file)

    # ── 属性 ────────────────────────────────────────────
    @property
    def project_dir(self) -> str:
        return self._project_dir

    @property
    def project(self) -> Project:
        return self._project

    @property
    def project_file(self) -> str:
        return os.path.join(self._project_dir, "project.json")

    @property
    def frames_data_path(self) -> str:
        return os.path.join(self._project_dir, "frames.data")

    # ── 工厂方法 ─────────────────────────────────────────
    @classmethod
    def create(cls, projects_dir: str, name: str) -> "ProjectSession":
        """创建新项目目录 + 占位 project.json，返回 ProjectSession"""
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "_- " else "_" for c in name).strip()
        dir_name = f"{timestamp}_{safe_name}" if safe_name else timestamp
        project_dir = os.path.join(projects_dir, dir_name)
        os.makedirs(project_dir, exist_ok=True)
        
        proj = Project()
        proj.name = name
        proj.save(os.path.join(project_dir, "project.json"))
        
        session = cls.__new__(cls)
        session._project_dir = project_dir
        session._project = proj
        return session

    @classmethod
    def load(cls, project_dir: str) -> "ProjectSession":
        """从目录加载 Project + 校验 schema 兼容性。
        校验失败抛 ValueError 并保持参数 project_dir 不变。
        """
        project_dir = cls.normalize_path(project_dir)
        if not os.path.isdir(project_dir):
            raise FileNotFoundError(f"项目目录不存在: {project_dir}")
        return cls(project_dir)

    # ── 持久化 ───────────────────────────────────────────
    def save(self, compositor_state: dict | None = None,
             timeline_tracks: list | None = None,
             audio_regions: list | None = None,
             crop_region=None,
             cursor_events: list | None = None,
             click_events: list | None = None,
             monitor_offset: list | None = None) -> None:
        """原子保存 project.json: 写临时文件 → os.replace。
        写入失败时原 project.json 不受影响。
        """
        p = self._project
        p.modified_at = None  # save() 内部设置
        
        # 更新可变字段
        if cursor_events is not None:
            p.cursor_events = cursor_events
        if click_events is not None:
            p.click_events = click_events
        if monitor_offset is not None:
            p.monitor_offset = monitor_offset
        if crop_region is not None:
            p.crop_region = crop_region
        if timeline_tracks is not None:
            p.timeline = timeline_tracks
        if audio_regions is not None:
            p.audio_regions = audio_regions
        
        p.save(self.project_file)  # 委托 Project.save() — T06 原子写入

    def save_audio(self, mic_data: np.ndarray | None,
                   system_data: np.ndarray | None,
                   samplerate: int) -> None:
        """分别写入麦克风/系统音频到项目目录下的 WAV 文件，
        更新 project.source.audio_mic / project.source.audio_system 为相对路径。
        不持久化混音文件。
        """
        from core.project import write_audio_wav  # T07 Refactor 提取的函数
        
        if mic_data is not None and len(mic_data) > 0:
            path = os.path.join(self._project_dir, "audio_mic.wav")
            write_audio_wav(mic_data, path, samplerate)
            if self._project.source:
                self._project.source.audio_mic = "audio_mic.wav"
        
        if system_data is not None and len(system_data) > 0:
            path = os.path.join(self._project_dir, "audio_system.wav")
            write_audio_wav(system_data, path, samplerate)
            if self._project.source:
                self._project.source.audio_system = "audio_system.wav"
        
        self._project.save(self.project_file)

    def load_audio(self) -> dict | None:
        """从项目目录加载 WAV 音频，返回 {'mic': ndarray, 'system': ndarray, 
        'mixed': ndarray, 'samplerate': int} 或 None"""
        from core.project import read_audio_wav  # T07 Refactor 提取的函数
        from core.audio_capture import mix_audio_results
        
        mic_data, sys_data = None, None
        sr = 44100
        
        if self._project.source:
            mic_rel = self._project.source.audio_mic
            sys_rel = self._project.source.audio_system
            
            if mic_rel:
                mic_path = os.path.join(self._project_dir, mic_rel)
                if os.path.exists(mic_path):
                    mic_data, sr = read_audio_wav(mic_path)
            
            if sys_rel:
                sys_path = os.path.join(self._project_dir, sys_rel)
                if os.path.exists(sys_path):
                    sys_data, _ = read_audio_wav(sys_path)
        
        if mic_data is None and sys_data is None:
            return None
        
        mixed = mix_audio_results(mic_data, sys_data) if (mic_data is not None and sys_data is not None) else (mic_data or sys_data)
        return {"mic": mic_data, "system": sys_data, "mixed": mixed, "samplerate": sr}

    # ── 路径工具 ─────────────────────────────────────────
    @staticmethod
    def normalize_path(input_path: str) -> str:
        """将 project.json 文件路径规范化为项目目录路径"""
        if not input_path:
            return input_path
        if os.path.basename(input_path) == "project.json":
            return os.path.dirname(input_path)
        return input_path
```

---

#### Step 3: `app/main_window.py` — 渐进引入 ProjectSession（先加后切）

**最小侵入策略：保留 `_current_project_path` 同时添加 `_project_session`**

```python
class MainWindow(QMainWindow):
    # ...
    _project_session: ProjectSession | None = None

    # _finalize_project() 中:
    def _finalize_project(self):
        # ... 原有代码 ...
        # 在原有 project.save() 之后添加:
        if self._project_session:
            # 通过 ProjectSession 进行原子保存
            mic = self._recorded_data.get("mic_audio")
            sys = self._recorded_data.get("system_audio")
            sr = self._recorded_data.get("audio", {}).get("samplerate", 44100) if self._recorded_data.get("audio") else 44100
            self._project_session.save_audio(mic, sys, sr)
            self._project_session.save(
                cursor_events=..., click_events=..., monitor_offset=...

    # _on_open_project() 中:
    def _on_open_project(self, path: str):
        project_dir = ProjectSession.normalize_path(path)
        
        # 安全拒绝协议（先校验再替换）
        try:
            new_session = ProjectSession.load(project_dir)
        except (ValueError, FileNotFoundError) as e:
            self._show_notification("无法打开项目", str(e), "error")
            return  # 保持当前状态不变
        
        # 校验通过 → 替换
        self._project_session = new_session
        self._current_project_path = project_dir
        
        # 加载音频
        audio_info = self._project_session.load_audio()
        if audio_info:
            self._recorded_data = {"audio": audio_info}
        
        # ... 原有加载逻辑 ...

    # _on_save_project() 中:
    def _on_save_project(self):
        if self._project_session:
            self._project_session.save(
                cursor_events=..., click_events=..., ...
            )
        # ... 原有保存逻辑（保留兼容）...
```

**验证命令:** `pytest tests/test_main_window.py -q` → 全部通过（不退化）

---

### 🔵 REFACTOR — 移除 MainWindow 中的重复逻辑

#### Step 4: 移除 `_finalize_project()` 中的 inline WAV 写入

T07 的 MainWindow helper `_save_audio_wavs` → 替换为 `self._project_session.save_audio(...)`。

#### Step 5: 移除 `_on_open_project()` 中的 inline WAV 读取

T07 的 MainWindow helper `_load_audio_from_wavs` → 替换为 `self._project_session.load_audio()`。

#### Step 6: 替换路径规范化

所有 `os.path.dirname(path)` 或 `Path(...).parent` 模式 → `ProjectSession.normalize_path(path)`。

---

## 5. 接口/契约

### ProjectSession 公开接口（完整签名）

```python
class ProjectSession:
    # 构造
    __init__(project_dir: str) -> ProjectSession          # raises FileNotFoundError, ValueError
    create(projects_dir: str, name: str) -> ProjectSession  # @classmethod
    load(project_dir: str) -> ProjectSession                # @classmethod

    # 属性
    project_dir: str       # 项目目录绝对路径
    project: Project       # 当前 Project 模型
    project_file: str      # project_dir/project.json
    frames_data_path: str  # project_dir/frames.data

    # 持久化
    save(compositor_state=None, timeline_tracks=None, audio_regions=None,
         crop_region=None, cursor_events=None, click_events=None, 
         monitor_offset=None) -> None
    save_audio(mic_data: np.ndarray|None, system_data: np.ndarray|None, 
               samplerate: int) -> None
    load_audio() -> dict | None

    # 工具
    normalize_path(input_path: str) -> str  # @staticmethod
```

### 安全拒绝协议

```
_on_open_project(path):
    1. project_dir = ProjectSession.normalize_path(path)
    2. 创建临时 ProjectSession.load(project_dir)  ← schema 验证
    3. 成功 → 替换 self._project_session + 加载到 Compositor
    4. 失败 → 保持 self._project_session 不变 + 显示错误
```

---

## 6. 数据模型变化

**无数据模型变化。** ProjectSession 是纯 Python 包装器，使用已有的 `Project`、`SourceInfo`、`Project.save()`/`Project.load()`。

---

## 7. 测试指引

### 单元测试 (test_project_session.py) — 覆盖矩阵

| 方法 | 正常路径 | 异常路径 | 边界 |
|------|---------|---------|------|
| `__init__` | 有效目录 | 不存在目录、损坏 JSON | 空目录 |
| `create` | 创建新项目 | 权限不足 | 特殊字符项目名 |
| `load` | 加载已有项目 | schema 不兼容、无 project.json | 路径含 project.json 文件名 |
| `save` | 原子写入 | 磁盘满、权限错误 | 并发保存 |
| `save_audio` | 双 WAV 写入 | None 数据、空数组 | 仅 mic/仅 system |
| `load_audio` | 读取 WAV | 文件不存在、损坏 WAV | 路径为空字符串 |
| `normalize_path` | project.json→dir | 空字符串、非 JSON 文件 | 目录路径不变 |

### 集成测试 (test_main_window.py) — 确认无回归

```python
def test_open_project_card_uses_project_session(qtbot, tmp_projects_dir):
    """项目卡片打开 → _project_session 非空"""

def test_save_uses_project_session_atomic_write(qtbot):
    """保存后 project.json 是通过临时文件写入的"""

def test_open_corrupt_project_preserves_current_state(qtbot):
    """打开损坏项目 → 当前编辑状态不变"""
```

---

## 8. 验收标准

- [ ] `app/project_session.py` 通过全部单元测试（新文件，覆盖率 ≥ 90%）
- [ ] `ProjectSession.save()` 使用 T06 的 `Project.save()` 原子写入
- [ ] `ProjectSession.load()` 使用 T03 的 schema 验证
- [ ] `ProjectSession.save_audio()` / `load_audio()` 正确读写项目目录下的 WAV 文件
- [ ] `ProjectSession.normalize_path()` 将 `project.json` 文件路径规范化为目录路径
- [ ] `pytest tests/test_project_session.py -q` 全部通过
- [ ] `pytest tests/test_main_window.py -q` 全部通过（不退化）
- [ ] ProjectSession 纯 Python（非 QObject），可独立测试
- [ ] 打开损坏项目后当前编辑状态保持不变
- [ ] 全量 `pytest -q` 0 failed

---

## 9. 边界情况与风险

| 边界/风险 | 处理策略 |
|-----------|---------|
| `_current_project_path` 和 `_project_session` 同时存在 | 渐进策略：先加 ProjectSession 并行运行，T13（MainWindow 缩减）时移除 `_current_project_path` |
| `ProjectManager` 与 `ProjectSession` 功能重叠 | `ProjectSession` 内部可调用 `ProjectManager` 的方法，不替代它 |
| `load_audio()` 依赖 `mix_audio_results` | 如果 audio_capture 模块不可用，load_audio 降级返回分离的 mic/system 数据 |
| WAV 文件不存在但路径字段非空 | `load_audio()` 中对每个路径做 `os.path.exists` 检查，不存在则跳过 |
| `save_audio()` 中的 `Project.save()` 调用 | 在 `save_audio()` 末尾调用 `self._project.save(self.project_file)` 持久化 audio_mic/audio_system 路径到 JSON |

---

## 10. 任务级验证命令

```bash
# Step 1 (Red): 确认测试文件不存在
ls tests/test_project_session.py 2>&1 || echo "文件不存在"

# Step 2-3 (Green): 实现后验证
pytest tests/test_project_session.py -q
pytest tests/test_main_window.py -q

# Step 4-6 (Refactor): 全量回归
pytest tests/ -q

# 行数检查
wc -l app/project_session.py  # 预期 ~180 行
```

---

## 11. TDD 切片汇总

| 切片 | 步骤 | 验证 |
|------|------|------|
| 🔴 Red | Step 1 编写 ProjectSession 测试 | `pytest tests/test_project_session.py -q` → FAIL |
| 🟢 Green | Step 2-3 实现 ProjectSession + MainWindow 渐进引入 | `pytest tests/test_project_session.py -q` → PASS + `pytest tests/test_main_window.py -q` → PASS |
| 🔵 Refactor | Step 4-6 移除 MainWindow 重复逻辑 | `pytest tests/ -q` → 0 failed |

---

*本文档由 @architect 基于技术方案 v1.0 §3.1.1、任务图 T10、ADR-007 和现有代码 `app/main_window.py` (1246 行分散职责) 编写。*
