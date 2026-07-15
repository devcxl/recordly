## 审查报告

### 变更概述
- **PR**: #64 — fix: restore new recording roundtrip stability (closes #63)
- **目标**: 修复新录制项目保存、重开预览、音频恢复、GIF FPS、控件状态和路径安全
- **修改文件数**: 10（2 业务代码 + 1 helper 重构 + 4 测试 + 2 文档 + 1 CI 辅助）
- **新增测试文件**: `tests/test_recording_roundtrip.py`（548 行）
- **风险等级**: 低
- **测试结果**: 343 passed, 1 skipped（六矩阵 CI 全部通过）
- **审查依据**: Issue #63 + `docs/dev/recording-roundtrip-stability.md`

### 逐文件审查

---

#### `app/main_window.py`

**改动概要**:
1. `_read_wav` 返回签名改为 `(data, samplerate, channels)` tuple — 供 `_load_project_audio` 使用
2. 新增 `_resolve_media_path` — 路径越界防护（`..` 和外部绝对路径拒绝）
3. 新增 `_load_project_audio` — 从 `project.json` 声明的 WAV 恢复混合音频
4. `_finalize_project` 修复 `self.recording_controller` → `self._recording_controller`
5. `_collect_project_state` 光标时间戳转为相对于 `compositor._base_time`
6. `_on_open_project` 重构 — 路径安全校验 + 音频恢复 + 控件条件启用

**逐条分析**:

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `_read_wav` 返回签名变更 | ✅ | 所有调用方已适配（仅 `_load_project_audio` 使用），内部 helper |
| `_resolve_media_path` 路径越界 | ✅ | `realpath` + `commonpath` 双重检查；覆盖 `..` 逃逸、外部绝对路径、Windows 跨盘符 |
| `_resolve_media_path` TOCTOU | ⚠️ | realpath 后到文件读取间存在 symlink 竞态窗口 — 桌面应用场景可接受 |
| `_load_project_audio` source 空处理 | ✅ | `source` 为 None、`audio_mic`/`audio_system` 为空、WAV 不存在均有正确空返回 |
| `_load_project_audio` 异常传播 | ✅ | 调用方 `_on_open_project` 有 try/except，失败时通知但不阻断打开 |
| `_finalize_project` 属性修复 | ✅ | `self._recording_controller` 是正确私有属性名 |
| `_collect_project_state` 光标相对化 | ✅ | 两种格式 (`CursorEvent` 对象 + tuple) 均处理；`base_ts = comp._base_time` |
| 点击事件不相对化 | ✅ | 点击事件仍为绝对时间戳 — 由 `build_camera`（在 `_populate_timeline` 中调用）使用 base_time 处理 |
| `_on_open_project` 视频路径安全 | ✅ | 越界时通知用户并置空，无崩溃 |
| `_on_open_project` 音频恢复 | ✅ | 失败时 `mixed_audio = None`，继续无音频打开 |
| `_on_open_project` `_recorded_data` 构造 | ✅ | `has_content = bool(comp._frames) or mixed_audio is not None` — 有帧或有音频时构造 |
| `_on_open_project` 控件条件启用 | ✅ | `has_frames = len(comp._frames) > 0` 守卫播放/裁剪/导出 |

---

#### `core/exporter.py`

**改动概要**:
1. `_build_gif_output` 在 `split` 前插入 `fps` filter 降采样
2. 移除输出节点 `r=self._compositor.fps`（由 fps filter 接管帧率）

**分析**:

| 检查项 | 状态 | 说明 |
|--------|------|------|
| fps filter 位置 | ✅ | `split` 前应用 — 保证 palettegen/paletteuse 接收已降采样流，时长不变 |
| round=near | ✅ | 避免帧选择偏移导致时长偏差 |
| 输出节点移除 `-r` | ✅ | GIF 容器从流推断 FPS，帧延迟由降采样后的帧率决定 |
| `ExportResult.duration` 计算 | ✅ | `total / c.fps` 用于元数据报告，不影响实际输出 |

---

#### `app/project_session.py`

**改动**: `normalize_path` 使用 `Path.name` 精确匹配 + `os.path.normpath` 跨平台

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `endswith("project.json")` → `path.name == "project.json"` | ✅ | 防止 `/foo/project.json.bak` 误匹配 |
| `os.path.normpath` | ✅ | Windows 反斜杠 → 正斜杠统一 |

---

#### 测试文件

**`tests/test_recording_roundtrip.py`** (新增 548 行):
- `TestAutosaveCreatesRequiredArtifacts` — `frames.idx` + `project.json` 完整性
- `TestCursorTimebase` — 相对时间戳保存→重开后光标插值一致性
- `TestGifFps` — FFmpeg 图验证 `fps=fps=15` filter + 实际导出 30fps_1s→10fps_10帧_1s
- `TestControlState` — 无帧项目控件禁用 / 有帧启用
- `TestMediaPathResolution` — 5 个路径越界场景 + Windows 跨盘符 mock
- `TestAudioHelper` — WAV 加载/混合 + 加载失败通知
- `TestFullRoundtrip` — 保存→重开→帧恢复→音频恢复→可导出 贯穿测试
- `TestMp4AudioTrack` — ffprobe 验证 MP4 含 video+audio stream

**`tests/test_exporter.py`**: GIF 断言从 `-r 30` 更新为 `-r 30` + `fps=fps=15`

**`tests/test_frames_data.py`**: Windows CI 修复 — `del` + `gc.collect()` 释放文件句柄

**`tests/test_main_window.py`** / **`tests/test_project_session.py`**: 路径测试 `os.path.join` + `os.path.normpath` 跨平台

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 测试覆盖 | ✅ | 8 个测试类，覆盖保存/重开/音频/GIF/控件/路径安全/MP4 |
| 无旧项目恢复测试 | ✅ | 所有测试仅验证新创建项目，无迁移逻辑 |
| 跨平台 | ✅ | `os.path.samefile`、`os.path.normpath`、`gc.collect()`、Windows 盘符 mock |
| 实际执行 | ✅ | 343 passed, 1 skipped（GIF 实际导出需要 ffmpeg，部分 CI 矩阵 skip） |

---

### 发现问题

**无 Critical 或 High 问题。**

[MEDIUM] `_recorded_data` 键不一致：初始录制流 vs 重开流
- **文件**: `app/main_window.py:1273-1278` vs 初始录制流
- **问题**: 初始录制完成后 `_recorded_data` 包含 `mic_audio`/`system_audio` 键，但 `_create_playback_controller` 读取 `_recorded_data.get("audio")`。重开流正常（`_recorded_data["audio"]` 已混合），但初始录制流中播放控制器无音频。
- **影响**: 录制完成后首次播放无声音（重开后正常）。属于预存问题，不在本次修复范围。
- **修复建议**: 后续 PR 在初始录制流中补充 `_recorded_data["audio"]`，或让 `_create_playback_controller` 兼容两种键。

[MEDIUM] `_resolve_media_path` TOCTOU 竞态
- **文件**: `app/main_window.py:71-85`
- **问题**: `os.path.realpath()` 与后续文件读取间存在 symlink 竞态窗口。攻击者可在此期间替换 symlink 目标。
- **影响**: 桌面应用、用户自己的项目目录 — 风险极低，可接受。
- **修复建议**: 深度防御 — 在 `_read_wav` / `load_frames_data` 中再次校验 `os.path.realpath`（非阻断）。

[MEDIUM] `_collect_project_state` 注释与范围不完全一致
- **文件**: `app/main_window.py:753`
- **问题**: 注释声明"光标轨迹（保存为相对 compositor._base_time 的时间戳）"，但下方点击事件（line 763-768）未相对化。
- **影响**: 无功能影响（点击事件由相机合成器使用 `base_time` 处理），但注释可能误导维护者。
- **修复建议**: 注释改为"光标轨迹（保存为相对 compositor._base_time 的时间戳）；点击事件保留绝对时间戳由相机合成器处理"。

[LOW] `_read_wav` 返回签名变更无显式标注
- **文件**: `app/main_window.py:56-68`
- **问题**: 从 `ndarray | None` 改为 `tuple | None`，函数是模块级 helper，未标注为 internal。
- **影响**: 无（仅被 `_load_project_audio` 调用）。
- **修复建议**: 可忽略。

[LOW] `_resolve_media_path` 嵌套 try/except 风格
- **文件**: `app/main_window.py:78-84`
- **问题**: 嵌套 try/except 用于区分 `os.path.commonpath` 原生 ValueError 和自定义 raise — 功能正确但略绕。
- **修复建议**: 可提取为两个独立 try 块，但非必须。

---

### 测试建议

| 测试场景 | 覆盖状态 | 建议 |
|----------|---------|------|
| 录制→保存→重开→光标插值 | ✅ `TestCursorTimebase` | — |
| 录制→保存→重开→音频恢复 | ✅ `TestFullRoundtrip` | — |
| MP4 包含 video + audio stream | ✅ `TestMp4AudioTrack` | — |
| GIF fps filter 降采样 | ✅ `TestGifFps` | — |
| 路径遍历防护 | ✅ `TestMediaPathResolution` (5 场景) | — |
| 无帧项目控件禁用 | ✅ `TestControlState` | — |
| 音频加载失败不阻断打开 | ✅ `TestAudioHelper` | — |
| Windows 跨盘符 `commonpath` | ✅ mock 覆盖 | — |
| 旧项目不触发恢复逻辑 | ✅ 无相关逻辑 | — |
| 录制完成后立即播放含音频 | ❌ 未覆盖 | 后续 PR 补充（MEDIUM 问题关联） |
| `_on_save_project` 保持光标相对时间 | ❌ 未覆盖 | 可补充 `test_save_preserves_relative_cursor` |

---

### Issue #63 验收标准对照

| 标准 | 实施 | 测试 |
|------|------|------|
| 录制完成生成有效 `frames.idx` 和完整 `project.json` | ✅ `_finalize_project` 使用 `_recording_controller` | ✅ `test_finalize_project_creates_frames_idx_and_project_json` |
| 新项目重开恢复麦克风和系统音频 | ✅ `_load_project_audio` + `mix_audio_results` | ✅ `TestFullRoundtrip` + `TestAudioHelper` |
| 光标事件与帧使用同一相对时间基 | ✅ `_collect_project_state` base_ts | ✅ `TestCursorTimebase` |
| GIF 使用用户选择 FPS 并保持时长 | ✅ `fps` filter before `split` | ✅ `TestGifFps` (实际 ffmpeg + 图验证) |
| 无帧项目不启用播放/导出 | ✅ `has_frames` 守卫 | ✅ `TestControlState` |
| 不恢复现有损坏项目 | ✅ 无迁移/猜测逻辑 | ✅ 无相关代码 |
| 全量测试通过 | ✅ | ✅ 343 passed, 1 skipped |

---

### 审查结论

- [x] **通过 — 无 Critical/High 问题**

所有改动严格限定在方案范围：
- ✅ 仅修复新录制项目链路，无旧项目恢复/迁移
- ✅ 保存/重开音频与光标路径完整
- ✅ MP4 含真实 video/audio stream（ffprobe 验证）
- ✅ GIF FPS 降采样保持时长
- ✅ 路径安全（5 种越界场景覆盖，含 Windows 跨盘符）
- ✅ 跨平台 CI 修复（`normpath`/`samefile`/`gc.collect`）
- ✅ 测试覆盖 8 个测试类、343 全部通过

3 个 MEDIUM 问题均为预存问题或注释级别，不阻塞合并。
