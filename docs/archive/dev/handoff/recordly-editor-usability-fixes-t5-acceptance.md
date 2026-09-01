# T5 编辑器快捷键组合根验收记录

日期：2026-07-19
范围：`recordly-editor-usability-fixes` T5

## 验收方式

本记录是**自动化 offscreen GUI 验收**，不是人工桌面验收。所有 Qt 用例均通过
`QT_QPA_PLATFORM=offscreen pytest -q ...` 运行；键盘操作由
`PyQt5.QtTest.QTest.keyClick()` 发送，鼠标拖动由 `QMouseEvent` 重放。

## 规格 8.2 可重复验证

| 项目 | 自动化用例 | 验证事实 |
|---|---|---|
| video/audio/audio_extra 切割与 source/undo/redo | `tests/test_timeline.py::TestTimelineCommands::test_split_preserves_source_ranges`、`TestTimelineGui::test_x_key_splits_playhead_video_without_selection`、`TestTimelineGui::test_x_key_splits_audio_clips_with_source_ranges` | video 的命令层 source 分界正确；X 触发 video 切割并选择右段；audio、audio_extra 参数化用例验证 source 分界、undo、redo。 |
| 右段向左、向右拖动 | `tests/test_timeline.py::TestTimelineGui::test_split_right_clip_body_click_drags_with_one_undoable_move` | 参数化覆盖左右两个目标位置；右段主体被选中，移动只生成一个 `MoveClipCommand`，source 保持且 undo/redo 恢复。 |
| X 改为 K 后即时生效及重启保留 | `tests/test_editor_shortcut_integration.py::test_settings_shortcut_save_rebinds_shared_timeline_and_persists` | Settings Accepted 后 Window 与 Timeline 持有同一 `ShortcutRegistry`；X 不切割、K 切割；重建 `AppConfig.load()` 和 `MainWindow` 后仍保持 K。 |
| 窗口级旧键失效、新键触发 | `tests/test_editor_shortcut_integration.py::test_rebound_window_qshortcut_uses_real_events_and_safety_guards` | 真实 `MainWindow` 子类持有实际 `QShortcut`；保存后 Space 不触发，`Ctrl+K` 经 `QTest.keyClick()` 触发播放处理器。 |
| 冲突、单项恢复、全量恢复 | `tests/test_settings_dialog.py::test_shortcut_capture_keeps_draft_on_conflict_or_invalid_key`、`test_shortcut_resets_change_only_draft_after_confirmation` | 冲突展示提示且不改草稿；单项恢复只改草稿；全量恢复需确认并恢复目录默认值。 |
| 输入框/modal/首页守卫 | `tests/test_editor_shortcut_integration.py::test_rebound_window_qshortcut_uses_real_events_and_safety_guards` | 在首页、`QLineEdit` 焦点、模态 `QDialog` 下发送真实 `Ctrl+K` 事件，播放处理器均不触发。 |

本轮复核命令：

```bash
QT_QPA_PLATFORM=offscreen pytest -q \
  tests/test_timeline.py::TestTimelineCommands::test_split_preserves_source_ranges \
  tests/test_timeline.py::TestTimelineGui::test_x_key_splits_playhead_video_without_selection \
  tests/test_timeline.py::TestTimelineGui::test_x_key_splits_audio_clips_with_source_ranges \
  tests/test_timeline.py::TestTimelineGui::test_split_right_clip_body_click_drags_with_one_undoable_move \
  tests/test_editor_shortcut_integration.py \
  tests/test_settings_dialog.py::test_shortcut_capture_keeps_draft_on_conflict_or_invalid_key \
  tests/test_settings_dialog.py::test_shortcut_resets_change_only_draft_after_confirmation \
  tests/test_main_window.py::test_space_shortcut_ignores_non_editor_contexts \
  tests/test_main_window.py::test_space_shortcut_ignores_input_focus
```

## R1 导出边界复核

通过 `git diff bb7b9dc..9c2240e -- app/main_window.py` 复核，T5 生产变更仅在
`TimelineWidget` 创建和 Settings Accepted 后注入同一个 `ShortcutRegistry`。再以
`git diff bb7b9dc..9c2240e --name-only` 核对，该提交未修改
`core/exporter.py`、`app/export_controller.py` 或其他导出模块。

因此普通音频切割的本期验收仅覆盖 Timeline 模型、`source_start`/`source_end` 和
undo/redo；没有改变导出管线。仅切普通音频是否改变真实导出结果仍是已知 R1 风险，
需要独立需求与导出语义设计后处理。
