---
issue: 132
test_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/test_record_audio_dialog.py tests/test_commands.py tests/test_timeline.py tests/test_main_window.py
verify_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/
---

# mic-re-record

## Builds

麦克风补录闭环：右键 mic 轨 clip →「补录音频」→ 独立录音窗口（`RecordAudioDialog`，mic_factory 注入可测）→ 录音写入项目目录 `re_record_<时间戳>.wav` → `CompositeCommand([ChangeVolumeCommand(原 clip → 0.0), AddClipCommand(新 clip)])` 单步可撤销（原 clip 整段 volume=0 保留，新 clip 覆盖同一时间区间）。对话框取消 / 写盘失败 / 0 秒录音均零残留；补录后保存再打开完整恢复。

## Acceptance Criteria

- [ ] 命令组合（test_commands / test_timeline）：执行后原 clip volume=0、新 clip 存在且 start/source_path/volume/source_start 正确（end = min(目标 end, start + 录音时长)）；`undo()` 一次后原 clip 音量恢复、新 clip 消失；`redo()` 恢复
- [ ] 录音窗口（qapp + FakeCapture）：点开始 → 结束 → `audio_result` 为 FakeCapture 返回的 AudioResult；直接关闭 → `audio_result` 为 None 且 FakeCapture 被 stop（丢弃数据）；0 秒数据 → reject 且不产生文件
- [ ] 右键入口：timeline 上下文菜单对 `clip.type == "audio"` 追加「补录音频」→ 发射 `re_record_requested(track_index, clip_index)`；audio_system / audio_extra / video clip 无此入口
- [ ] 端到端 `_on_re_record_requested`（monkeypatch `RecordAudioDialog` 返回 Accepted/Rejected + FakeCapture + `_write_wav` 抛 IO 错误）：Accepted → timeline 出现新 clip、项目目录出现 wav；Rejected → timeline 不变、无文件；写盘失败 → 无新 clip、残留文件被清理（monkeypatch `os.remove` 断言）
- [ ] 补录后保存/加载：`_collect_project_state` → `_restore_timeline_and_playback` 完整恢复（新 clip 与静音状态）
- [ ] 回归：全量既有测试绿

## Blocked By

- dual-track-display-and-migration

## Implementation Notes

- `RecordAudioDialog` 新模块 `ui/record_audio_dialog.py`（方案 §7.1）：复用 `core.audio_capture.MicrophoneCapture`（sounddevice 回调线程，UI 不阻塞）；`mic_factory=MicrophoneCapture` 构造参数为注入点；开始 → `capture.start()` + QTimer 计时（1s 刷新）；结束 → `capture.stop()` → `audio_result` + accept；关闭/取消 → 未结束时 stop 并丢弃；录音时长 ≤ 0 → 提示并 reject。
- `_on_re_record_requested`（方案 §7.3）：`self._project_dir` 为空 → 提示拒绝；wav 路径 `<project_dir>/re_record_<YYYYmmdd_HHMMSS>.wav`；`_write_wav`（main_window.py:42）写盘失败 → 清理残留文件 + 通知 + return；新 clip `source_start=0`、`end=min(目标 end, start+录音时长)`；`insert_at` 按 start 升序 bisect；命令经 timeline `_push_undo`（或新增 `push_command` 公共方法）压栈。
- 撤销语义：`CompositeCommand.undo` 逆序 → 删新 clip → 恢复原 clip 音量，一次撤销完整还原（ADR-3）；补录 wav 撤销后不回收（文件作为项目资产，YAGNI）。
- 依赖 T5 的原因（用户约束）：补录端到端与保存/加载闭环复用双轨恢复链路（`ensure_builtin_audio_tracks` + `_restore_timeline_and_playback`），且 timeline 右键菜单改动落在 T5 的 timeline 基线之上。
- 新测试文件 `tests/test_record_audio_dialog.py`（qapp fixture + FakeCapture）。
