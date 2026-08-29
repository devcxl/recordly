# Issue #141 代码审查逐项核对报告

> **核对对象**: [issue #141 — AI 深度代码审查日报 2026-08-16](https://github.com/devcxl/recordly/issues/141)
> **核对基线**: `master @ 231d9ee`（v1.3.0-2-g231d9ee，2026-08-28）
> **核对方法**: 逐点阅读当前代码（文件:行号为证），结合 git 历史判断修复情况
> **核对日期**: 2026-08-28

---

## 总体结论

| 状态 | 数量 | 条目 |
|------|------|------|
| ✅ 已修复 | 4 | 发现 #1、#2、#3、许可证一致性（技术债项） |
| 🟡 部分修复 | 2 | 发现 #10；私有成员访问收敛（技术债项） |
| ❌ 未修复 | 8 | 发现 #4、#5、#6、#7、#8、#9；main_window 行数（A5）、半成品路径（A5） |

修复率约 **27%**（4/15 完全修复，2/15 部分修复）。审查 12 天间项目经历了 v1.2.x 打包重建与 v1.3.0 音量功能，但**运行时/安全类问题基本未动**。

> 2026-08-29 更新：**发现 #2（录制停止竞态）已修复**（commit `a657c89`）——锁保护 + 快照读取 + 可中断循环 + clear 守卫，含 4 个回归测试。
> 2026-08-29 更新：**发现 #3（损坏项目崩溃）已修复**（commit `7426f48`）——`_validate_schema` 深度类型/范围校验（加载即拒绝非法字段，带字段路径错误信息）+ `_on_open_project` restore 步骤整体 try/except 回退干净状态，含 12 个回归测试。

---

## 一、架构评估逐项核对

### A1. 定位分层与工程规范 — ✅ 正面依旧成立
- 分层结构（app/core/ui）未变；测试规模从 288 → **655 个**，文档体系完整。
- 原子写、目录边界守卫、realpath 越界校验、无 shell 调用等正面项复查仍成立。

### A2. 录制管线线程模型 — ❌ 未修复
原始风险：`ScreenCapture.stop()` 只 `join(timeout=5)`，mss.grab 阻塞时主线程仍读取/清理采集线程数据。

| 核验点 | 现状 |
|--------|------|
| `stop()` join 超时仍读数据 | `core/screen_capture.py:190-193` — `self._quit.set()` + `join(timeout=5)`，无"确认线程已退出"逻辑 ☑ 未变 |
| `all_frames` 迭代竞态 | `core/screen_capture.py:213-219` — `zip(self._timestamps, self._indices)` 直接遍历**原列表**（`frame_meta` 是 copy，但 `all_frames` 不是）☑ 未变 |
| `frame_offsets` 一致性 | `core/screen_capture.py:221-224` 返回 `self._store._offsets` **原引用**；`app/main_window.py:872` 直接读 ☑ 未变 |
| `clear()` 线程已死断言 | `core/screen_capture.py:231-240` — 无断言 ☑ 未变 |

### A3. 导出管线 — 🟡 部分修复
- **注入面（严重项）已消除**：`_build_audio_filtergraph` 已删除，音频全部改为 `core/audio_mix.py` 的 `compose_audio()` 在 Python 内存合成 → 写临时 WAV → ffmpeg 仅 `-i final_wav`。GIF 滤镜图参数全为常量。**无用户数据进 filtergraph**（详见发现 #1）。
- **取消/断管 WAV 泄漏**：仍存在（见发现 #4）。
- **GPU 探测 UI 线程同步**：仍存在（见发现 #9）。

### A4. 资源与错误处理 — 🟡 部分修复
- 录制临时文件：仍 `NamedTemporaryFile(delete=False)` + `atexit.register`，崩溃残留依旧（见发现 #4）。
- `Project.load`：**新增了 `_validate_schema`**（未知键校验），但无递归类型/范围校验（见发现 #3）。
- `_on_open_project`：`open_project` 加载步骤已包 try/except（`app/main_window.py:1669-1673`），但 5 个 restore 步骤仍在 try 外。

### A5. 技术债 — 🟡 部分改善
| 核验点 | 现状 |
|--------|------|
| main_window.py 单类过大 | 1640 行 → **1895 行**（继续增大，未拆分）❌ |
| 跨模块私有成员访问 | issue 时多处 → 现残留 3 处：`app/main_window.py:872`（`screen.frame_offsets`）、`app/main_window.py:965`（注释）、`ui/preview_widget.py:426`（`compositor._frames`）🟡 大幅收敛 |
| 半成品路径 `ProjectManager.create_project` | 仍**无调用方**（UI 用 `ProjectSession.create`）❌ |
| 半成品路径 `Compositor.load_video` | 有调用方（`app/main_window.py:1736`，打开 mp4 项目时走）；含 BGR 缺陷（见发现 #7）❌ |
| 许可证一致性 | **已修复** ✅：LICENSE 文件存在（MIT）、README/pyproject/spec 全 MIT、setup.py 已删，无 AGPL 残留 |
| 首页缩略图永不显示 | 仍存在（见发现 #8）❌ |

---

## 二、发现逐项核对

### #1 [MEDIUM][安全] FFmpeg 滤镜图注入 — ✅ 已修复
**原问题**: `_build_audio_filtergraph` 把 project.json 数值 f-string 拼进 `-filter_complex`。

**现状**:
- `core/exporter.py` 中 `_build_audio_filtergraph` **已不存在**（git 历史：v1.2.x 音频重构时删除）。
- 音频混合完全由 `compose_audio()`（`core/audio_mix.py`）Python/numpy 完成，ffmpeg 只读合成后的临时 WAV（`exporter.py:259-269`），无 `atrim`/`volume=` 滤镜字符串。
- 残留的 `_apply_atempo`（`exporter.py:570-586`）已**无调用方**（死代码），不再构成注入面。
- GIF 滤镜（`_build_gif_output`，`exporter.py:446-466`）参数均为硬编码常量。

**遗留小点**: `core/audio_mix.py:73-74` `data * region.volume` 对 volume 无范围校验（畸形大值 → 最终 `np.clip(mixed, -1.0, 1.0)` 削波，降级为音频失真，不构成注入）。

### #2 [MEDIUM][架构] 录制停止竞态 — ✅ 已修复（2026-08-29, commit `a657c89`）
**原问题**: 采集线程 join 超时后主线程仍读取/清理其数据。

**修复**:
- `core/screen_capture.py`：新增 `_data_lock` 保护 `_timestamps`/`_indices`/`_latest_frame`；`all_frames`/`frame_meta`/`frame_offsets` 全部锁内返回**快照**；`_CompressedFrameStore.snapshot_offsets()` 锁内复制；`run()` 循环改用可中断的 `_quit.wait()` 且 grab 后检查退出信号；`stop()` 返回线程是否确认退出（join 超时不再静默）；`clear()` 前确认线程已死，仍存活则抛错拒绝清理
- `core/recorder.py`：`stop_recording` 对 join 超时记录 warning
- `tests/test_screen_capture.py`：+4 回归测试（并发写读快照一致性、可中断循环 + stop 确认、clear 守卫）

### #3 [LOW][安全] project.json 子结构无类型校验 — ✅ 已修复（2026-08-29, commit `7426f48`）
**原问题**: `Project.load` 对子结构 `**data` 展开无类型校验，打开损坏项目抛未处理异常。

**修复**:
- `core/project.py`：`_validate_schema` 扩展为深度类型/范围校验——`source`（字符串/数值/fps 1-240）、`timeline→clips`（start/end/source_start 数值、source_end 可空、speed 0.0001-8、volume 0-2、绘制字段 font_size/color/rect）、`cursor_events`/`click_events`（[x,y,ts] 三元组）、`audio_regions`（ms + volume 0-2）、`annotations`、`crop_region`（0-1 归一化）、`duration`/`monitor_offset` 等；非法字段加载时即抛 ValueError（含字段路径）
- `app/main_window.py`：`_on_open_project` 的 6 个 restore 步骤整体 try/except，失败回退 `_clear_editor_state()` + `_project_dir=None` + 错误通知，不进入编辑器
- `tests/test_data_persistence.py`：+10 参数化坏字段拒绝 + 合法边界值加载
- `tests/test_main_window.py`：+2 打开失败/恢复失败回退测试

### #4 [LOW][安全] 临时文件生命周期 — ❌ 未修复
**原问题**: 录屏临时文件仅 atexit 清理（崩溃残留）；导出取消/断管跳过 WAV 清理。

**现状**:
- 录制: `core/screen_capture.py:46-59` 仍 `tempfile.NamedTemporaryFile(prefix="recordly-", suffix=".frames", delete=False)` + `atexit.register(self.cleanup)`，未用 `TemporaryDirectory`，崩溃残留依旧。
- 导出: `core/exporter.py` 的 `_temp_paths` 删除循环（`_export_mp4_cpu` ~358 行、`_export_mp4_nvenc` ~437 行）位于正常完成路径；取消/断管时 `_stream_frames_parallel` 提前 return（`if not ...: return`），**跳过清理**。GIF 路径无音频临时文件，不受影响。

### #5 [LOW][安全] 项目名未消毒，目录穿越 — ❌ 未修复
**原问题**: `create_project`/`ProjectSession.create` 拼接 name 不校验。

**现状**:
- `core/project_manager.py:66`: `dest_dir = self._projects_dir / f"{timestamp}_{name}"` — 无消毒 ☑ 未变
- `app/project_session.py:58`: `os.path.join(projects_dir, f"{timestamp}_{name}")` — 无消毒 ☑ 未变
- 可达性: UI 侧 `_create_project_for_recording`（`app/main_window.py:697`）用自动生成名（`录制 2026-08-28 19:22`），**当前不可达**；但 API 层无防护，与 issue 结论一致。
- `delete_project` 的 resolve 守卫（`project_manager.py:112-116`）仍存在 ✅（可复用为修复模板）。

### #6 [LOW][架构] 指针事件监听线程竞态 — ❌ 未修复
**原问题**: `pointer.stop()` 后 listener 线程可能仍在写入，`stop_recording` 直接遍历 `_events` 改写时间戳。

**现状**（实测验证 pynput 行为）:
- pynput `AbstractListener.stop()` **不 join 线程**（仅置 `_running=False` + 队列投递 stop + `_stop_platform()`），在途回调仍可能 append。
- `core/recorder.py:104-105` 仍 `for e in self.pointer._events: e.timestamp = ...` — 直接遍历**私有列表**并原地改写 ☑ 未变
- `PointerTracker.stop()`（`pointer_tracker.py:54-57`）仅调 `listener.stop()`，无 join/快照方法。

### #7 [LOW][架构] load_video BGR/RGB 通道错乱 — ❌ 未修复
**原问题**: cv2 读到 BGR 原样存入，`Image.fromarray(mode="RGB")` 红蓝互换。

**现状**:
- `core/compositor.py:132-146`: `CapturedFrame(data=frame_bgr, ...)` **未做 `cv2.cvtColor`** ☑ 未变
- `core/compositor.py:460`: `Image.fromarray(frame.data, mode="RGB")` ☑ 未变
- 可达性扩大: `app/main_window.py:1736` `_restore_video_frames` 对非 `frames.data` 的 source.video（如 mp4）调用 `load_video` — 录制流程存 `video="frames.data"`（`main_window.py:864`）不受影响，但打开 mp4 来源项目会错色。

### #8 [LOW][架构] 首页缩略图 CWD 解析永不显示 — ❌ 未修复
**原问题**: `list_projects` 原样返回相对路径，`ProjectCard` 按 CWD `isfile` 解析。

**现状**:
- `core/project_manager.py:53-55, 62-65`: `thumbnail_path=data.get("thumbnail_path", "")` **不拼接项目目录** ☑ 未变
- `ui/project_card.py:104-107`: `thumb_path = self._summary.thumbnail_path; if thumb_path and os.path.isfile(thumb_path)` — 按 CWD 解析 ☑ 未变（且无路径越界校验）

### #9 [LOW][架构] is_gpu_available UI 线程同步阻塞 — ❌ 未修复
**原问题**: `ExportDialog.__init__` 同步 `subprocess.run(timeout=10)`。

**现状**:
- `core/exporter.py:25-41`: `is_gpu_available()` 仍同步 `subprocess.run(..., timeout=10)` + 全局缓存无失效。
- `ui/export_dialog.py:138-142`: 构造时同步 `self.gpu_check.setEnabled(is_gpu_available())` ☑ 未变 — ffmpeg 缺失/异常时对话框首次打开仍可能冻结 UI 最长 10s。

### #10 [LOW][架构] 调试日志 f-string 缺失 — 🟡 部分修复
**原问题**: 两处 debug 日志缺 f 前缀。

**现状**:
- `core/exporter.py:302`: `logger.debug("ffmpeg {' '.join(cmd)}")` — **仍无 f 前缀**，命令行永不输出 ❌
- "音频混合失败" 那行已随 `_build_audio_filtergraph` 重构**消失** ✅
- 新增 `logger.debug(f"帧数={total} 尺寸={w}x{h} fps={s.fps}")`（`exporter.py:303`）带 f ✅

---

## 三、未修复项汇总（按严重度）

| 优先级 | 条目 | 位置 | 建议 |
|--------|------|------|------|
| **中** | #8 首页缩略图永不显示 | `core/project_manager.py:32-60`、`ui/project_card.py:104-115` | list_projects 用项目目录拼接相对路径 + 越界绝对路径拒绝 |
| **中** | #5 公开 API 目录穿越 | `core/project_manager.py:66`、`app/project_session.py:58` | name 消毒（剔除路径分隔符/控制字符）+ resolve 后校验仍在 projects_dir 内（复用 delete_project 守卫） |
| **中** | #4 临时文件泄漏（崩溃残留 + 取消泄漏 WAV） | `core/screen_capture.py:46-59`、`core/exporter.py` 取消路径 | 录制用 TemporaryDirectory 或信号清理；`_temp_paths` 清理移入 try/finally |
| **中** | #9 GPU 探测 UI 阻塞最多 10s | `core/exporter.py:25-41`、`ui/export_dialog.py:138-142` | 探测移入后台线程/导出线程；缓存可失效 |
| **低** | #6 指针事件竞态 | `core/recorder.py:104-105`、`core/pointer_tracker.py:54-57` | PointerTracker.stop() 内 join + `normalize_timestamps()` 快照方法；消费 events 副本 |
| **低** | #7 BGR/RGB 错乱（潜伏） | `core/compositor.py:132-146, 460` | 存帧前 `cv2.cvtColor(BGR2RGB)` |
| **低** | #10 ffmpeg 命令行 debug 日志失效 | `core/exporter.py:302` | 补 `f` 前缀 |
| **低** | A5 main_window 1895 行单类 | `app/main_window.py` | 继续按控制器拆分 |
| **低** | A5 半成品路径 | `core/project_manager.py:62`、`core/compositor.py:125` | 接线或删除 |
| **低** | `_apply_atempo` 死代码 | `core/exporter.py:570-586` | 删除 |
| **低** | audio_mix volume 无范围校验 | `core/audio_mix.py:73-74` | `volume ∈ [0, 2]` clamp |

---

## 四、已修复确认（无需处理）

1. ✅ **#1 FFmpeg 滤镜图注入** — compose_audio 重构彻底消除（音频不进滤镜图）
2. ✅ **#2 录制停止竞态** — 2026-08-29 修复（commit `a657c89`）：锁保护 + 快照 + 可中断循环 + clear 守卫
3. ✅ **许可证一致性** — LICENSE(MIT) 存在，README/pyproject/spec 全 MIT，setup.py 已删
4. ✅ **#3 部分** — `_validate_schema` 未知键校验已上线（防旧版/误写字段，报错友好）
5. ✅ **#10 部分** — 已删失效日志行，新增带 f 前缀的行
6. 🟡 私有成员跨模块访问从多处收敛到 3 处

---

*附注: 本报告全部结论基于静态代码核对；#2/#6 竞态类问题在常规测试中不易复现，建议修复后再做压力验证。*