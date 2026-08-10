---
issue: 128
test_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/test_exporter.py tests/test_export_controller.py
verify_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/
---

# export-composed-audio

## Builds

导出视频的音频由 `compose_audio(settings.audio_regions, samplerate, video_duration)` 内存合成 → `_save_temp_wav` → FFmpeg 单输入，替代旧「混音 wav + `_build_audio_filtergraph` + `amix`」链路（消除 `amix` normalize 归一化衰减，无 FFmpeg ≥ 6.0 依赖）。`ExportSettings.extra_audio` 更名 `audio_regions`（语义变为全部音频区域，含内置轨）；`ExportWorker` 删除 `audio_data` 构造参数；`_build_audio_filtergraph`/`_atempo_filter_text`/`orig_wav` 概念删除。

## Acceptance Criteria

- [ ] monkeypatch `compose_audio` 捕获调用：`ExportSettings.audio_regions`（过滤 audio_path 不存在的项后）被传入 `compose_audio`，且携带 `samplerate` 与 `video_duration`（= total / fps）
- [ ] `_save_temp_wav` 写入非空 wav，输出为 `compose_audio` 的合成结果
- [ ] `_build_audio_filtergraph` 与 `_atempo_filter_text` 已删除且无调用者；`_export_mp4_cpu` / `_export_mp4_nvenc` / `_export_gif` 三条导出路径均不再出现 `orig_wav`
- [ ] `ExportWorker.__init__` 不再接收 `audio_data`；`ExportController.start_export`（app/export_controller.py）与 main_window 导出链（`_build_export_settings` → `_start_export_progress`）联动，`extra_audio` → `audio_regions`、传 `self._audio_regions`
- [ ] 回归：test_exporter 既有 filtergraph 音频用例（`test_audio_mix_trims_sources_and_preserves_timeline` 等 4 个）重写为 compose_audio 语义；全量既有测试绿

## Blocked By

- compose-audio-regions

## Implementation Notes

- 替换位置：`_export_mp4_cpu`（exporter.py:274）、`_export_mp4_nvenc`（exporter.py:399）、`_export_gif`（exporter.py:531）三处都含 `orig_wav` + `_build_audio_filtergraph` 逻辑，全部替换为 compose_audio 合成（方案 §5.2 的 `_export_mp4` 统称覆盖 cpu/nvenc 两个分支）。
- `video_duration = total / s.fps`（与旧 atrim 截断语义一致，方案 §5.2）；`_save_temp_wav`（exporter.py:732）保留不动。
- `_build_export_settings`（main_window.py:1341）`extra_audio=self._audio_regions` → `audio_regions=self._audio_regions`；`ExportWorker` 构造点（main_window.py:1357 / export_controller.py:30）同步去掉 `audio_data` 实参。
- 测试沿用现有 monkeypatch subprocess 捕获 cmd 的模式（方案 §9.2）。
- 本 Task 只交付「导出使用合成音频」链路；内置轨编辑进入 regions 由 sync-builtin-tracks（T3）负责，两者合入后导出编辑才完整生效。
