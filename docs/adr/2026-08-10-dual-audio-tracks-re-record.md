# ADR：双音频轨道编辑与麦克风补录

**日期：** 2026-08-10
**状态：** Accepted
**关联：** Flow #125 / `docs/dev/specs/recordly-dual-audio-tracks-and-re-record.md` / `docs/prd/recordly-dual-audio-tracks-and-re-record.md`

---

## 决策 1：轨道模型 — 新增 `audio_system` 轨道类型，数据模型零 schema 变更

### 背景

时间线现有 `audio`（内置，编辑不生效）与 `audio_extra`（外部音频，编辑生效）两种音频轨。需求要求双内置轨（mic + system）独立展示与编辑。

### 方案

- `Track.type` 新增数据值 `"audio_system"`（系统音频轨）；`audio` 轨语义明确为麦克风轨。
- 内置轨 clip 复用现有 `Clip.source_path` 字段写入**绝对路径**（与 `audio_extra` 现状一致）；裁剪/删除/移动/音量复用现有命令与 `sync_audio_regions_from_clips`，**不加任何新字段、不升级 `Project.VERSION`、不加顶层键**。
- `_validate_schema` 不校验 timeline/audio_regions 元素 → 旧项目与新字段零冲突。

### 候选方案与否决理由

- **A：mic/system 共用 `type="audio"`，靠 `track.name` 区分** —— 同步逻辑依赖名称字符串，脆弱；且现有 `_can_drop_to_track` 允许 `audio↔audio_extra` 互拖，mic/system 同 type 后互相拖拽语义混乱。否决。
- **B：升级 VERSION + 加载时迁移 timeline 数据** —— 本轮所有能力都可落在现有字段上（type 是数据值不是 schema），无迁移必要。运行时补齐（ADR-4）更简单且幂等。否决。

### 后果

- 优点：零迁移成本、旧项目打开即兼容；编辑链路与 `audio_extra` 完全同构。
- 代价：`Track.type` 取值集合扩大，任何按类型枚举的 UI 逻辑（TRACK_COLORS、_can_drop_to_track）需同步补充。

---

## 决策 2：导出/预览音频统一 numpy 内存合成，删除 FFmpeg filtergraph 链路

### 背景

旧导出链路：混音 wav（`orig_wav`，mic+system 预混合）→ 按 video clips atrim/atempo/adelay → 与 `audio_extra` regions 一起 `amix`。双轨编辑后 `orig_wav`（已混合）无法表达"只编辑 mic 轨"。

### 方案

- 新增 `core/audio_mix.compose_audio(regions, samplerate, duration)`：纯 numpy 按 region 列表合成（切片 × 音量 → 定位 → 逐样本相加 → clamp），与 `mix_audio_results` 语义一致。
- 导出：`ExportWorker` 删除 `audio_data` 参数与 `_build_audio_filtergraph`，改为 `compose_audio(settings.audio_regions, ...)` → `_save_temp_wav` → FFmpeg 单输入。
- 预览：`AudioPreviewPlayer` 改为接收 regions 并复用同一 `compose_audio`，预览与导出语义严格一致（DRY）。

### 候选方案与否决理由

- **A：保留 `orig_wav` 基础层 + 编辑 delta 覆盖（`anegate` 减法链）** —— 完全保留"video 变速跟随音频"旧语义，但 filtergraph 复杂到每轨需 2 条链（原始 + 编辑后），且所有链最终仍经 `amix` 混合，受 normalize 归一化影响（见下），调试与测试成本极高。否决。
- **B：`amix` 多路直接混合** —— 内置轨变成 2 个独立输入后，`amix` 默认 normalize 使输出按输入数衰减（-6dB），与旧版本"无 extra 时 1 路无衰减"不等价；`normalize=0` 又要求 FFmpeg ≥ 6.0，项目不保证版本。否决。
- **C：numpy 合成（采纳）** —— 无版本依赖、合成语义与录音混合（`mix_audio_results`）一致、预览/导出复用同一实现、无编辑时逐样本等价。

### 行为变化（需用户确认）

- video 轨 speed 不再影响导出音频（旧：`orig_wav` 按 video clips atempo）。新语义：所有音频轨独立于 video 轨，与 `audio_extra` 旧行为一致。
- `audio_extra` 轨不再绘制波形（旧实现绘制的是混音波形，本身不准确）。

### 后果

- 优点：无编辑等价性可证明（逐样本）；消除 ffmpeg 版本相关的归一化不确定性；预览/导出单一实现。
- 代价：丢弃"video 变速跟随音频"的耦合行为；`_build_audio_filtergraph` 相关测试需重写。

---

## 决策 3：补录语义 — 原段 volume=0 保留 + 新 clip 覆盖，CompositeCommand 单步撤销

### 背景

需求：补录"原段落静音保留（不删除），新录音替换声音"；失败/取消零残留；可撤销。

### 方案

- 补录 = `CompositeCommand([ChangeVolumeCommand(原 clip → 0.0), AddClipCommand(新 clip)])`：
  - 原 clip **保留**，整段 volume=0（静音标记与撤销语义天然一致——`ChangeVolumeCommand` 已是可撤销命令）；
  - 新 clip 覆盖同一时间区间，`source_path` = 项目内 `re_record_<时间戳>.wav` 绝对路径；
  - 撤销一次 = 逆序撤销（删新 clip + 恢复音量），完整还原。
- 失败/取消零残留：对话框取消不写文件；写盘失败删除已写文件；录音 0 秒拒绝。
- 新 clip 不等长规则：`end = min(原 clip.end, start + 录音时长)`——录音长则截断，短则剩余静音（原 clip 已 volume=0）。

### 候选方案与否决理由

- **A：删除原 clip + 插入新 clip** —— "不删除"是需求硬约束；且删除会改变撤销语义（需要恢复整个 clip 数据，`DeleteClipCommand` 虽支持但不满足"原段落静音保留"）。否决。
- **B：拆分原 clip 为三段，仅中间段静音** —— 仅在被补录区间严格小于 clip 时才有区别；本轮入口为"整 clip 补录"（右键 clip），拆分逻辑无触发场景（YAGNI）。否决，统一"整段静音 + 覆盖"。

### 后果

- 优点：复用全部现有命令；单步撤销/重做；原 clip 数据零丢失；补录区间边界语义简单。
- 代价：补录 wav 文件在撤销后保留（作为项目资产，不回收——YAGNI）。

---

## 决策 4：项目兼容 — 运行时补齐，不升级 VERSION

### 背景

旧项目 v1.1.0：audio 轨 clip 无 `source_path`；无 `audio_system` 轨；`source.audio_mic/audio_system` 记录原始 wav（相对路径）。

### 方案

`_restore_timeline_and_playback` 加载后执行幂等补齐：

1. `audio` 轨 clip 缺失 `source_path` → 回退 `_resolve_media_path(project_dir, source.audio_mic)`；
2. `source.audio_system` 存在且无 `audio_system` 轨 → 追加全时长 system 轨 clip。

补齐结果随保存写回 project.json，二次打开幂等。

### 候选方案与否决理由

- **A：`Project.load` 时迁移并升级 VERSION** —— 数据模型无 schema 变化，升级 VERSION 会触发不必要的"格式不兼容"信号；迁移逻辑放在 load 会让纯数据层耦合路径解析（`_resolve_media_path` 在 app 层）。否决。
- **B：运行时补齐（采纳）** —— 保持 `Project` 纯数据层不动，视图层负责补齐；幂等、可测试、无版本分支。

### 后果

- 优点：零 schema 变更；旧项目打开即用；补齐逻辑可提取为纯函数单测。
- 代价：补齐逻辑在 app 层，`Project.load` 调用者（ProjectManager 等）不感知补齐（仅 MainWindow 路径需要）。

---

## 与既有 ADR 的关系

- `docs/adr/006-data-persistence-json.md`：本轮不新增持久化字段，遵循原子保存与 schema 校验约定。
- 无冲突决策；本 ADR 的决策 2 是对导出音频链路的整体替换，属范围扩大而非增量修改，特此记录。
