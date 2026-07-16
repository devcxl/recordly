## Parent
Part of #27

## 任务信息
- **Task ID:** T08
- **Slug:** export-correctness
- **类型:** fix
- **Batch:** B4

## 依赖
depends-on: #33
depends-on: #34

## 描述
修复三个导出正确性问题：

**F2 — 打开项目导出崩溃：** `MainWindow._on_export()` 在 `_recorded_data is None` 时无条件执行 `self._recorded_data.get("audio")`。修复：使用 `getattr` + 默认值处理，与 `_create_playback_controller()` 保持一致。音频数据通过 T07 持久化的 WAV 文件（`SourceInfo.audio_mic`/`audio_system` 路径）加载，不再依赖 `_recorded_data`。

**F8 — 音频 source time / timeline time 分离：** `core/exporter.py` 中 `_build_audio_filtergraph` 当前将 `start_ms/end_ms` 同时用于 atrim（源裁剪）和 adelay（时间线放置）。修复：
- `atrim=start=source_start_ms/1000:end=source_end_ms/1000` — 截取源文件
- `adelay=start_ms|start_ms` — 时间线延迟放置
- 音频移动到非零播放头、裁剪头尾或变速后音画同步

**F9 — 项目 FPS 单一时间基准：** MP4 导出 `ffmpeg.input` 的 `r=` 当前使用全局 `settings.fps`，应使用 `compositor.fps`。GIF 输出帧率也统一使用 `compositor.fps`。

## 验收标准
- [ ] 首页项目卡片 → 打开项目 → 导出不崩溃（`_recorded_data is None` 时优雅处理）
- [ ] 移动音频片段到非零播放头 → 导出音画同步
- [ ] 裁剪音频头尾 → 导出只使用裁剪后的源区间
- [ ] 变速视频 + 音频 → 导出音画同步
- [ ] 60 FPS 项目导出 → 时长 = total_frames / 60（与当前配置 FPS 无关）
- [ ] 30 FPS 项目导出 → 时长 = total_frames / 30
- [ ] `pytest tests/test_exporter.py -q` 全部通过
- [ ] 更新 `test_exporter.py:107-134` 中固化错误行为的音频测试

## 输出文件
- `core/exporter.py` — F8 atrim/adelay 分离 + F9 compositor.fps
- `app/main_window.py` — F2 _on_export 空值处理，通过 SourceInfo WAV 路径加载音频
- `tests/test_exporter.py` — 更新音频测试 + 新增 FPS 测试
- `tests/test_main_window.py` — 新增打开项目→导出流程测试

## 需求追踪
- F2（打开项目导出）
- F8（音频时间分离）
- F9（项目 FPS 基准）
- US-3（正确导出）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
