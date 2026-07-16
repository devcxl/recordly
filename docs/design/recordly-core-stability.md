# 技术方案: Recordly 核心稳定性与架构治理

**日期:** 2026-07-16
**状态:** Draft
**来源:** PRD `docs/prd/recordly-core-stability.md` + 审查报告 `docs/review/core-architecture-interaction-review-2026-07-16.md`
**Parent Issue:** #27

---

## 1. 需求概述

### 1.1 问题描述

Recordly 录制、项目持久化、重新打开、播放和导出链路存在以下阻断问题：
- **High:** 打开项目导出崩溃、录音未持久化、项目路径与目录契约冲突、录制启动/停止路径分散
  且缺少失败恢复、导出 worker 异常时 finished 信号不发出、GIF stderr 管道死锁、
  音频 source time / timeline time 混淆、托盘录制绕过项目创建、项目 FPS 与全局 FPS 混用。
- **Medium:** 临时文件 mktemp 竞态、非原子写入可能损坏数据、项目加载缺少 schema 校验、
  光标插值实现重复、启动失败清理覆盖原始异常、打开项目失败时破坏当前会话状态、
  录制停止失败窗口不恢复。
- **阻断项:** 测试基线 11 failed（含 mock 契约断裂、Recorder 新增 store_path 未更新
  FakeScreen、CursorSettings 旧字段不兼容等）。

`MainWindow` 1246 行，跨模块访问 6 个私有字段，导致相同业务动作存在多套不一致流程。

### 1.2 目标用户

使用 Recordly 桌面应用录制教程、产品演示或问题复现视频的个人用户。

### 1.3 成功标准

1. 全量测试 `0 failed`，无 skip/xfail 绕过
2. 审查报告中所有 ❌/⚠️ 流程通过自动化回归
3. MP4/GIF 导出时长误差 ≤ 1 帧
4. 音频时间线定位误差 ≤ 1 音频采样块
5. 取消/失败导出后无残留 FFmpeg 进程、临时文件
6. 项目保存异常时原 `project.json` 保持可读
7. `MainWindow` ≤ 800 行，不跨模块访问私有字段
8. 最终审查无 Critical/High

### 1.4 Out-of-Scope（不纳入本轮）

历史项目自动迁移、macOS 系统音频、FPS 转换/重采样、独立调音 UI、
日志文件轮转、远程错误上报、新编辑功能、云同步、Release 发布。
详见 `docs/dev/out-of-scope.md`。

---

## 2. 架构设计

### 2.1 现有技术栈复用

| 层级 | 技术 | 本轮复用说明 |
|------|------|-------------|
| UI | PyQt5 (QMainWindow, QStackedWidget, QThread, pyqtSignal) | 全量复用，不替换 |
| 合成 | Compositor + Effect 插件 | 全量复用，仅统一光标插值 |
| 录制 | Recorder (ScreenCapture + AudioCapture + PointerTracker) | 全量复用，仅修复启动失败清理 |
| 帧存储 | _CompressedFrameStore (JPEG 磁盘写入) | 全量复用 |
| 导出 | ExportWorker (ffmpeg-python) + QThread | 修复 stderr drain/mktemp/cancel 协议 |
| 项目 | Project dataclass + JSON + ProjectManager | 复用，增加原子写入和 schema 验证 |
| 配置 | AppConfig (QSettings) | 复用 |
| 音频 | sounddevice + ffmpeg subprocess | 复用，增加双音轨 WAV 持久化 |
| 测试 | pytest + unittest.mock | 复用，修复 mock 契约 |

**不引入任何新的运行时依赖。**

### 2.2 当前架构

```
┌─────────────────────────────────────────────────────┐
│ main.py (QSS 内联 228 行)                             │
│  └── MainWindow (1246 行)                             │
│       ├── 页面导航 (_switch_to_home / _switch_to_editor)│
│       ├── 录制生命周期 (2 套入口, 3 种路径)              │
│       ├── 项目创建/加载/保存 (_current_project_path 歧义) │
│       ├── 播放控制 (_create_playback_controller)       │
│       ├── 时间线同步 (_populate_timeline, _connect_*)  │
│       ├── 裁剪 (CropOverlay)                           │
│       ├── 导出线程管理 (QThread + ExportWorker)         │
│       └── 直接访问私有字段:                              │
│            _recorder.screen._store._offsets            │
│            _compositor._frames/_cursor_events/...      │
│            _timeline._tracks                           │
│            _playback._playing/_current_frame           │
└─────────────────────────────────────────────────────┘
            │                          │
   ┌────────▼────────┐     ┌──────────▼──────────┐
   │ core/recorder   │     │ core/exporter       │
   │ core/compositor │     │ (worker 异常不 emit  │
   │ core/project    │     │  finished; GIF stderr│
   │ core/camera     │     │  死锁; mktemp 竞态) │
   └─────────────────┘     └─────────────────────┘
```

### 2.3 目标架构

```
┌──────────────────────────────────────────────────────────┐
│ main.py                                                    │
│  ├── QSS → resources/style.qss (F23)                       │
│  └── config → MainWindow (≤800 行)                         │
│       ├── QStackedWidget: HomePage / EditorInterface        │
│       ├── 信号绑定 (不访问私有字段)                           │
│       └── 委托三个 Controller:                              │
│            ├── ProjectSession  (项目生命周期)               │
│            ├── RecordingController (录制状态机)              │
│            └── ExportController   (导出线程管理)             │
└──────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌─────────────┐ ┌──────────────┐ ┌──────────────────┐
│ProjectSession│ │RecordingCtrl │ │ExportController  │
│(纯 Python)   │ │(纯 Python)   │ │(QObject owner)   │
│              │ │              │ │                  │
│• 项目目录路径 │ │• 录制状态机   │ │• QThread 生命周期 │
│• Project 模型 │ │• 项目自动创建 │ │• 进度/取消信号    │
│• 媒体文件路径 │ │• 失败恢复     │ │• 资源清理        │
│• 原子 JSON 写 │ │• 状态回调     │ │• 确保单次 finished│
│• 音频 WAV 路径│ │              │ │                  │
└──────┬───────┘ └──────┬───────┘ └──────┬───────────┘
       │                │                │
       ▼                ▼                ▼
┌──────────┐  ┌──────────────┐  ┌──────────────────┐
│Project   │  │core/recorder │  │core/exporter     │
│Manager   │  │core/audio    │  │(stderr drain 统一 │
│(目录扫描) │  │core/screen   │  │ mktemp→mkstemp  │
└──────────┘  │core/pointer  │  │ 统一清理协议)     │
              └──────────────┘  └──────────────────┘
```

### 2.4 数据流向

```
录制流程:
  HomePage.record_requested
    → RecordingController.start_recording()
       → 创建 ProjectSession + 项目目录
       → Recorder.start_recording(project_dir)
       → 成功 → MainWindow._switch_to_editor()
       → 失败 → 恢复窗口 + 清理占位项目 + 通知用户

项目打开:
  HomePage.project_opened(path) 或 QFileDialog
    → 路径规范化 (project.json → 父目录)
    → ProjectSession.load(project_dir)
       → 独立临时 Project 校验
       → 校验通过 → 替换当前 ProjectSession + 加载到 Compositor
       → 校验失败 → 保持当前状态 + 错误提示

导出:
  ExportController.export(compositor, project_session, settings)
    → 创建 QThread + ExportWorker
    → worker 所有路径恰好发出一次 finished
    → 取消: terminate → wait → 删除临时文件 + 不完整输出
    → 完成后: ExportController 通知 MainWindow 显示结果

项目保存:
  _on_save_project()
    → ProjectSession.save(compositor, timeline, audio_regions)
       → 序列化 Project → 写入临时文件 → os.replace 原子替换
```

---

## 3. 模块拆分

### 3.1 新增模块

#### 3.1.1 ProjectSession (`app/project_session.py`)

**职责:** 拥有当前项目目录、Project 模型和媒体资源路径契约。MainWindow 通过 ProjectSession 获取/修改项目状态，不再直接访问 `_current_project_path` 和 compositor 私有字段。

**公开接口:**

```python
class ProjectSession:
    """当前项目会话 — 纯 Python 对象，非 QObject"""

    def __init__(self, project_dir: str):
        """
        Args:
            project_dir: 项目目录绝对路径（非 project.json 文件路径）
        Raises:
            FileNotFoundError: 项目目录不存在
            ValueError: project.json 损坏或不兼容
        """

    @property
    def project_dir(self) -> str: ...
    @property
    def project(self) -> Project: ...
    @property
    def project_file(self) -> str: ...      # project_dir/project.json
    @property
    def frames_data_path(self) -> str: ...  # project_dir/frames.data

    @classmethod
    def create(cls, projects_dir: str, name: str) -> "ProjectSession":
        """创建新项目目录 + 占位 project.json，返回 ProjectSession"""

    @classmethod
    def load(cls, project_dir: str) -> "ProjectSession":
        """从目录加载 Project + 校验 schema 兼容性。
        校验失败抛 ValueError 并保持参数 project_dir 不变。
        """

    def save(self, compositor_state: dict, timeline_tracks: list,
             audio_regions: list, crop_region, cursor_events,
             click_events, monitor_offset) -> None:
        """原子保存 project.json: 写临时文件 → os.replace。
        写入失败时原 project.json 不受影响。
        """

    def save_audio(self, mic_data: np.ndarray | None,
                   system_data: np.ndarray | None,
                   samplerate: int) -> None:
        """将麦克风/系统音频分别写入项目目录下的 WAV 文件，
        更新 project.source.audio_mic / project.source.audio_system 为相对路径。
        不持久化混音文件——播放/导出时按现有规则动态混音。
        """

    @staticmethod
    def normalize_path(input_path: str) -> str:
        """将 project.json 文件路径规范化为项目目录路径"""
```

**依赖方向:** ProjectSession → core/project.py (Project, SourceInfo), core/project_manager.py (仅用于 validate 逻辑共享)

**不与 Qt 耦合** — 纯 Python，可独立单元测试。

---

#### 3.1.2 RecordingController (`app/recording_controller.py`)

**职责:** 拥有录制生命周期状态机。所有录制入口（首页按钮、托盘菜单）通过 RecordingController 统一调度。成功/失败通过回调通知 MainWindow。

**状态机:**

```
                    ┌─────────┐
        start() ───▶│ STARTING│─── 异常 ───▶ FAILED(恢复窗口, 清理项目)
                    └────┬────┘
                         │ 成功
                    ┌────▼────┐
                    │RECORDING│
                    └────┬────┘
                         │ stop()
                    ┌────▼────┐
                    │STOPPING │─── 异常 → RECOVERY(帧可读则保留, 否则删除)
                    └────┬────┘
                         │ 成功
                    ┌────▼────┐
                    │   IDLE  │
                    └─────────┘
```

**公开接口:**

```python
class RecordingState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    STOPPING = "stopping"

class RecordingController:
    """录制控制器 — 纯 Python 对象"""

    def __init__(self, config: AppConfig):
        """config: 用于获取 projects_dir, default_fps"""

    @property
    def state(self) -> RecordingState: ...

    def start(self, project_dir: str | None = None) -> ProjectSession:
        """
        启动录制。
        - project_dir=None → 自动创建 ProjectSession
        - 返回创建的 ProjectSession
        Raises:
            RuntimeError: 已在录制中
            RecordingStartError: 启动失败 (含 recoverable 标记)
        """

    def stop(self) -> dict:
        """
        停止录制，返回 recorded_data (frames, audio, cursor_events, ...)。
        Raises:
            RecordingStopError: 停止异常 (含可恢复帧标记)
        """

    def set_callbacks(self,
                      on_state_changed: Callable[[RecordingState], None] | None = None,
                      on_error: Callable[[str, bool], None] | None = None):
        """设置状态变更和错误回调。on_error(msg, recoverable)"""

    def cleanup(self):
        """强制清理录制资源和项目占位目录"""
```

**依赖方向:** RecordingController → core/recorder.py, ProjectSession

**不与 Qt 耦合** — 纯 Python，可独立单元测试。

---

#### 3.1.3 ExportController (`app/export_controller.py`)

**职责:** 拥有 QThread + ExportWorker 生命周期管理。确保 finished 信号在所有路径恰好发出一次；统一取消/清理协议。

**公开接口:**

```python
class ExportController(QObject):
    """导出控制器 — QObject，管理 QThread 生命周期"""

    # 信号
    export_progress = pyqtSignal(int)          # 0-100
    export_finished = pyqtSignal(ExportResult)  # 所有路径恰好一次

    def __init__(self, parent=None): ...

    def start_export(self, compositor: Compositor,
                     project_session: ProjectSession,
                     settings: ExportSettings) -> None:
        """
        启动导出线程。
        - 从 project_session 获取音频数据路径
        - 创建 ExportWorker + QThread
        - 绑定 finished → quit → deleteLater
        Raises:
            RuntimeError: 已有导出进行中
        """

    def cancel(self) -> None:
        """取消当前导出。触发 worker.cancel() → terminate → wait → 清理"""

    @property
    def is_exporting(self) -> bool: ...
```

**终止协议（ExportWorker.run 内）:**

```python
def run(self):
    process = None
    stderr_thread = None
    temp_paths = []
    output_exists = False
    try:
        # ... 设置 process, stderr_thread, temp_paths ...
        # 所有帧写入
        process.stdin.close()
        returncode = process.wait()
        stderr_thread.join(timeout=5)
        output_exists = os.path.exists(s.output_path) and os.path.getsize(s.output_path) > 0
        if self._cancelled:
            result = ExportResult(False, s.output_path, error="已取消")
        elif returncode != 0 or not output_exists:
            result = ExportResult(False, s.output_path,
                error=f"FFmpeg 失败 (exit={returncode}):\n{stderr_text}")
        else:
            result = ExportResult(True, s.output_path, ...)
    except Exception as exc:
        result = ExportResult(False, s.output_path, error=f"导出异常: {exc}")
    finally:
        # 统一清理
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=5)
            except: process.kill()
        if stderr_thread: stderr_thread.join(timeout=3)
        for p in temp_paths:
            try: os.remove(p)
            except OSError: pass
        if self._cancelled and os.path.exists(s.output_path):
            try: os.remove(s.output_path)
            except OSError: pass
        self.finished.emit(result)
```

**stderr drain 统一方案:**

`_start_stderr_reader()` 已存在于 MP4 路径。GIF 路径在 `_export_gif()` 开头也调用同一函数，替换当前直接 `process.stderr.read()` 的方式。

---

### 3.2 修改现有模块

#### 3.2.1 `core/project.py`

| 改动 | 说明 |
|------|------|
| `Project.save()` → 原子写入 | 写临时文件 → `os.replace` |
| `Project.load()` → schema 严格验证 | **拒绝**未知字段和不可识别的未来版本；当前版本 optional 字段缺失使用默认值。旧 `CursorSettings.size/theme/color`、旧 `FrameStyle.margin/radius` 等未知字段均为不兼容 schema，拒绝加载并抛 `ValueError` |
| `_load_frame_style()` 边界编解码 | `FrameStyle.bg_color` 运行时类型 `tuple[int,int,int]`，JSON 持久化格式 `#RRGGBB` 字符串。`Project.save()` 边界 encode tuple→str，`Project.load()` 边界校验 `^#[0-9A-Fa-f]{6}$` 后 decode str→tuple。这是当前 schema 的正常序列化契约，不是历史迁移 |
| `Project._frame_count` → 显式属性 | 带类型注解 |
| `SourceInfo.audio_mic` / `audio_system` 字段路径写入 | 复用已有字段保存项目内相对 WAV 路径（如 `"audio_mic.wav"`）；不新增字段 |

**schema 验证策略:**

`Project.load()` 加载 JSON 后严格校验：
- 当前版本定义的键出现未知类型或未知键名 → 拒绝，抛 `ValueError`（含明确错误信息）
- 当前版本标记为 optional 的字段缺失 → 使用 dataclass 默认值
- 历史项目迁移明确为 Out-of-Scope：旧版 `CursorSettings.size/theme/color`、旧 `FrameStyle.margin/radius` 等未知字段安全拒绝且不破坏当前会话
- `FrameStyle.bg_color` 的 `#RRGGBB` ↔ `tuple` 转换是当前 schema 的边界编解码，不是迁移：运行时统一为 `tuple[int,int,int]`，JSON 持久化统一为 `#RRGGBB` 字符串

**安全拒绝协议（`_on_open_project` 中）:**
1. 先在新临时 Project 实例中完成 `Project.load()` 校验
2. 校验通过 → 替换当前 ProjectSession
3. 校验失败 → 保持原编辑状态不变，显示明确错误提示

#### 3.2.2 `core/exporter.py`

| 改动 | 说明 |
|------|------|
| `run()` → try/except/finally | 确保 `finished` 所有路径恰好一次；finally 统一清理 |
| GIF 复用 `_start_stderr_reader()` | 替换 `process.stderr.read()` |
| `tempfile.mktemp` → `tempfile.mkstemp` | 消除竞态 (F13) |
| MP4/GIF FPS 统一使用 `compositor.fps` | 替换 `settings.fps` 作为时间基准；移除 GIF 输出帧率覆盖逻辑 (F9) |
| `_build_audio_filtergraph` 分离 source time / timeline time | `atrim=start=source_start:end=source_end`, `adelay=start_ms` (F8) |
| 取消路径清理不完整输出文件 | `finally` 块中检查 `_cancelled` → `os.remove(output_path)` |
| `_DEBUG` → `logging` | 模块 logger，默认 WARNING (F21) |
| 移除 `__import__` 动态导入 | (F22) |

**音频 source time / timeline time 映射:**

```
源音频:
  atrim=start=region.source_start_ms/1000:end=region.source_end_ms/1000
  → 截取源文件的一段

时间线放置:
  adelay=region.start_ms|region.start_ms
  → 在时间线 start_ms 位置开始播放截取片段

（之前错误地将 start_ms/end_ms 同时用于 atrim 和 adelay）
```

#### 3.2.3 `core/recorder.py`

| 改动 | 说明 |
|------|------|
| `start_recording()` → finally 独立清理 | 对每个已启动资源 best-effort 清理，重新抛原始异常 |
| 记录已启动资源栈 | `_started_resources: list[callable]`，逆序关闭 |

#### 3.2.4 `core/compositor.py`

| 改动 | 说明 |
|------|------|
| `_interpolate_cursor_raw()` → 复用 `_interpolate_cursor()` 的二分逻辑 | 删除线性扫描版本 |
| 移除 `compose_index()` 中的 FPS debug 输出 | 替换为 logger.debug |
| `load_frames_data()` 中缓存 `_frame_times` 二分索引 | 可选优化，不阻塞 P0 |

#### 3.2.5 `core/camera.py`

| 改动 | 说明 |
|------|------|
| `_interpolate()` 缓存 `events` 时间数组 | 预计算 `_event_times: list[float]`，用 `bisect` 替代线性扫描 |
| `_calc_speed()` 复用缓存的 `_event_times` | 减少逐帧重复扫描 |

#### 3.2.6 `core/frame_style.py`

| 改动 | 说明 |
|------|------|
| `FrameStyle.bg_color` 运行时类型统一为 `tuple[int,int,int]` | 当前 dataclass 声明已是 tuple；不改为 str |
| JSON 持久化格式统一为 `#RRGGBB` 字符串 | `Project.save()` 边界显式 encode tuple→str；`Project.load()` 边界校验 `^#[0-9A-Fa-f]{6}$` 后 decode str→tuple |
| 测试分别固定运行时和序列化契约 (F24) | 运行时断言 `isinstance(bg_color, tuple)`；JSON 断言 `re.match(r'^#[0-9A-Fa-f]{6}$', bg_color_str)` |
| 拒绝旧 `margin/radius` 等未知字段 | 已由 §3.2.1 的 schema 严格验证覆盖 |

#### 3.2.7 `app/main_window.py`

**目标:** 从 1246 行缩减到 ≤800 行。

**删除的职责:**

| 原职责 | 迁移到 |
|--------|--------|
| `_current_project_path` 管理 | `ProjectSession.project_dir` |
| `_auto_create_project` / `_finalize_project` | `RecordingController.stop()` → `ProjectSession.save()` |
| 录制启动/停止 2 套入口 | `RecordingController.start()` / `stop()` |
| 导出 QThread 创建/绑定/清理 | `ExportController.start_export()` |
| `_cancel_export` | `ExportController.cancel()` |
| `_on_export_finished` 线程清理 | `ExportController.export_finished` 信号 |
| 私有字段访问 (`_compositor._frames` 等) | 通过 ProjectSession 或公共方法 |
| 项目路径规范化 | `ProjectSession.normalize_path()` |

**保留的职责:**

- QStackedWidget 页面切换
- 菜单栏/工具栏可见性管理
- 信号绑定 (connect 各 Controller 信号到 UI)
- 播放控制
- 时间线同步
- 裁剪/缩放编辑
- 设置对话框

#### 3.2.8 `main.py`

| 改动 | 说明 |
|------|------|
| QSS 移至 `resources/style.qss` | `DARK_STYLESHEET` 常量删除，改用文件读取 |
| 添加 `logging.basicConfig` | `RECORDLY_DEBUG=1` 时 level=DEBUG，默认 WARNING |

#### 3.2.9 `resources/style.qss` (新增)

将 `main.py` 中 `DARK_STYLESHEET` (228 行) 完整移入，不改变任何样式规则。

---

### 3.3 文件变更总览

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `app/project_session.py` | **新增** | ~180 |
| `app/recording_controller.py` | **新增** | ~200 |
| `app/export_controller.py` | **新增** | ~180 |
| `resources/style.qss` | **新增** | ~240 |
| `app/main_window.py` | 修改 | 1246 → ≤800 |
| `core/exporter.py` | 修改 | ~100 行改动 |
| `core/project.py` | 修改 | ~50 行改动 |
| `core/recorder.py` | 修改 | ~30 行改动 |
| `core/compositor.py` | 修改 | ~30 行改动 |
| `core/camera.py` | 修改 | ~20 行改动 |
| `core/frame_style.py` | 修改 | ~10 行改动 |
| `main.py` | 修改 | ~50 行改动 |
| `tests/conftest.py` | 修改 | ~20 行改动 |
| `tests/test_*.py` | 修改 | ~200 行改动 (修复 11 个失败) |

**合计: 14 个文件变更（4 新增 + 10 修改）。超过 10 个文件阈值，按 PRD 分三批交付:**

| 批次 | 范围 | 文件数 | 独立验证 |
|------|------|--------|----------|
| **P0** | 测试基线修复 + 导出崩溃 + 项目路径 + 录制恢复 | 7 | 全量测试 0 failed |
| **P1** | ProjectSession + RecordingController + ExportController 提取 | 9 (含 P0 文件) | 集成测试通过 + MainWindow ≤800 行 |
| **P2** | logging/QSS/FrameStyle/插值性能 | 6 | QSS 视觉一致 + logger 输出正确 |

---

## 4. 接口设计

### 4.1 ProjectSession 数据模型

项目目录结构（目标）:

```
~/Recordly/projects/20260716_143022_录制项目名/
├── project.json        # 原子写入
├── frames.data         # JPEG 压缩帧 (已有)
├── frames.idx          # 帧偏移索引 (已有)
├── audio_mic.wav       # 麦克风录音 (新增)
├── audio_system.wav    # 系统音频录音 (新增)
└── thumbnail.png       # 缩略图 (已有)
```

混音不持久化。播放/导出时从 `audio_mic.wav` + `audio_system.wav` 按现有规则动态混音。

### 4.2 Project.save() 原子写入协议

```python
def save(self, path: str):
    data = self._to_dict()
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".project-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)  # 原子替换 (POSIX)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

### 4.3 项目 FPS 单一时间基准

```
规则: MP4 与 GIF 导出始终使用 compositor.fps 作为唯一时间基准。
      本轮不做任何 FPS 转换/重采样。

MP4 导出:
  ffmpeg.input(..., r=compositor.fps)
  output duration = total_frames / compositor.fps

GIF 导出:
  ffmpeg.input(..., r=compositor.fps)   # 与 MP4 一致
  output duration = total_frames / compositor.fps

音频:
  动态混音 WAV 时长 = total_frames / compositor.fps
```

### 4.4 录制失败恢复状态机（详细）

```
启动录制:
  1. 创建 ProjectSession + 项目目录
  2. 写占位 project.json (原子写入)
  3. 启动 recorder
     ├── 成功 → 状态=RECORDING, 通知 UI
     └── 异常:
         ├── 停止所有已启动资源 (逆序)
         ├── 检查帧数据是否可读
         │   ├── 有可读帧 → 状态=RECOVERY, 保留项目, 恢复窗口
         │   └── 无帧 → 状态=FAILED, 删除项目目录, 恢复窗口
         └── 重新抛异常通知 MainWindow

停止录制:
  1. recorder.stop_recording()
     ├── 成功 → 收集数据, ProjectSession.save(), 切换编辑器
     └── 异常:
         ├── 检查 self.screen.error 和帧数据
         │   ├── screen.error 非空 + 有可读帧 → RECOVERY, 保留项目
         │   ├── screen.error 非空 + 无帧 → FAILED, 清理
         │   └── 其他异常 + 有帧 → RECOVERY
         └── 恢复窗口 (showNormal + raise_)
```

### 4.5 关键接口签名汇总

```python
# ── ProjectSession ──
ProjectSession.create(projects_dir: str, name: str) -> ProjectSession
ProjectSession.load(project_dir: str) -> ProjectSession
ProjectSession.normalize_path(input_path: str) -> str  # @staticmethod
session.save(compositor_state, timeline_tracks, audio_regions,
             crop_region, cursor_events, click_events, monitor_offset)
session.save_audio(mic, system, samplerate)

# ── RecordingController ──
controller.start(project_dir: str | None = None) -> ProjectSession  # raises RecordingStartError
controller.stop() -> dict        # raises RecordingStopError
controller.state -> RecordingState
controller.set_callbacks(on_state_changed, on_error)
controller.cleanup()

# ── ExportController ──
controller.start_export(compositor, project_session, settings)
controller.cancel()
controller.is_exporting -> bool
# 信号: export_progress(int), export_finished(ExportResult)

# ── ExportWorker (修改后) ──
worker.run()      # try/except/finally, 确保 finished 恰好一次
worker.cancel()   # 设置 _cancelled + terminate process

# ── Project (修改后) ──
Project.save(path)  # 原子写入
Project.load(path) -> Project   # schema 严格验证, raises ValueError
```

---

## 5. 实施计划

### 5.1 子任务拆分（按 PRD 批次）

#### P0: 发布阻断修复

| # | 子任务 | 涉及文件 | 验收标准 |
|---|--------|---------|---------|
| P0-1 | 恢复测试基线 (11 failed → 0) | `tests/conftest.py`, `tests/test_*.py`, `core/project.py` | `pytest -q` 全绿 |
| P0-2 | 修复打开项目导出崩溃 (F2) | `core/exporter.py`, `app/main_window.py` | 项目卡片打开 → 导出不崩溃 |
| P0-3 | 项目路径规范化 (F3, F4) | `app/main_window.py` (渐进, P1 移入 ProjectSession) | 选 project.json 能正确打开 |
| P0-4 | 统一录制入口 + 失败恢复 (F5, F6) | `app/main_window.py`, `core/recorder.py` | 启动/停止失败恢复窗口 |
| P0-5 | 双音轨持久化 (F7) | `core/recorder.py`, `core/project.py`, `app/main_window.py` | 保存 → 重启 → 导出有音频 |
| P0-6 | 音频 source/time 分离 (F8) | `core/exporter.py` | 移动/裁剪/变速后音画同步 |
| P0-7 | 项目 FPS 单一基准 (F9) | `core/exporter.py` | 不同 FPS 项目导出时长正确 |
| P0-8 | ExportWorker finished 保证 (F10, F11, F12) | `core/exporter.py` | 取消/失败/异常后无残留 |

**预计文件变更: 7 个 (test 多个文件计为 1 组)**

#### P1: 安全与架构治理

| # | 子任务 | 涉及文件 | 验收标准 |
|---|--------|---------|---------|
| P1-1 | 提取 ProjectSession (F14, F16) | `app/project_session.py` (新), `core/project.py`, `app/main_window.py` | 原子写入 + 路径契约清晰 |
| P1-2 | 提取 RecordingController (F17) | `app/recording_controller.py` (新), `app/main_window.py` | 录制入口统一 + 状态机覆盖 |
| P1-3 | 提取 ExportController (F11, F15, F18) | `app/export_controller.py` (新), `core/exporter.py`, `app/main_window.py` | finished 单次 + 清理完整 |
| P1-4 | MainWindow 缩减 + 私访消除 (F19) | `app/main_window.py` | ≤800 行 + 无跨模块私访 |
| P1-5 | 替换 mktemp (F13) | `core/exporter.py` | 全量 mkstemp + 测试覆盖 |

**预计文件变更: 9 个 (含 P0 文件继续修改)**

#### P2: 质量收尾

| # | 子任务 | 涉及文件 | 验收标准 |
|---|--------|---------|---------|
| P2-1 | logging 统一 (F21, F22) | `core/compositor.py`, `core/exporter.py`, `core/recorder.py`, `main.py` | `RECORDLY_DEBUG=1` 时输出 debug |
| P2-2 | QSS 提取 (F23) | `main.py`, `resources/style.qss` (新) | UI 视觉不变 |
| P2-3 | FrameStyle.bg_color 统一 (F24) | `core/frame_style.py`, `core/project.py`, `tests/` | 类型 + 测试契约一致 |
| P2-4 | 光标插值性能 (F20) | `core/compositor.py`, `core/camera.py` | 二分查找 + 缓存时间索引 |
| P2-5 | 函数长度 ≤50 行 (F25) | 所有修改文件 | 新增/修改函数不超过 50 行 |

**预计文件变更: 6 个**

### 5.2 渐进式迁移顺序

```
P0-1 (测试基线) → P0-2~P0-8 (正确性修复)
  ↓ P0 完成后: 全量测试 0 failed, 核心流程可用
P1-1 (ProjectSession) → P1-4 (MainWindow 缩减)
  ↓ 引入 ProjectSession 后 MainWindow 逐步委托
P1-2 (RecordingController) → 替换录制入口
P1-3 (ExportController) → 替换导出入口
  ↓ P1 完成后: 架构目标达成
P2-1~P2-5 (质量收尾)
  ↓ 最终审查通过
```

**核心原则: 每批完成后全量测试必须 0 failed。不在 P0 未完成时启动 P1 抽象。**

### 5.3 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 测试 mock 契约修复引发二次回归 | 中 | 高 | P0-1 只修复 mock 契约和 schema 兼容，不引入新逻辑 |
| ProjectSession 引入后 MainWindow 信号连接断裂 | 中 | 中 | P1-1 保持 `_on_open_project` 签名兼容，先加 ProjectSession 再切信号 |
| ExportWorker finally 清理覆盖不全 | 低 | 高 | P1-3 验收测试覆盖: 取消/FFmpeg 不存在/BrokenPipe/异常四种路径 |
| 音频 WAV 文件过大 | 低 | 低 | 44100Hz × 2ch × 16bit × 600s ≈ 100MB，桌面场景可接受 |
| 原子写入在某些文件系统不保证 | 低 | 中 | `os.replace` 在 Linux ext4/NTFS 上原子；Windows FAT32 不支持但非目标平台 |
| 超过 10 文件阈值导致审查困难 | 高 | 中 | 按 P0/P1/P2 分批 PR，每批 ≤7 文件 |

---

## 6. 测试策略

### 6.1 测试金字塔

```
        ┌──────┐
        │ E2E  │  手动验收: Linux 核心流程 + Windows 兼容
        ├──────┤
        │ 集成  │  pytest + QTest: 录制→保存→打开→导出 全链路
        ├──────┤
        │ 单元  │  pytest: 每个 Controller/Worker 独立测试
        └──────┘
```

### 6.2 必须自动化的回归场景

| 场景 | 测试位置 | 类型 |
|------|---------|------|
| 首页录制启动失败后恢复 | `tests/test_recording_controller.py` (新) | 单元 |
| 屏幕采集停止失败后恢复 | `tests/test_recording_controller.py` | 单元 |
| 托盘录制创建新项目 | `tests/test_main_window.py` | 集成 |
| project.json 文件选择能打开 | `tests/test_main_window.py` | 集成 |
| 打开损坏项目后状态不变 | `tests/test_project_session.py` (新) | 单元 |
| 项目卡片打开后可导出 | `tests/test_main_window.py` | 集成 |
| 双音轨保存→重新打开→导出 | `tests/test_exporter.py` | 集成 |
| 不同 FPS 导出时长正确 | `tests/test_exporter.py` | 单元 |
| 音频移动/裁剪/变速后导出正确 | `tests/test_exporter.py` | 单元 |
| FFmpeg 不存在时 worker 结束 | `tests/test_exporter.py` | 单元 |
| GIF 大量 stderr 不死锁 | `tests/test_exporter.py` | 单元 |
| 取消导出无残留 | `tests/test_export_controller.py` (新) | 单元 |
| 原子保存异常时原 JSON 可读 | `tests/test_project_session.py` | 单元 |

### 6.3 测试基础设施改进

- `tests/conftest.py`: 移除全局 `cv2` MagicMock，改为按需 mock
- `FakeScreen` 更新 `store_path` 参数合约
- `test_playback_receives_recorded_audio_and_video_edit_map`: 添加 `preview.set_fps()` mock
- 新 Controller 测试使用 `pytest.fixture` 注入 mock 依赖，不依赖全局 MagicMock

### 6.4 验收命令

```bash
# 单元 + 集成测试
.venv/bin/python -m pytest -q

# 可选：覆盖率观测（不作为完成条件）
.venv/bin/python -m pytest --cov=app --cov=core --cov-report=term-missing

# Debug 模式诊断
RECORDLY_DEBUG=1 .venv/bin/python main.py

# 代码行数检查
wc -l app/main_window.py   # 应 ≤800
```

---

## 7. 技术选型与约束

### 7.1 技术栈

| 层级 | 选型 | 版本约束 |
|------|------|---------|
| 语言 | Python | 3.11+ |
| UI | PyQt5 | 5.15.x |
| 视频 | FFmpeg (系统依赖) | 4.x+ |
| 图像 | Pillow, NumPy, OpenCV | 现有版本 |
| 音频 | sounddevice | 现有版本 |
| 测试 | pytest | 现有版本 |

### 7.2 编码规范

- 新 Controller 为**纯 Python 类**（非 QObject），除非必须发信号
- ExportController 是唯一 QObject（需要 moveToThread 信号机制）
- 所有公开方法有类型注解
- 新增/修改函数原则上 ≤50 行 (F25)
- 使用 `logging.getLogger(__name__)` 统一日志

### 7.3 安全约束

- 临时文件使用 `tempfile.mkstemp`，禁止 `mktemp`
- 项目 JSON 原子写入（临时文件 + os.replace）
- FFmpeg 子进程超时保护（wait timeout + kill fallback）
- 导出失败不残留不完整输出文件

---

## 8. 附录: 与现有 ADR 的关系

| ADR | 决策 | 本轮影响 |
|-----|------|---------|
| ADR-001 | 目录扫描项目存储 | 继续遵循；ProjectSession 封装目录路径契约 |
| ADR-002 | 缩略图侧车文件 | 不受影响 |
| ADR-003 | 卡片网格展示 | 不受影响 |
| ADR-005 | 双页面架构 | 继续遵循；RecordingController 支持从首页和托盘发起 |
| ADR-006 | JSON 持久化 | 增强为原子写入；复用 SourceInfo.audio_mic/audio_system 持久化音频路径 |

---

*本方案由 @architect 基于 PRD v1.0 和审查报告 a46f24f 编写。implementation 由 @backend 和 @frontend 按 P0→P1→P2 顺序执行。*
