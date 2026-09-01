# Recordly 核心代码、架构与交互流程审查报告

**日期：** 2026-07-16  
**范围：** 当前仓库整体，重点检查录制、项目持久化、重新打开、播放与导出链路  
**基线：** `a46f24f`  
**结论：** ❌ 不通过；存在 High 问题，且测试基线失败

## 1. 执行摘要

- 未发现已证实的 Critical 漏洞。
- 发现 10 项 High、9 项 Medium、3 项 Low。
- 最严重的用户流程问题是：已有项目可进入编辑器，但导出会因 `_recorded_data is None` 崩溃；即使修复崩溃，原始录音也没有持久化，重新打开后导出的视频会丢失录音。
- `MainWindow` 已增长到 1246 行，并直接操作多个模块的私有状态，导致状态契约分散、测试脆弱和交互分支行为不一致。
- 实际执行 `.venv/bin/python -m pytest -q`：**290 passed、11 failed、1 skipped**，当前不可合并或发布。

## 2. 阻断问题

### **[HIGH]** `app/main_window.py:920`

**问题：** 打开已有项目并加载到帧后，用户确认导出会访问空对象。

`_on_open_project()` 在第 1068 行将 `_recorded_data` 设为 `None`，而 `_on_export()` 在第 920 行无条件执行：

```python
audio = self._recorded_data.get("audio")
```

入口校验允许“没有 `_recorded_data`、但 compositor 有帧”的已打开项目继续导出，因此会触发 `AttributeError`。

**受影响流程：** 首页项目卡片 → 打开项目 → 导出。

**修复：** 使用与 `_create_playback_controller()` 一致的空值处理；同时补充该完整流程的回归测试。

---

### **[HIGH]** `app/main_window.py:519-550`、`core/project.py:166-175`

**问题：** 原始录音只存在于内存 `_recorded_data["audio"]`，项目保存时只持久化 `frames.data`，`SourceInfo.audio_mic` 和 `audio_system` 从未写入。重新打开项目后，即使修复上述空对象崩溃，导出仍会丢失麦克风和系统音频。

**受影响流程：** 录制 → 保存 → 退出/重启 → 打开项目 → 导出。

**修复：** 录制完成时将最终混音或独立音轨安全写入项目目录，在 `SourceInfo` 中保存相对路径；打开项目时恢复为导出器可消费的音频源。应优先采用“持久化一个最终混音 WAV”的简单方案，除非产品明确要求后续分别编辑麦克风和系统音轨。

---

### **[HIGH]** `app/main_window.py:446-453`、`core/project_manager.py:101-106`

**问题：** “打开项目”文件选择器返回 `project.json` 文件路径，但 `ProjectManager.open_project()` 的契约是项目目录，并会再次拼接 `/project.json`。

**实际结果：** 选择 `/projects/demo/project.json` 后尝试打开 `/projects/demo/project.json/project.json`，功能不可用。

**修复：** 在 UI/Session 边界将输入统一规范化为项目目录，再将该目录用于 `_current_project_path`、视频相对路径解析和后续保存。只让 `ProjectManager.open_project()` 兼容两种输入还不够，否则 MainWindow 仍会把文件路径当作目录使用。

---

### **[HIGH]** `app/main_window.py:439-444`、`app/main_window.py:466-473`

**问题：** 首页录制走 `_start_recording_from_home()`，直接调用 recorder，绕过已有的 `_on_recording_started()` 异常恢复逻辑。麦克风、屏幕或权限初始化失败时，QTimer 回调异常逃逸，窗口可能保持最小化，预创建的空项目目录残留，用户得不到错误通知。

**修复：** 合并为单一录制启动入口，参数化 `project_dir`；所有入口必须复用同一状态转换和错误恢复逻辑。

---

### **[HIGH]** `core/exporter.py:92-97`

**问题：** `ExportWorker.run()` 没有顶层异常处理。FFmpeg 不存在、临时文件创建失败、编码器初始化失败或任何未预期异常都会导致 `finished` 信号不发出。`MainWindow` 依赖该信号关闭进度框并退出 QThread，因此 UI 可能永久停留在导出中。

**修复：** `run()` 必须捕获异常并在所有路径恰好发出一次 `finished(ExportResult(...))`；资源回收放入 `finally`。增加 FFmpeg 启动失败和渲染异常测试。

---

### **[HIGH]** `core/exporter.py:285-315`

**问题：** GIF 导出把 FFmpeg stderr 连接到 PIPE，但写帧期间不持续读取。长时间导出时 stderr 管道可能填满，FFmpeg 阻塞，主线程又在等待 stdin 写入或 process 结束，形成死锁。

MP4 路径已有 `_start_stderr_reader()`，GIF 路径未复用。

**修复：** GIF 和 MP4 共用持续 drain stderr 的实现，并确保取消、BrokenPipe、成功和异常路径都 join reader、wait process、清理状态。

---

### **[HIGH]** `core/exporter.py:359-387`、`app/main_window.py:999-1005`

**问题：** 音频导出混淆“时间线位置”和“源文件裁剪区间”。

- 额外音频使用 `start_ms/end_ms` 裁剪源文件，完全忽略 `source_start_ms/source_end_ms`。
- 原始录音按视频 Clip 的 `start/end` 裁剪，忽略 `source_start/source_end`。
- `start` 应只决定输出时间线上的 delay，不能同时决定源文件从哪里开始读取。

**实际影响：** 音频移动到非零播放头、裁剪头尾或随视频变速后，可能导出错误片段、静音或音画不同步。`tests/test_exporter.py:107-134` 当前还把错误行为固化成测试预期。

**修复：** 源音频 `atrim` 使用 `source_start/source_end`，`adelay` 使用时间线 `start`；补充移动、裁剪和变速组合测试。

---

### **[HIGH]** `app/main_window.py:393-395,457-469,519-550`

**问题：** 托盘录制绕过项目会话创建。

- 首次启动后从托盘录制时，`_current_project_path` 为空，`_finalize_project()` 直接返回，录制只存在于内存和临时帧文件，无法正常保存。
- 如果此前打开过项目，`_current_project_path` 仍指向旧项目；新录制可能覆盖旧项目的 `project.json/frames.idx`，但帧数据又写在临时文件中，造成旧项目元数据与 `frames.data` 不一致。

**修复：** 所有录制入口必须先创建新的 ProjectSession 和项目目录，再进入统一录制状态机；禁止复用上一个项目路径。

---

### **[HIGH]** `app/main_window.py:909,1109-1110`、`core/exporter.py:121,127-128,146`

**问题：** 打开项目后，MP4 导出使用当前全局配置的 FPS，而不是项目/Compositor 的 FPS。渲染帧数和音频时长基于 `compositor.fps`，FFmpeg 输入时间基准却来自 `settings.fps`，两套时间基准可能不一致。

**实际影响：** 打开 60 FPS、600 帧的 10 秒项目，而当前配置为 30 FPS 时，视频可能按 20 秒编码，音频提前结束并产生音画不同步。

**修复：** MP4 输入时间基准使用项目的 `compositor.fps`。如果产品允许导出时修改 FPS，必须显式重采样帧，而不是只修改 FFmpeg 的输入 `r`。

---

### **[HIGH]** 测试基线失败

**验证命令：**

```bash
.venv/bin/python -m pytest -q
```

**结果：** `11 failed, 290 passed, 1 skipped`

主要失败类型：

1. `Project.load()` 无法加载测试定义的旧版 `CursorSettings` 字段，旧项目兼容失败。
2. `tests/conftest.py:32-39` 无条件把未导入的 `cv2` 替换为 `MagicMock`，但帧存储测试又要求真实 `imencode/imdecode`，测试基础设施自相矛盾。
3. Recorder 新增 `store_path` 后，多处 FakeScreen 契约未更新。
4. Recorder 每次启动会替换 `screen` 实例，原有实例级 monkeypatch 失效，测试错误地进入伪造的 mss 采集流程。
5. `test_playback_receives_recorded_audio_and_video_edit_map` 未同步新增的 `preview.set_fps()` 契约。

**修复：** 先恢复全绿基线，再处理架构重构。测试替身必须模拟明确接口，不应依赖全局 `MagicMock` 隐式吞掉调用。

## 3. 重要问题

### **[MEDIUM]** `core/exporter.py:403,453`

**问题：** 使用 `tempfile.mktemp()` 产生竞态窗口，临时路径在创建前可能被同机进程抢占。

**修复：** 使用 `NamedTemporaryFile(delete=False)` 或 `mkstemp()`，关闭句柄后再交给 wave/FFmpeg。该问题属于安全缺陷，但在当前本地桌面应用、未展示提权边界的情况下，不足以定为 Critical。

---

### **[MEDIUM]** `core/exporter.py:20`、`core/compositor.py:434-446`

**问题：** 导出 debug 永久开启；播放每 60 帧无条件写 stderr。会泄露本地路径、污染终端并产生持续 I/O。

**修复：** 使用模块 logger；debug 默认关闭，由环境变量或应用配置启用。移除 `__import__()` 动态导入。

---

### **[MEDIUM]** `core/recorder.py:61-68`

**问题：** 启动失败后的 `finally` 清理可能用 `screen.stop()` 等二次异常覆盖原始异常，且没有停止 pointer。

**修复：** 对每个已启动资源独立 best-effort 清理并记录清理错误，最终重新抛出原始异常。更理想的是记录启动成功的资源栈并逆序关闭。

---

### **[MEDIUM]** `core/exporter.py:186-225,288-316`

**问题：** 取消和 BrokenPipe 路径未统一等待进程、关闭管道和删除临时 WAV，可能留下子进程或临时文件。

**修复：** 单一 `finally` 负责 stdin、process、reader 和临时文件生命周期。

---

### **[MEDIUM]** `core/project.py:230-263`

**问题：** 项目加载直接将 JSON 字典展开到 dataclass，缺少按版本字段过滤/迁移。当前测试已证明旧 `CursorSettings` 的 `size/theme/color` 会导致 `TypeError`；旧 FrameStyle 的 `margin/radius` 也存在同类风险。

**修复：** 为每个版本提供显式迁移，将未知字段过滤掉，并在迁移后构造当前模型。不要依赖注释宣称兼容。

---

### **[MEDIUM]** `core/compositor.py:220-272`、`core/camera.py:59-78`

**问题：** 光标插值实现重复且复杂度不一致：一处二分，一处线性；Camera 每次插值扫描事件两遍，并被逐帧重复调用。

**修复：** 抽取单一二分插值函数，并缓存事件时间数组。属于性能与一致性问题，不应高于核心流程正确性问题。

---

### **[MEDIUM]** `core/project.py:203-227`

**问题：** `Project.save()` 直接覆盖 `project.json`，进程中断或磁盘写失败会损坏唯一项目元数据；同项目的 rename 已采用临时文件 + `os.replace()`，实现不一致。

**修复：** 复用原子 JSON 写入函数。

---

### **[MEDIUM]** `app/main_window.py:1067-1082`

**问题：** 打开新项目时先清空当前 compositor、播放和编辑状态，之后才验证目标项目。目标损坏、缺失或格式错误时，打开操作虽然报错，但当前会话已被部分破坏。

**修复：** 先在独立临时状态中完成项目读取和最低限度校验；成功后再一次性替换当前 ProjectSession。失败时必须保持原编辑状态不变。

---

### **[MEDIUM]** `app/main_window.py:423-437,476-484`

**问题：** 首页录制会预创建项目并最小化窗口，但 `stop_recording()` 异常时直接返回，不执行成功路径中的 `showNormal()`、`raise_()` 和项目收尾。屏幕采集异步失败后，窗口可能继续最小化，空项目残留，用户只能通过托盘手动恢复。

**修复：** 停止失败也必须进入统一终止状态：恢复窗口和按钮、提示错误，并清理或明确标记失败项目。

## 4. 架构评估

### 优点

- `core/` 与 Qt UI 大体分离，Compositor、Camera、ProjectManager 可独立测试。
- Effect 注册机制简单、扩展点清晰。
- 录制帧改为磁盘压缩存储，避免旧版固定帧数上限，方向正确。
- 首页与编辑器页面切换已统一到 `_switch_to_home()` / `_switch_to_editor()`。

### 主要结构风险

`MainWindow` 当前 1246 行，承担：

- 页面导航和菜单状态；
- 录制生命周期；
- 项目创建、加载、保存；
- 播放控制；
- 时间线同步；
- 裁剪与音频编辑；
- 导出线程管理。

同时直接访问以下私有实现：

```text
_recorder.screen._store._offsets
_compositor._frames / _cursor_events / _click_events / _clips
_timeline._tracks
_playback._playing / _current_frame
```

这不是单纯“文件太长”，而是状态所有权不明确。当前已出现同一录制动作存在多套启动路径、项目路径同时被当作目录和文件、运行时音频与持久化音频脱节、时间线时间与源媒体时间混用等实际缺陷。

### 建议的最小拆分顺序

1. **先修正确性，不先大重构：** 修复打开、导出、音频持久化和异常终止协议，并补充流程测试。
2. **提取 ProjectSession：** 统一“当前项目目录、Project 模型、frames/audio 路径”的加载与保存契约。
3. **提取 RecordingController：** 统一开始/停止/失败恢复状态机，MainWindow 只响应结果。
4. **提取 ExportController：** 管理 QThread、进度、取消和完成；ExportWorker 保证单一终止信号。
5. MainWindow 最终只保留 UI 组装、信号绑定和页面导航。

不建议一次性拆成大量抽象层；上述三个对象已经足以消除当前的状态分叉。

## 5. 核心交互流程审查

| 流程 | 状态 | 说明 |
|------|------|------|
| 启动 → 首页 | ✅ | 默认首页、工具栏隐藏 |
| 首页 → 录制 → 编辑器 | ⚠️ | 成功路径完整；启动失败恢复缺失 |
| 首页录制 → 停止失败 | ❌ | 窗口不恢复，空项目可能残留 |
| 托盘 → 录制 → 保存 | ❌ | 未创建新项目会话，可能丢失录制或破坏旧项目 |
| 首页项目卡片 → 编辑器 | ✅ | 目录路径契约正确，页面切换统一 |
| 首页“打开项目” → 编辑器 | ❌ | 文件路径与目录契约冲突 |
| 打开损坏项目 | ❌ | 报错前已清空当前编辑状态 |
| 编辑器 → 保存 | ⚠️ | 主路径可用，但非原子写入；原始音频未保存 |
| 已打开项目 → 播放 | ⚠️ | 视频可恢复；原始音频不可恢复 |
| 当前录制 → 导出 | ⚠️ | 正常条件可工作；worker 异常可能挂起 UI |
| 已打开项目 → 导出 | ❌ | `_recorded_data is None` 导致崩溃 |
| 不同 FPS 项目 → MP4 导出 | ❌ | 项目 FPS 与全局 FPS 混用，时长和音画同步错误 |
| 移动/裁剪/变速音频 → 导出 | ❌ | 时间线区间被错误用于裁剪源文件 |
| GIF 长视频导出 | ⚠️ | stderr PIPE 存在阻塞风险 |
| 取消导出 | ⚠️ | 进程与临时文件清理不完整 |

## 6. Low 建议

### **[LOW]** `main.py:9-228`

大型 QSS 内联，影响 UI 代码可读性。可在功能稳定后移至 `resources/style.qss`。

### **[LOW]** 分散的 `print(..., file=sys.stderr)`

统一为 `logging`，但不应为了日志重构阻塞核心流程修复。

### **[LOW]** `core/frame_style.py:13`、`core/project.py:112`

`FrameStyle.bg_color` 类型声明为 tuple，迁移注释却宣称新版为 str。Pillow 两者都可接受，但数据契约和测试应统一。

## 7. 修复优先级

1. 恢复测试基线全绿。
2. 修复“打开项目 → 导出”崩溃和“打开项目”按钮路径契约。
3. 统一所有录制入口的 ProjectSession 创建，防止录制丢失和旧项目污染。
4. 持久化原始混音音频，并修正时间线时间与源音频时间映射。
5. 统一项目、Compositor 和 FFmpeg 的 FPS 时间基准。
6. 统一录制启动、停止和错误恢复。
7. 保证 ExportWorker 所有路径发出一次 finished，修复 GIF stderr drain。
8. 替换 `mktemp`，统一进程和临时文件清理。
9. 再按 ProjectSession → RecordingController → ExportController 顺序拆分 MainWindow。

## 8. 最低回归测试集

- 首页录制启动失败：恢复窗口、状态和按钮，提示用户，清理占位项目。
- 屏幕采集在停止时报告失败：恢复窗口和状态，处理失败项目目录。
- 托盘录制总是创建新项目；已有项目打开时开始托盘录制不会修改旧项目。
- 文件选择器选择 `project.json` 后能正确打开项目。
- 打开损坏项目失败后，当前编辑状态保持不变。
- 项目卡片打开后导出不访问空 `_recorded_data`。
- 录制含麦克风/系统音频，保存并重启后导出仍有音轨。
- 项目 FPS 与当前应用配置不同时，MP4 时长和音画同步保持正确。
- 额外音频移动、头尾裁剪和视频变速后，导出使用正确的源区间与时间线延迟。
- FFmpeg 启动失败时 worker 发出失败结果，线程退出，进度框关闭。
- GIF 大量 stderr 输出时导出不死锁。
- 导出取消后无遗留 FFmpeg 进程和临时 WAV。
- 至少两个历史版本的 project.json 可加载并迁移。

## 9. 最终判定

- [ ] 通过
- [ ] 有条件通过
- [x] **不通过：存在 High 问题且测试基线失败**

在第 2 节问题修复并使全量测试恢复为 0 failed 前，不应合并或发布。
