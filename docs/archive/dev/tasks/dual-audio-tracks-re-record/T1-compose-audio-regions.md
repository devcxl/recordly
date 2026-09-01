---
issue: 127
test_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/test_audio_mix.py tests/test_audio_capture.py
verify_commands:
  - QT_QPA_PLATFORM=offscreen pytest -q tests/
---

# compose-audio-regions

## Builds

新增 `core/audio_mix.compose_audio(regions, samplerate, duration)` 纯 numpy 内存音频合成：任意 `AudioRegion` 列表（切片 × 音量 → 定位 → 逐样本相加 → clamp，缺失文件跳过、采样率不一致重采样）可直接合成为时间轴音频；无任何编辑时（两个全时长 region）输出与旧版本 `mix_audio_results` 混音结果逐样本等价。`read_wav` 从 `app/main_window.py` 提升到 `core/audio_capture.py` 供后续导出/预览/波形按轨共用。

这是后续导出接线（T2）、预览接线（T4）、波形按轨（T5）的共同底座。

## Acceptance Criteria

- [ ] 无编辑等价性：两个全时长 region（volume=1.0，audio_path 指向分别写入 mic/system 内容的 wav）的合成输出与 `mix_audio_results(两个 wav 的 AudioResult)` 逐样本一致（浮点误差内）
- [ ] 编辑语义（参数化）：删除某 region → 该时间区间样本为 0；volume=0.5 → 样本减半；source_start/source_end 切片 → 仅窗口内样本；start_ms 后移 → 样本位于对应位置、前段为 0
- [ ] 采样率不一致重采样：region wav 采样率 ≠ samplerate → 输出长度 == round(duration*samplerate)（duration 给定），信号形状近似保留（正弦峰位置一致）
- [ ] 缺失文件：audio_path 不存在 → 该 region 无贡献、不抛异常；全部缺失 → 返回 None
- [ ] duration 给定 → 输出长度 == round(duration*samplerate)（超出截断）；未给定 → max(region.end_ms)
- [ ] `core.audio_capture.read_wav(path)` 返回 `AudioResult | None`；`main_window._read_wav` 委托或删除后统一走 core 函数，`_load_project_audio` 等既有调用点行为不变（回归）
- [ ] 回归：全量既有测试绿（554 基线）

## Blocked By

- None

## Implementation Notes

- `compose_audio` 纯 Python + numpy，无 Qt/FFmpeg 依赖，可独立单测（新 `tests/test_audio_mix.py`）。
- 合成语义与 `mix_audio_results`（core/audio_capture.py:23-46）一致：加法混合 + clamp 到 [-1.0, 1.0]；输出声道数 = max(2, 各输入声道数)。
- 采样率 ≠ samplerate 的 region 用 `np.interp` 线性插值重采样（覆盖 audio_extra 外部文件如 48k；内置轨与补录 wav 均为项目采样率，speed=1 直接 np 切片，不做插值）。
- `read_wav` 提升（方案 §5.3）：从 `app/main_window.py:60` 迁移到 `core/audio_capture.py`（`AudioResult` 定义处），返回类型改为 `AudioResult | None`；main_window 内 `data, sr, ch = result` 的解包调用点同步适配。
- 测试写临时 wav 复用 `_write_wav`（app/main_window.py:42）或等价 wave 写入逻辑（方案 §9.1）。
