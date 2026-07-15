## Parent
Part of #27

## 任务信息
- **Task ID:** T07
- **Slug:** audio-persistence-dual-wav
- **类型:** feature
- **Batch:** B3

## 依赖
depends-on: #32

## 描述
将麦克风和系统音频分别持久化为项目目录下的 WAV 文件。

当前原始录音只存在于内存 `_recorded_data["audio"]`，项目保存时只持久化 `frames.data`，`SourceInfo.audio_mic` 和 `audio_system` 从未写入。重新打开项目后导出丢失音频。

P0 方案（不依赖 ProjectSession）：
1. 录制完成时 `MainWindow._finalize_project()` 中使用 `wave` 模块将 `_recorded_data` 中的麦克风和系统音频 numpy 数组分别写入项目目录下的 `audio_mic.wav` 和 `audio_system.wav`
2. `SourceInfo.audio_mic` / `audio_system` 写入相对路径字符串（如 `"audio_mic.wav"`），由 `Project.save()` 持久化到 `project.json`
3. 打开项目时 `MainWindow._on_open_project()` 读取 `SourceInfo` 中的 WAV 相对路径，用 `wave` 模块加载音频 numpy 数组，恢复到播放/导出可消费的数据结构中
4. 混音不持久化 — 播放/导出时按现有规则动态混音
5. 导出流程中通过 `SourceInfo` 的 WAV 路径获取音频，替代直接访问 `_recorded_data["audio"]`

> P1 阶段 T10 将 WAV 读写逻辑迁移到 `ProjectSession.save_audio()` / `load_audio()`。

## 验收标准
- [ ] 录制含麦克风 + 系统音频 → 项目目录含 `audio_mic.wav` + `audio_system.wav`
- [ ] `project.json` 中 `SourceInfo.audio_mic` / `audio_system` 为有效相对路径
- [ ] 保存 → 重启 → 打开项目 → 播放有音频
- [ ] 保存 → 重启 → 打开项目 → 导出有音轨
- [ ] `pytest tests/test_main_window.py -q -k "audio"` 通过
- [ ] 新增集成测试：录制→保存→重新加载→验证音频数据一致性

## 输出文件
- `app/main_window.py` — `_finalize_project()` WAV 写入 + `_on_open_project()` WAV 读取恢复
- `core/recorder.py` — 暴露麦克风/系统音频 numpy 数组接口（如需）
- `core/project.py` — `SourceInfo.audio_mic`/`audio_system` 在 save/load 流程中正确读写
- `tests/test_main_window.py` — 音频持久化集成测试
- `tests/test_recorder.py` — 音频数据收集接口测试

## 需求追踪
- F7（双音轨持久化）
- US-2（项目持久化与重新打开）
- US-3（正确导出）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
