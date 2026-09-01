# 双音频轨道编辑与麦克风补录 — 技术方案

**日期：** 2026-08-10
**状态：** Draft
**关联：** Flow #125 / `docs/01-product/prd/recordly-dual-audio-tracks-and-re-record.md`

---

## 1. 目标、范围与结论

在现有 Python 3.11 + PyQt5 架构上增量实现双音频轨道编辑与麦克风补录：

1. **双轨展示**：时间线新增 `audio_system`（系统音频）轨，`audio` 轨语义明确为麦克风轨；两轨 clip 均带 `source_path`（绝对路径）与各自波形。
2. **编辑生效（预览 + 导出）**：内置轨的裁剪/删除/移动/音量编辑统一经 `AudioRegion` 表达，导出与预览的音频合成全部改为 **numpy 内存合成**（新增 `core/audio_mix.py`），替代现有「混音 wav + FFmpeg filtergraph」链路。无编辑时输出与旧版本等价。
3. **麦克风补录**：mic 轨 clip 右键 → 独立录音窗口 → wav 写入项目目录 → `CompositeCommand`（原 clip 音量置 0 + 插入新 clip）单步可撤销；失败/取消零残留。

### 1.1 关键设计结论

| 问题 | 结论 |
|---|---|
| 数据模型 | **零 schema 变更**：不升级 `Project.VERSION`、不加顶层键、不加 Clip/AudioRegion 字段。新增 `Track.type="audio_system"` 只是数据值。内置轨复用现有 `Clip.source_path` + `AudioRegion` + `sync_audio_regions_from_clips`。 |
| 编辑链路 | `_on_clips_changed` 把 `audio`/`audio_system`/`audio_extra` 三轨 clip 一并 sync 到 `_audio_regions`；导出与预览消费统一的 region 列表。 |
| 导出音频 | 删除 `_build_audio_filtergraph` 与 `orig_wav` 概念；`ExportWorker` 用 `compose_audio(regions, ...)` 合成内存音频 → `_save_temp_wav` → FFmpeg 单输入。规避 FFmpeg `amix` 的 normalize 归一化（多路 amix 使音量按输入数衰减，`normalize=0` 又依赖 FFmpeg ≥ 6.0）。 |
| 预览音频 | `AudioPreviewPlayer` 输入从「混音音频 + video clips」改为「regions 列表」，复用同一 `compose_audio`（DRY），预览与导出语义严格一致。 |
| 补录语义 | 原 clip 整段 `volume=0`（保留 clip，不删除）+ 新 clip 覆盖同一时间区间，`CompositeCommand` 包装为单步撤销。失败/取消不写文件、不插入 clip。 |
| 旧项目兼容 | 运行时补齐：`audio` 轨 clip 缺失 `source_path` 时回退 `source.audio_mic`；`source.audio_system` 存在但无 system 轨时自动补轨。补齐结果随保存持久化，幂等。 |

### 1.2 本轮不做

- 内置音频轨的速度编辑（`speed` 菜单仍仅对 video 轨显示；合成按 speed=1 直接切片）。
- mic ↔ system 轨跨轨拖拽（`_can_drop_to_track` 保持 `audio↔audio_extra`、`audio_system↔audio_extra` 互通，内置两轨之间禁止）。
- 补录撤销后的 wav 文件回收（文件作为项目资产保留）。
- 补录波形实时预览、降噪、增益。

---

## 2. 现状与根因（已核实）

| 环节 | 现状 | 问题 |
|---|---|---|
| 采集 | `core/recorder.py:107-113` 返回 `mic_audio`/`system_audio` 分离 + `audio`（混音） | 数据已分离 |
| 保存 | `app/main_window.py:812-825` 分写 `audio_mic.wav`/`audio_system.wav`，`SourceInfo` 记录 | 数据已分离 |
| 加载 | `_load_project_audio`（main_window.py:92-113）混音为单一 `AudioResult` | **合并点** |
| 时间线 | `_populate_timeline`（869-906）只建 video/audio/zoom 三轨；audio 轨 clip 无 `source_path` | 无 system 轨、无源路径 |
| 编辑同步 | `_on_clips_changed`（1209-1233）只 sync `audio_extra` 轨 | **内置轨编辑不生效根因** |
| 导出 | `_build_audio_filtergraph`（exporter.py:600-696）：`orig_wav`（混音，按 video clips atrim/atempo/adelay）+ extra regions → `amix` | 内置轨无 region；`amix` 多路有 normalize 衰减 |
| 预览 | `AudioPreviewPlayer._build_timeline_data`（preview_widget.py:353-382）混音 + video clips 重排 | 不支持 region/多轨 |
| 命令 | `SplitClipCommand`/`MoveClipCommand`/`ChangeVolumeCommand`/`DeleteClipCommand`/`AddClipCommand`/`CompositeCommand` 按 `(track_index, clip_index)` 操作，与轨道类型无关 | 直接复用 |
| 波形 | `TimelineWidget.set_waveform_provider`（callable() → (data, sr)）单一数据源 | 需按轨提供数据 |
| 路径安全 | `_resolve_media_path`（main_window.py:75-89） | 加载时解析相对路径 |

---

## 3. 数据模型变更（零 schema 变更）

### 3.1 轨道类型

`Track.type` 新增取值 **`"audio_system"`**（纯数据值，`_validate_schema` 不校验 timeline 内容，向后兼容）。

| type | 含义 | 数据来源 |
|---|---|---|
| `audio` | 麦克风轨（既有类型，语义明确为 mic） | `audio_mic.wav` + 补录 wav |
| `audio_system` | 系统音频轨（新增） | `audio_system.wav` |
| `audio_extra` | 用户添加的额外音频轨（现状不动） | 外部文件 |

### 3.2 内置轨 clip 的 source_path

- **写入绝对路径**（与 `audio_extra` 现状一致，`_collect_project_state` 原样持久化 timeline）：
  - `_populate_timeline`：mic clip `source_path = os.path.join(project_dir, "audio_mic.wav")`（文件存在才写，否则空串）；system clip 同理。
  - 旧项目加载（`_restore_timeline_and_playback`）：clip `source_path` 为空时回退 `_resolve_media_path(project_dir, source.audio_mic / source.audio_system)`。
- clip 语义：`start/end` = 时间轴区间；`source_start/source_end` = wav 内区间；拆分/移动/音量沿用现有命令与 sync 逻辑。

### 3.3 补录 wav

- 位置：`<project_dir>/re_record_<YYYYmmdd_HHMMSS>.wav`（项目目录内，随项目保存/删除生命周期）。
- clip 语义：`source_path` = 该 wav 绝对路径；`source_start=0`；`source_end` = 实际使用长度；`start` = 被补录 clip 的 `start`；`end` = `min(被补录 clip.end, start + 录音时长)`。
- 录制时长 > 区间：截断（`source_end` = 区间时长）；录制时长 < 区间：剩余区间静音（原 clip 已 volume=0，自然静音）。

### 3.4 `AudioRegion` 复用

`sync_audio_regions_from_clips(clips, regions)` **签名不变**，`_on_clips_changed` 传入三轨 clip 合并列表。region 无需新增 track 字段——合成只消费 `audio_path`，波形按轨从 timeline 读数据。

---

## 4. 编辑链路设计

### 4.1 同步扩展（`app/main_window.py::_on_clips_changed`）

```python
audio_clips = [
    c for t in self._timeline.tracks
    if t.type in ("audio", "audio_system", "audio_extra")
    for c in t.clips
]
self._audio_regions = sync_audio_regions_from_clips(audio_clips, self._audio_regions)
```

`sync_audio_regions_from_clips` 现有语义完整覆盖需求：

- `region.audio_path = clip.source_path or region.audio_path` → 内置轨 clip 有绝对路径即生效；
- `source_end` 计算含 speed（内置轨 speed 恒 1.0，`source_end = source_start + (end-start)`）；
- `region.volume = clip.volume` → 音量/静音编辑生效；
- clip 无 id 时自动补 uuid（`_populate_timeline` 创建的 clip 无 id，sync 会补齐）。

删除 clip → 无对应 region → 该区间无该轨声音（静音），**不改变总时长**（与 video 轨删除语义一致）。

### 4.2 无编辑等价性论证

无任何编辑时 regions = [mic 全时长 clip(0→duration, vol=1), system 全时长 clip(0→duration, vol=1)]。
`compose_audio` 输出 = mic wav 逐样本 + system wav 逐样本（clamp 到 ±1.0）= 旧版本保存的混音内容（`mix_audio_results` 语义一致）→ 与旧版本导出音频**逐样本等价**（数值差异仅在 int16 量化舍入，与旧链路相同）。

### 4.3 行为变化声明（需用户确认，见 §10）

- **video 轨 speed 不再影响音频**：旧链路 `orig_wav` 按 video clips atempo；新链路所有音频轨独立于 video 轨。`audio_extra` 轨旧行为（不跟随 video 变速）成为统一语义。
- **`audio_extra` 轨不再绘制波形**：旧实现用混音数据画 extra 波形（本身不准）；新实现 provider 按轨提供数据，extra 轨无对应源数据，不绘制。

---

## 5. 导出音频合成（新 Module：`core/audio_mix.py`）

### 5.1 Module / Interface

```python
def compose_audio(regions: list[AudioRegion], samplerate: int,
                  duration: float | None = None) -> np.ndarray | None:
    """按 AudioRegion 列表合成时间轴音频。

    - 每个 region：读取 audio_path（缺失文件跳过）→ 按 source_start/source_end
      切片 → × volume → 定位到 start_ms。
    - 采样率 ≠ samplerate 的 region 先用 np.interp 重采样（线性插值）。
    - 各 region 逐样本相加，clip 到 [-1.0, 1.0]；
      输出声道数 = max(2, 各输入声道数)。
    - duration 给定则输出长度 = round(duration*samplerate)（超出截断），
      否则 = max(region.end_ms)。无有效 region 返回 None。
    """
```

- 合成语义与 `mix_audio_results`（core/audio_capture.py:23-46）一致：加法混合 + clamp。
- speed=1 直接切片（np 切片），不做插值；补录/内置 wav 均为项目采样率，重采样仅覆盖外部 extra 文件（48k 等）。
- 纯 Python + numpy，无 Qt/FFmpeg 依赖，可独立单测。

### 5.2 `ExportWorker` 改造（`core/exporter.py`）

- `ExportSettings.extra_audio` **改名 `audio_regions`**（语义变为全部音频区域，含内置轨）；`audio_data` 构造参数删除，worker 内部从 `settings.audio_regions` 合成。
  - 同步改动：`main_window._build_export_settings`（传 `self._audio_regions`）、`ExportController` 传递链、相关测试。
- `_export_mp4` / `_export_gif` 中删除 `orig_wav` 与 `_build_audio_filtergraph` 调用，替换为：

```python
regions = [r for r in (s.audio_regions or []) if os.path.exists(r.audio_path)]
mixed = compose_audio(regions, s.samplerate, video_duration)
if mixed is not None:
    final_wav = self._save_temp_wav(mixed, s.samplerate)
    _temp_paths.append(final_wav)
```

- `video_duration = total / s.fps`（与旧 atrim 截断语义一致）。
- `_build_audio_filtergraph` 与 `_atempo_filter_text` 删除（无其他调用者；`_save_temp_wav` 保留）。

### 5.3 读 wav 能力

`read_wav(path) -> AudioResult | None` 新增到 `core/audio_capture.py`（`AudioResult` 定义处），内容从 `main_window._read_wav`（main_window.py:60-72）提升并复用；`main_window._read_wav` 改为调用它（或直接删除、统一走 core 函数）。

---

## 6. 预览音频合成（`ui/preview_widget.py`）

### 6.1 `AudioPreviewPlayer` 改造

```python
class AudioPreviewPlayer:
    def __init__(self, audio_regions: list, samplerate: int,
                 duration: float | None = None, stream_factory=None):
        # timeline_data = compose_audio(audio_regions, samplerate, duration)
```

- 删除 `_build_timeline_data` 内部实现（复用 `core/audio_mix.compose_audio`，DRY）。
- `PlaybackController` 不变：`main_window._create_playback_controller` 改为构造 `AudioPreviewPlayer(self._audio_regions, samplerate)`。
- 采样率来源：优先 `_load_project_audio` 返回的混合 `samplerate`，否则 `DEFAULT_SAMPLE_RATE`（app/constants.py）。

### 6.2 波形 provider 按轨化（`ui/timeline.py` + `app/main_window.py`）

- `set_waveform_provider(provider)` 契约改为 `provider(track_type: str) -> (np.ndarray, samplerate) | None`。
- `_draw_audio_waveform`（timeline.py:1082）按 `self._tracks[ti].type` 调用 provider；`audio_extra` 无数据不绘制。
- main_window 注册 provider：遍历 timeline 找 `audio`/`audio_system` 轨，取首个 clip 的 `source_path` 读 wav（结果缓存 dict）：

```python
def _track_audio_provider(self, track_type):
    for t in self._timeline.tracks:
        if t.type == track_type and t.clips and t.clips[0].source_path:
            data = self._track_audio_cache.get(t.clips[0].source_path)
            if data is None:
                data = read_wav(t.clips[0].source_path)
                self._track_audio_cache[t.clips[0].source_path] = data
            return (data[0], data[1]) if data else None
    return None
```

- 缓存随 `_clear_editor_state` / `_populate_timeline` 失效。

---

## 7. 麦克风补录流程

### 7.1 录音窗口（新 Module：`ui/record_audio_dialog.py`）

```python
class RecordAudioDialog(QDialog):
    """独立补录窗口。开始/结束按钮 + 计时显示 + 取消。"""
    def __init__(self, parent=None, mic_factory=MicrophoneCapture):
        # mic_factory() → MicrophoneCapture（可注入 fake，便于测试）
        # 开始 → capture.start() + QTimer 计时（1s 刷新）
        # 结束 → capture.stop() → self._audio_result = AudioResult；accept()
        # 关闭/取消 → 未结束时 stop() 并丢弃数据；无结果时 reject()
    @property
    def audio_result(self) -> AudioResult | None: ...
```

- 复用 `core/audio_capture.MicrophoneCapture`（sounddevice 回调线程，UI 不阻塞）。
- 录音时长 ≤ 0 → 提示并 reject（不产生文件）。

### 7.2 入口（`ui/timeline.py`）

- 右键菜单：`clip.type == "audio"` 时追加「补录音频」项 → 新信号 `re_record_requested(track_index, clip_index)`。
- `TRACK_COLORS` 增加 `"audio_system": QColor(...)`（建议 `#2FA38C` 一类，区别于 mic 的 `#50C878`）。
- `_can_drop_to_track`：`audio_system ↔ audio_extra` 互通；`audio ↔ audio_system` 禁止（返回 False）。

### 7.3 补录执行（`app/main_window.py::_on_re_record_requested`）

```python
def _on_re_record_requested(self, track_index, clip_index):
    # 前置：self._project_dir 为空 → 提示拒绝
    # 1) dialog = RecordAudioDialog(self); if exec_() != Accepted: return
    # 2) wav_path = os.path.join(self._project_dir, f"re_record_{timestamp}.wav")
    #    _write_wav(wav_path, result.data, result.samplerate)
    #    写入失败 → 清理残留文件 + 通知 + return（零残留）
    # 3) 构造命令：
    #    target = self._timeline.tracks[track_index].clips[clip_index]
    #    clip_end = min(target.end, target.start + 录音时长)
    #    new_clip = Clip(type="audio", start=target.start, end=clip_end,
    #                    source_start=0, source_end=clip_end - target.start,
    #                    source_path=wav_path, volume=1.0, content="补录音频")
    #    insert_at = 按 start 升序的插入位置（bisect）
    #    cmd = CompositeCommand([
    #        ChangeVolumeCommand(track_index, clip_index, target.volume, 0.0),
    #        AddClipCommand(track_index, asdict(new_clip), clip_index=insert_at),
    #    ])
    #    self._timeline._push_undo(cmd)  # 或新增 timeline.push_command() 公共方法
```

- 撤销：`CompositeCommand.undo` 逆序 → 删新 clip → 恢复原 clip 音量，**一次撤销完整还原**（AC-6）。
- 重做：正序重放（AC-6）。
- `_on_clips_changed` 随后触发 → regions 更新 → 预览/导出生效（AC-4）。
- **失败/取消零残留**（AC-5）：对话框取消不写文件；写盘失败删除已写文件；录音 0 秒不产生 clip。
- 补录仅允许在已打开项目时执行。

### 7.4 补录后保存/加载

`_collect_project_state` 保存 timeline（含补录 clip 的绝对路径）与 `_audio_regions` → 重新打开时 `_restore_timeline_and_playback` 原样恢复（AC-4 闭环）。补录 wav 随项目目录保存。

---

## 8. 旧项目兼容与迁移

### 8.1 运行时补齐（`_restore_timeline_and_playback` 内，幂等）

```python
# 1) audio 轨 clip 回退源路径（旧项目 clip 无 source_path）
for track in project.timeline:
    if track.type == "audio" and track.clips and not track.clips[0].source_path:
        if project.source and project.source.audio_mic:
            track.clips[0].source_path = _resolve_media_path(
                project_dir, project.source.audio_mic)
# 2) 缺失 audio_system 轨自动补齐
if project.source and project.source.audio_system:
    if not any(t.type == "audio_system" for t in project.timeline):
        sys_path = _resolve_media_path(project_dir, project.source.audio_system)
        project.timeline.append(Track(type="audio_system", name="系统音频", clips=[
            Clip(type="audio_system", start=0.0, end=project.duration,
                 source_start=0.0, source_path=sys_path, content="系统音频"),
        ]))
```

补齐结果随 `_collect_project_state` 保存回 project.json → 二次打开幂等。

### 8.2 兼容性/迁移矩阵

| 场景 | audio 轨 | audio_system 轨 | 补录 clip | 说明 |
|---|---|---|---|---|
| 新录制（mic+system） | clip 带绝对 source_path | clip 带绝对 source_path | — | `_populate_timeline` 建两轨 |
| 新录制（仅 mic） | 有，source_path 指向 audio_mic.wav | 有，source_path 为空串 | — | 空 source_path → 无 region → 导出无 system 声音 |
| 新录制（仅 system） | 有，source_path 为空 | 有，指向 audio_system.wav | — | 同上，反向 |
| 旧项目 v1.1.0（有双 wav） | 有，无 source_path → 运行时回退 source.audio_mic | 缺失 → 自动补齐 | — | 保存后幂等 |
| 旧项目 v1.1.0（仅 mic） | 有，回退 | 缺失，source.audio_system 为空 → 不补 | — | 符合预期 |
| 补录后保存/加载 | 含补录 clip（绝对路径） | 不变 | 完整恢复 | timeline 原样持久化 |
| 无 audio 轨的异常项目 | 无 | — | — | 不强制补 audio 轨（旧项目理论总有），仅补 system |

`_validate_schema` 不校验 timeline/audio_regions 元素字段 → 全部场景无加载错误（AC-7）。

---

## 9. Testing Decisions

测试惯例：pytest 纯 Python 单元测试；Qt 组件用 `qapp` fixture（`QT_QPA_PLATFORM=offscreen`）。所有 Seam 均为公共函数/构造器，fresh-context developer 可直接实现与验证。

### 9.1 音频合成（compose_audio）— 核心行为

- **无编辑等价性**
  - Test Seam: `core.audio_mix.compose_audio(regions, samplerate)`
  - Observable Result: 两个全时长 region（volume=1）的合成输出 == `mix_audio_results(两个 wav 内容)` 逐样本一致
  - Test Level: unit（新 `tests/test_audio_mix.py`；wav 用 `_save_temp_wav`/`_write_wav` 逻辑写临时文件）

- **删除 = 静音、音量、裁剪、移动**
  - Test Seam: 同上
  - Observable Result: 删除某 region → 该时间区间样本为 0；volume=0.5 → 样本减半；source 切片 → 只有窗口内样本；start_ms 后移 → 样本在对应位置，前段为 0
  - Test Level: unit（同一文件，参数化）

- **采样率不一致重采样**
  - Test Seam: `compose_audio`（region wav 采样率 ≠ samplerate）
  - Observable Result: 输出长度 == round(duration*samplerate)，且信号形状近似保留（正弦峰位置一致）
  - Test Level: unit

- **缺失文件跳过**
  - Test Seam: `compose_audio`（audio_path 不存在）
  - Observable Result: 该 region 无贡献，不抛异常；全部缺失返回 None
  - Test Level: unit

### 9.2 编辑生效（预览 + 导出）

- **导出使用合成音频**
  - Test Seam: `ExportWorker`（monkeypatch `compose_audio` 捕获调用参数 + 断言 `_save_temp_wav` 输出为合成结果）
  - Observable Result: `ExportSettings.audio_regions` 传入 `compose_audio`；`_save_temp_wav` 写入非空 wav；`_build_audio_filtergraph` 不再被调用（已删除）
  - Test Level: unit（`tests/test_exporter.py` 重写 filtergraph 相关用例；沿用 monkeypatch subprocess 捕获 cmd 的现有模式）

- **预览与导出同一语义**
  - Test Seam: `AudioPreviewPlayer(audio_regions, samplerate).timeline_data`
  - Observable Result: 相同 regions 下，`timeline_data` == `compose_audio(...)` 输出；编辑后（删/移/音量）timeline_data 相应变化
  - Test Level: unit（`tests/test_preview_widget.py`，现有 `_build_timeline_data` 用例重写）

### 9.3 sync 扩展

- **三轨 clip → regions**
  - Test Seam: `sync_audio_regions_from_clips(clips, regions)`（core/project.py，签名不变）
  - Observable Result: 传入 audio + audio_system + audio_extra 混合 clip 列表，返回 regions 各字段（start_ms/end_ms/source_start_ms/source_end_ms/audio_path/volume）正确；重复调用幂等（id 稳定）
  - Test Level: unit（`tests/test_project.py` `TestAudioRegionSync` 扩展）

### 9.4 双轨展示与补齐

- **populate 双轨**
  - Test Seam: `MainWindow._populate_timeline`（fake `_recorded_data` + fake compositor）
  - Observable Result: timeline 含 `audio` 与 `audio_system` 轨；mic clip 的 source_path == `<project_dir>/audio_mic.wav`；无 mic 音频时 source_path 为空串
  - Test Level: qt unit（`tests/test_main_window.py`）

- **旧项目补齐（纯函数提取）**
  - Test Seam: 提取 `ensure_builtin_audio_tracks(project, project_dir) -> None`（main_window 或 project.py 的公共函数）
  - Observable Result: 旧项目（clip 无 source_path、无 system 轨）调用后 audio clip 有回退路径、system 轨补齐；已补齐项目调用无变化（幂等）；`source.audio_system` 为空不补
  - Test Level: unit（不依赖 Qt 的纯函数测试）

- **波形按轨**
  - Test Seam: `TimelineWidget.set_waveform_provider(provider)` + provider(track_type) 契约
  - Observable Result: 注册的 provider 被按 track.type 调用；audio 轨收到 mic 数据、audio_system 轨收到 system 数据；audio_extra 无波形绘制（provider 返回 None 时不画）
  - Test Level: qt unit（`tests/test_timeline.py` / `test_main_window.py`）

### 9.5 补录

- **命令组合与撤销**
  - Test Seam: `TimelineWidget` 上执行补录命令（或直接构造 `CompositeCommand([ChangeVolumeCommand, AddClipCommand])` 在 timeline 上执行/撤销/重做）
  - Observable Result: 执行后原 clip volume=0、新 clip 存在（start/source_path/音量正确）；`undo()` 一次后原 clip 音量恢复、新 clip 消失；`redo()` 恢复
  - Test Level: unit（`tests/test_commands.py` 扩展 + `tests/test_timeline.py`）

- **录音窗口交互**
  - Test Seam: `RecordAudioDialog(mic_factory=FakeCapture)`（qapp fixture）
  - Observable Result: 点开始→结束 → `audio_result` 为 FakeCapture 返回的 AudioResult；直接关闭 → `audio_result` 为 None 且 FakeCapture 被 stop（丢弃）；0 秒数据 → reject
  - Test Level: qt unit（新 `tests/test_record_audio_dialog.py`）

- **补录端到端（失败/取消零残留）**
  - Test Seam: `MainWindow._on_re_record_requested`（monkeypatch `RecordAudioDialog` 返回 Accepted/Rejected + FakeCapture；monkeypatch `_write_wav` 抛 IO 错误）
  - Observable Result: Accepted → timeline 出现新 clip、项目目录出现 wav；Rejected → timeline 不变、无文件；写盘失败 → 无新 clip、残留文件被清理（monkeypatch `os.remove` 断言）
  - Test Level: qt unit（`tests/test_main_window.py`）

### 9.6 回归

- **全量基线**：既有 554 tests 全绿（涉及改动文件：test_exporter / test_preview_widget / test_project / test_main_window / test_timeline / test_commands）
- **无编辑导出音频回归**：既有 `test_audio_mix_trims_sources_and_preserves_timeline` 等 filtergraph 用例删除/重写为 compose_audio 语义

---

## 10. 开放问题（已确认，2026-08-10）

1. **video 轨 speed 与音频解耦**（§4.3）：**已确认解耦**。旧行为"video 变速 → 导出音频跟随变速"取消，所有音频轨（含内置轨）独立于 video 轨编辑。
2. **`audio_extra` 轨波形消失**：**已确认不绘制**。旧实现绘制的是混音波形（本身不准确）；audio_extra 轨仅显示色块+名称。
3. **`ExportSettings.extra_audio` 改名 `audio_regions`**：**已确认改名**。字段语义变为全部音频区域，ExportController/测试联动改名。
4. **补录 clip 与目标区间不等长**：**已确认"截断/静音补齐"规则**（§3.3），不引入 time-stretch。

## 11. 假设

- FFmpeg 版本不保证 ≥ 6.0 → 不引入 `amix normalize=0`（numpy 合成规避）。
- 内置轨 clip `speed` 恒为 1.0（UI 不提供音频轨速度菜单，现状如此）。
- 补录 wav 采样率 = MicrophoneCapture 默认（与录制一致），无需重采样；extra 外部文件可能不同（重采样已覆盖）。
- 项目目录内媒体文件命名唯一（时间戳到秒，同一秒多次补录追加不同时间戳字段可扩展，默认时间戳冲突概率可忽略）。

