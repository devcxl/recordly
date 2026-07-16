## Parent
Part of #27

## 任务信息
- **Task ID:** T02
- **Slug:** test-infra-recorder-contracts
- **类型:** test-infra
- **Batch:** B0

## 依赖
无

## 描述
修复 Recorder 新增 `store_path` 参数后测试契约未更新导致的 7 个测试失败，以及 `test_playback_receives_recorded_audio_and_video_edit_map` 中缺失 `preview.set_fps()` mock。

具体修复：
1. `tests/test_recorder.py` 中的 FakeScreen class 需接受 `store_path` 参数（与真实 `ScreenCapture.__init__` 签名一致）
2. Recorder 每次启动替换 `screen` 实例导致实例级 monkeypatch 失效 — 修复测试中 mock 注入时机
3. `tests/test_main_window.py` 中 `test_playback_receives_recorded_audio_and_video_edit_map` 的 Preview mock 需添加 `set_fps` 方法

> 本任务不修改 `tests/conftest.py`（当前 conftest 中无 FakeScreen 定义）。

## 验收标准
- [ ] `pytest tests/test_recorder.py -q` 全部通过（当前 7 failed）
- [ ] `pytest tests/test_main_window.py::test_playback_receives_recorded_audio_and_video_edit_map -q` 通过
- [ ] FakeScreen 签名与 ScreenCapture 公共接口一致
- [ ] 无新增 skip/xfail

## 输出文件
- `tests/test_recorder.py` — 更新 FakeScreen + 修复 7 个测试的 mock 注入
- `tests/test_main_window.py` — 添加 preview.set_fps() mock

## 需求追踪
- F1（测试基线恢复）
- US-1（录制验证）
- US-2（播放验证）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
