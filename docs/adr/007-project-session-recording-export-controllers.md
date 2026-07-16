# ADR-007: ProjectSession + RecordingController + ExportController 架构提取

**日期:** 2026-07-16
**状态:** Proposed
**决策者:** @architect
**影响范围:** `app/` 架构层、`core/exporter.py`、`core/project.py`

---

## 背景

`MainWindow` 当前 1246 行，承担页面导航、录制生命周期、项目创建/加载/保存、播放控制、时间线同步、导出线程管理共七类职责。同时直接访问以下私有实现：

```text
_recorder.screen._store._offsets
_compositor._frames / _cursor_events / _click_events / _clips
_timeline._tracks
_playback._playing / _current_frame
```

审查报告证实：这种架构导致同一录制动作存在多套启动路径（首页按钮 vs 托盘菜单，各自
绕过 `_on_recording_started` 异常恢复）、项目路径同时被当作目录和文件处理
（`_current_project_path` 歧义）、运行时音频与持久化音频脱节（`SourceInfo.audio_mic`
从未写入）、时间线时间与源媒体时间混用等实际缺陷。

## 决策

**提取三个独立对象替代 `MainWindow` 中的分散逻辑：`ProjectSession`、`RecordingController`、`ExportController`。**

不继续扩展 `MainWindow`，也不一次性重写整个应用。

### 三个对象职责边界

| 对象 | 拥有 | 不拥有 |
|------|------|--------|
| **ProjectSession** | 项目目录路径、Project 模型、媒体资源路径、原子 JSON 写入 | UI 状态、录制、导出 |
| **RecordingController** | 录制状态机、Recorder 实例、项目自动创建、失败恢复 | 合成器、时间线、导出 |
| **ExportController** | QThread 生命周期、ExportWorker 管理、取消/清理协议 | 录制、项目持久化 |

### 依赖方向

```
MainWindow (UI 组装)
  ├── ProjectSession      (纯 Python, 可独立测试)
  ├── RecordingController (纯 Python, 依赖 ProjectSession)
  └── ExportController    (QObject, 依赖 ProjectSession + Compositor)
```

所有 Controller 不互相依赖，仅通过 MainWindow 协调。

## 理由

### 为什么不是继续扩展 MainWindow

1. **状态所有权不明确。** `_current_project_path` 同时承载"当前编辑的项目目录"和"录制目标路径"，托盘录制在 `_current_project_path is None` 时直接返回，已有项目被新录制覆盖。
2. **异常恢复路径发散。** `_on_home_record` 中 `QTimer.singleShot(500, self._start_recording_from_home)` 抛出的异常无法被 `_on_recording_started` 的 try/except 捕获，因为没有复用同一入口。
3. **测试脆弱。** 测试 `_update_frame_counter` 需要 mock 整个 `SimpleNamespace`，而不是测试明确接口。`_on_open_project` 测试需要理解组件清空顺序才能正确 mock。
4. **扩展线性退化。** 每新增一条路径（如托盘快速录制）都需要在 MainWindow 中添加新的信号→槽对和 `if project_path is None` 分支。

### 为什么不是一次性重写

1. **风险集中。** 1246 行一次性重写意味着所有测试需要同时重建，无法渐进验证。
2. **违反 KISS。** 审查报告中大部分阻断问题是正确性缺陷（导出崩溃、音频丢失、FPS 混用），不是架构过度耦合。修复正确性问题不需要重构整个窗口。
3. **PRD 明确要求。** 审查报告建议"先修正确性，不先大重构"，PRD 第 4.2 节要求"不以大规模一次性重写替代渐进式重构"。

### 为什么是三个对象而非更多/更少

- **ProjectSession 是必需的最小抽象。** 所有项目路径歧义、音频路径缺失、非原子写入问题都源于没有统一的项目会话对象。提取为独立对象后，`_current_project_path`、`SourceInfo` 字段、`project.json` 写入都收敛到一个地方。
- **RecordingController 是必需的最小抽象。** 当前 3 条录制路径（首页录制、托盘录制、`_toggle_record` fallback）共享 Recorder 实例但不共享异常恢复逻辑。提取为状态机后所有路径收敛到 `start()`/`stop()`。
- **ExportController 是必需的最小抽象。** `_on_export` 中 QThread 创建、信号绑定、`_cancel_export` 和 `_on_export_finished` 分散在 5 个方法中。提取后统一了线程生命周期和清理协议。
- **不再提取 PlaybackController 或 TimelineController。** 播放控制和时间线同步虽然也在 MainWindow 中，但没有形成多套不一致路径，且已经通过 `PlaybackController` 类（`ui/preview_widget.py`）封装了播放逻辑。MainWindow 中的播放代码是薄的信令层，不值得提取为独立 Controller。

## 备选方案

### 方案 A: 使用 MVC 框架重写

提取 Model (ProjectSession + data)、View (MainWindow + widgets)、Controller (Recording + Export + Playback) 三层。引入信号总线解耦 Controller 之间通信。

**拒绝理由:** 过度设计。三个 Controller 已经够用；引入信号总线增加理解成本，且 PyQt 已有信号机制无需另外抽象。

### 方案 B: 只修复 bug，不提取 Controller

只修复导出崩溃、音频持久化、FPS 混用等正确性问题，继续在 MainWindow 中管理所有状态。

**拒绝理由:** 不解决状态所有权问题。审查报告已证明当前架构是缺陷的根源，不是巧合。下次新功能（如画中画、批注导出）会再次产生同样的路径分叉问题。

### 方案 C: 全部提取到 `core/` 层

将 ProjectSession、RecordingController、ExportController 放入 `core/` 包，完全脱离 Qt。

**部分采纳。** ProjectSession 和 RecordingController 放 `app/` 而非 `core/` 的理由：
- 它们使用 `AppConfig`（Qt QSettings 依赖）获取 `projects_dir`
- RecordingController 需要了解"创建项目 → 切换编辑器"的应用级流程
- `core/` 保持为 Qt 无关的纯领域逻辑层
- ExportController 必须是 QObject（需要 moveToThread），放 `core/` 破坏分层

## 影响

### 文件变更

- **新增:** `app/project_session.py` (~180 行), `app/recording_controller.py` (~200 行), `app/export_controller.py` (~180 行)
- **修改:** `app/main_window.py` (1246→≤800 行), `core/exporter.py`, `core/project.py`, `core/recorder.py`, `core/compositor.py`, `core/camera.py`, `core/frame_style.py`, `main.py`
- **修改:** `tests/conftest.py`, `tests/test_main_window.py`, `tests/test_exporter.py`, `tests/test_project.py`, 新增 `tests/test_project_session.py`, `tests/test_recording_controller.py`, `tests/test_export_controller.py`

### 接口契约

`MainWindow` 不再通过 `self._compositor._frames` 访问帧数据。改为通过 `ProjectSession` 或 `Compositor` 公开方法获取。

`MainWindow` 不再直接设置 `self._current_project_path`。改为调用 `ProjectSession.create()` / `.load()`。

### 测试影响

- 新 Controller 可独立单元测试（纯 Python 对象，注入 mock 依赖）
- MainWindow 测试关注信号绑定和 UI 行为，不再测试业务逻辑
- 录制状态机可覆盖 5 种状态 × 3 种异常路径 = 15 个测试用例

### 兼容性

- `project.json` **仅保证当前 schema 兼容**；不兼容版本（旧版字段不可识别或未来版本格式未知）安全拒绝并抛 `ValueError`，同时不破坏当前会话状态
- 不影响 ADR-001~006 的已有决策
- `ProjectManager` API 保持不变（ProjectSession 内部调用）
- `SourceInfo.audio_mic` / `audio_system` 复用已有字段保存项目内相对 WAV 路径（不新增字段）

### 迁移路径

```
P0: 修复所有正确性缺陷，全量测试 0 failed
    ↓
P1: MainWindow 中引入 ProjectSession（先加后切: 保留 _current_project_path 同时设 ProjectSession）
    → 添加 RecordingController（统一 start/stop 入口）
    → 添加 ExportController（抽取 QThread 管理）
    → MainWindow 缩减到 ≤800 行
    ↓
P2: 质量收尾
```

---

*本 ADR 作为 ADR-007 记录，与 ADR-005（双页面架构）和 ADR-006（JSON 持久化）形成完整的架构决策链。*
