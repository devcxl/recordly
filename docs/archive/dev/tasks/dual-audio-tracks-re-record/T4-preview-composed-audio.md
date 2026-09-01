---
issue: 130
test_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/test_preview_widget.py tests/test_main_window.py
verify_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/
---

# preview-composed-audio

## Builds

预览音频与导出严格同一语义（DRY）：`AudioPreviewPlayer` 输入从「混音音频 + video clips」改为 regions 列表，内部复用 `core.audio_mix.compose_audio`（`_build_timeline_data` 删除）；`main_window._create_playback_controller` 以 `self._audio_regions` 构造播放器。编辑（删/移/音量）后 `timeline_data` 相应变化，预览能听到编辑结果。

## Acceptance Criteria

- [ ] 相同 regions 下 `AudioPreviewPlayer(audio_regions, samplerate).timeline_data` == `compose_audio(audio_regions, samplerate)` 输出（逐样本）
- [ ] 编辑后（删除/移动/音量 0.5）timeline_data 相应变化（与 compose_audio 语义一致）
- [ ] `_create_playback_controller`（main_window.py:1023）以 `self._audio_regions` 构造 `AudioPreviewPlayer`，采样率优先取 `_load_project_audio` 返回的混合 samplerate，否则 `DEFAULT_SAMPLE_RATE`
- [ ] 回归：test_preview_widget.py 既有 `_build_timeline_data` 用例重写；全量既有测试绿

## Blocked By

- compose-audio-regions

## Implementation Notes

- `AudioPreviewPlayer.__init__` 改为 `(audio_regions, samplerate, duration=None, stream_factory=None)`（preview_widget.py:316 改造），`_build_timeline_data` 内部实现删除，替换为 `compose_audio`（方案 §6.1）。
- `PlaybackController` 本身不变；只改 `_create_playback_controller` 中 AudioPreviewPlayer 的构造段。
- `_create_playback_controller` 中 waveform provider 注册段（main_window.py:1034-1038）本轮不动，由 T5（dual-track-display-and-migration）改造为按轨 provider——两任务改同一函数的不同段，先合入者不破坏后合入者。
- 测试沿用 test_preview_widget.py 现有构造模式（stream_factory 注入，无需真实声卡）。
