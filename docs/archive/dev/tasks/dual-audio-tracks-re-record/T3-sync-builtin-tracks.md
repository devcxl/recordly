---
issue: 129
test_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/test_project.py tests/test_main_window.py
verify_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/
---

# sync-builtin-tracks

## Builds

`_on_clips_changed` 把 `audio` / `audio_system` / `audio_extra` 三轨 clip 合并 sync 进 `_audio_regions`——内置轨（麦克风/系统音频）的删除、移动、音量、裁剪编辑真实进入 region 列表（数据层行为，是预览与导出生效的底座）。`sync_audio_regions_from_clips` 签名与语义不变（零 schema 变更，region 无需新增 track 字段）。

## Acceptance Criteria

- [ ] `sync_audio_regions_from_clips` 传入 audio + audio_system + audio_extra 混合 clip 列表 → 返回 regions 各字段（start_ms / end_ms / source_start_ms / source_end_ms / audio_path / volume）正确；无 id clip 自动补 uuid（既有语义）
- [ ] 幂等：重复调用 region id 稳定，字段随 clip 最新值更新（volume / source_path 变更反映到 region）
- [ ] `_on_clips_changed`（main_window.py:1209）接线：audio 轨 clip 变化（音量/删除/移动/拆分）→ `self._audio_regions` 相应更新；audio_extra 轨行为不变（回归）
- [ ] 回归：test_project.py `TestAudioRegionSync` 扩展 + 全量既有测试绿

## Blocked By

- None

## Implementation Notes

- 只改 `_on_clips_changed` 的 audio_clips 过滤（main_window.py:1228-1233）：`t.type in ("audio", "audio_system", "audio_extra")`；`sync_audio_regions_from_clips`（core/project.py:140）不动。
- 现有 sync 语义已覆盖全部需求（方案 §4.1）：`audio_path = clip.source_path or region.audio_path`（内置轨 clip 有绝对路径即生效）、`source_end` 含 speed（内置轨恒 1.0）、`volume` 映射、删除 clip → 无对应 region → 该区间静音且不改变总时长。
- 本 Task 完成时若 T2/T4 尚未合入，内置轨编辑已进入 regions 但预览/导出尚未消费——regions 为内部状态，仓库保持可工作（无 UI 回归）。
- 测试沿用 TestAudioRegionSync 现有模式（core/project.py 纯函数 + main_window qt 接线）。
