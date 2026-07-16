# 导出速度优化 — 诊断与方案

**日期:** 2026-07-16
**状态:** Proposed
**目标:** 15 秒视频导出 ≤30s（2× 实时），最终目标 ≤15s

---

## 1. 真实项目 Profiling

### 1.1 测试项目

| 属性 | 值 |
|------|----|
| 路径 | `projects/20260716_064342` |
| 录制分辨率 | 2560×1440 |
| 导出分辨率 | 1920×1080 |
| 源帧数 | 403 |
| 源帧存储 | JPEG (frames.data, 554MB) |
| 实际采集 fps | ~25.2 (403/16.0s) |
| 配置 fps | 60 (source.fps, 不反映实际采集率) |
| zoom clips | 11 段，覆盖 ~50% 时间线 |
| cursor events | 5442 条 |
| 时间线 clips | video + audio + zoom |

### 1.2 分段耗时（50 帧采样，每输出帧 @ 2560→1920）

```
JPEG decode (cv2, 2560×1440)   █████████       27.8ms  (21%)
compose (fromarray + effects)   ████████████    39.2ms  (29%)
  └─ 无 zoom 时                  8.3ms
  └─ 有 zoom 时                 97.5ms  (crop + LANCZOS resize)
resize 2560→1920 (LANCZOS)      ██████████████  45ms   (34%)
convert RGBA→RGB + tobytes      ██████          21ms   (16%)
pipe write + NVENC               ▏              <1ms   (<1%)
────────────────────────────────────────────────────────
每输出帧合计                    ~134ms
```

### 1.3 全量导出实测

| 配置 | 耗时 | 吞吐 | 输出帧 | 体积 |
|------|------|------|--------|------|
| CPU 30fps | 30.6s | 31fps | 958 | 17.7MB |
| GPU 30fps | 29.7s | 32fps | 958 | 12.4MB |
| CPU 60fps | 30.9s | 31fps | 958 | 17.7MB |
| GPU 60fps | 27.6s | 35fps | 958 | 12.4MB |

> 导出 fps 设置不影响 total_output_frames（由 compositor.fps=60 决定），故 30fps 和 60fps 耗时几乎相同。

### 1.4 音频耗时

音频处理不在逐帧循环中：
- WAV 读取 + AAC 编码在 ffmpeg 子进程中与视频并行（GPU 路径）
- 音频 filtergraph（混音、变速、延迟）在 `_build_audio_filtergraph()` 中一次性 `subprocess.run`，约 0.2–0.5s
- 对总导出时间的影响 < 2%

### 1.5 当前并行化效果

理论串行：958 帧 × 134ms = **128s**
实测 GPU：**27.6s**，约 4.6× 加速

并行机制已部分生效，但受限于两个并发 bug（见 §3）。

> 分段 profiling 脚本：`tools/profile_export.py` — 可独立运行复现上述数据。

---

## 2. 合成 Benchmark vs 真实项目差异

| 维度 | 合成 300 帧测试 | 真实 16s 项目 | 影响 |
|------|----------------|--------------|------|
| 源分辨率 | 1920×1080 内存数组 | 2560×1440 JPEG 文件 | 1.78× 像素 + 磁盘解码 |
| compose 路径 | fromarray only | fromarray + zoom crop + cursor effect | zoom 时 12× compose 耗时 |
| resize | 1920→1920 no-op | 2560→1920 LANCZOS | 新增 45ms/frame |
| format convert | RGB→RGB no-op | RGBA→RGB | 新增 21ms/frame |
| 输出帧数 | 300 | 958 | 3.2× |

合成 benchmark 的 2.6s/300帧 ≈ **8.7ms/帧** 与实际 134ms/帧 差 15 倍，因为合成测试跳过了 JPEG decode、zoom、resize 和 format convert。

---

## 3. 并发正确性 Bug

### Bug 1：loader fh.seek/read 无锁

**位置**: `core/compositor.py:156-175`

```python
fh = open(store_path, "rb")   # 共享文件句柄
def loader(_i):
    fh.seek(off)               # ← 多线程竞态
    payload = fh.read(length)  # ← 可能读到其他帧的数据
```

实测 8 线程并发解码 → 1/1308 帧损坏（低频但确定）。

### Bug 2：CursorEffect 可变状态

**位置**: `core/cursor_effects.py:73,88`

```python
self._smooth_x += ...   # ← 多线程读写
self._trail.append(...) # ← 多线程修改
```

---

## 4. 优化方案（按收益/风险）

### Phase 1：修复正确性 + 5 行改动 → 20-25s

| # | 改动 | 位置 | 行数 | 收益 | 风险 |
|---|------|------|------|------|------|
| 1 | loader 加 `threading.Lock` 保护 seek/read | `compositor.py:156` | 3 | 消除黑帧 + 安心全开并行 | 低 |
| 2 | CursorEffect 加 `threading.Lock` 保护 apply() | `cursor_effects.py:256` | 5 | 消除光标错乱 | 低 |
| 3 | cache_size 12→128 | `compositor.py:154` | 1 | 提高 cache hit 率 | 低 |

### Phase 2：zoom + resize 加速 → 15-18s

| # | 改动 | 说明 | 收益 |
|---|------|------|------|
| 4 | zoom crop resize `LANCZOS→BILINEAR` | 3-5× zoom 加速，肉眼不可辨 | 30-50ms/frame |
| 5 | compose 直接输出目标分辨率 | 跳过 exporter 的 2560→1920 LANCZOS resize | 45ms/frame |
| 6 | compose 输出 RGB（非 RGBA） | 跳过 convert("RGB") | 21ms/frame |

### Phase 3：有界预解码 + 乱序 → 10-13s

| # | 改动 | 说明 | 收益 |
|---|------|------|------|
| 7 | 256 MiB decoded byte-LRU + inflight 同帧去重 | 限制内存并避免重复 JPEG decode | 降低解码开销 |
| 8 | `FIRST_COMPLETED` 乱序准备 + effects/FFmpeg 顺序输出 | 消除 head-of-line blocking | 并行效率提升 |

> 全量预解码会使 2K 一分钟素材占用约 18.5 GiB，禁止作为默认路径。

### Phase 4：架构级 → 5-8s

| # | 改动 | 说明 |
|---|------|------|
| 9 | 全 GPU pipeline (NVDEC decode → scale_cuda → NVENC) | 消除 CPU↔GPU 传输 |
| 10 | 录制时直接存合成后帧 | 跳过导出 compose |

---

## 5. 验收标准

| 指标 | 当前 | Phase 1 | Phase 2 | Phase 3 | 验证方法 |
|------|------|---------|---------|---------|----------|
| 16s 1080p GPU 导出 | 27.6s | ≤25s | ≤18s | ≤13s | 3 次运行取中位数 |
| 输出帧损坏率 | 偶尔黑帧 | 0 | 0 | 0 | 连续 10 次导出无 RuntimeException |
| Cursor 位置 | 偶尔错乱 | 串行=并行 ±1px | 串行=并行 ±1px | 逐帧 bytes 一致 | 确定性帧 pixel 对比 |
| 全量测试 | 343 passed | 343 passed | 343 passed | 360 passed | `pytest -q` |
| 视觉质量 (BILINEAR) | LANCZOS | — | 无可见劣化 | 无可见劣化 | 2× 放大 A/B 对比 |

---

## 6. 预期代码触点

| 文件 | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|
| `core/compositor.py` | Lock + cache_size | compose 输出目标分辨率 | byte-LRU + inflight 去重 |
| `core/cursor_effects.py` | Lock | 目标坐标系 render_scale | 顺序 effects |
| `core/exporter.py` | — | 目标尺寸 RGB + BILINEAR | 乱序准备 + 顺序写入 |
| `core/screen_capture.py` | — | — | 直接录制路径 byte-LRU + inflight 去重 |
| `tests/test_recording_roundtrip.py` | 回归 | 新增 | FPS/时长回归 |

---

## 7. 不在范围内

- 修改录制管线（存储格式、frame_style 持久化等）
- 全 GPU pipeline（NVDEC/scale_cuda）
- 用户 55s 声明的视频：实际最长的录制项目为 23s/571 帧。本诊断以 16s/403 帧项目为基准，优化同样适用于更长视频。
