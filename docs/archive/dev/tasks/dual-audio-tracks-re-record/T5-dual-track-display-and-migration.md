---
issue: 131
test_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/test_main_window.py tests/test_timeline.py
verify_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/
---

# dual-track-display-and-migration

## Builds

时间线双轨展示与旧项目兼容：`_populate_timeline` 建立 `audio`（麦克风）+ `audio_system`（系统音频）双轨、内置轨 clip 带绝对 `source_path`；新增公共函数 `ensure_builtin_audio_tracks(project, project_dir)` 幂等补齐旧项目（clip 回退 `source.audio_mic`、缺失 system 轨自动补齐），补齐结果随保存写回；波形按轨提供（mic 轨画 mic 波形、system 轨画 system 波形、extra 轨不画）；`audio_system` 轨有独立轨道颜色与拖拽规则。

## Acceptance Criteria

- [ ] `_populate_timeline`（fake `_recorded_data` + fake compositor）：timeline 含 `audio` 与 `audio_system` 轨；mic clip 的 source_path == `<project_dir>/audio_mic.wav`、system clip 同理（对应 wav 存在时）；无对应音频时 source_path 为空串（轨仍存在）
- [ ] `ensure_builtin_audio_tracks(project, project_dir)`（公共函数）：audio 轨 clip 无 source_path → 回退 `_resolve_media_path(project_dir, source.audio_mic)`；`source.audio_system` 存在且无 system 轨 → 追加全时长 clip（source_path 为解析后路径）；已补齐项目调用无变化（幂等）；`source.audio_system` 为空 → 不补
- [ ] `_restore_timeline_and_playback` 加载路径调用补齐，补齐结果随 `_collect_project_state` 保存回 project.json（roundtrip：补后保存再打开，轨道与 source_path 完整保留）
- [ ] 波形按轨：`set_waveform_provider(provider)` 契约改为 `provider(track_type) -> (np.ndarray, samplerate) | None`；`_draw_audio_waveform` 按 `self._tracks[ti].type` 调用 provider；audio 轨收到 mic 数据、audio_system 轨收到 system 数据、audio_extra 轨不绘制（provider 返回 None）
- [ ] main_window 注册 `_track_audio_provider`：按轨取首个 clip 的 source_path 读 wav（结果缓存，随 `_clear_editor_state` / `_populate_timeline` 失效）
- [ ] `TRACK_COLORS` 增加 `audio_system`；`_can_drop_to_track`：audio_system ↔ audio_extra 互通、audio ↔ audio_system 返回 False
- [ ] 回归：全量既有测试绿

## Blocked By

- compose-audio-regions

## Implementation Notes

- `ensure_builtin_audio_tracks` 提取为公共纯函数（方案 §9.4 Seam；放 main_window 或 project.py 均可，但不得让 `Project` 纯数据层耦合路径解析——`_resolve_media_path` 留在 app 层）；`_restore_timeline_and_playback`（main_window.py:1591）在 `set_tracks` 后调用。
- 旧项目补齐逻辑（方案 §8.1）：audio 轨 clip 无 source_path 时回退 `source.audio_mic`；`source.audio_system` 存在且无 system 轨时补轨（全时长 clip，`end=project.duration`）。`_validate_schema` 不校验 timeline 元素 → 零加载错误。
- `_populate_timeline`（main_window.py:881-883）：audio 轨 clip 加 `source_path = os.path.join(project_dir, "audio_mic.wav")`（文件存在才写，否则空串）；新增 `audio_system` 轨（同语义）；缺 mic/system 音频时轨仍创建（PRD AC-1「对应轨存在但无音频」）。
- 波形按轨（方案 §6.2）：`_draw_audio_waveform`（timeline.py:1082）按轨 type 调 provider；`_create_playback_controller`（main_window.py:1034-1038）的 waveform 注册段改为注册 `_track_audio_provider`（与 T4 改同一函数的不同段，先合入者不破坏后合入者）。
- 内置轨 clip 无 id 由 sync 补齐（T3 完成时新 system 轨 clip 自动进入 regions）。
- `TRACK_COLORS`（timeline.py:17）建议 `"audio_system": QColor("#2FA38C")` 一类，区别于 mic 的 `#50C878`（方案 §7.2）。
