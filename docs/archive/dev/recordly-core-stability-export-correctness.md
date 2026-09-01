# T08: export-correctness — 导出正确性修复

**Project:** Recordly  
**Task ID:** T08  
**Slug:** export-correctness  
**Issue:** #35  
**类型:** fix  
**Batch:** B4  
**依赖:** T06 (#33), T07 (#34)

---

## 1. 目标

修复三个导出正确性问题：
- **F2:** 打开已保存项目后导出不崩溃（`_recorded_data is None`）
- **F8:** 音频 source time 与 timeline time 严格分离（atrim 用源区间，adelay 用时间线位置）
- **F9:** MP4 和 GIF 统一使用 `compositor.fps` 作为时间基准，不再用 `settings.fps`

---

## 2. 前置条件

- [x] T06 完成：`Project.save()` 原子写入
- [x] T07 完成：`SourceInfo.audio_mic`/`audio_system` 写入了有效 WAV 相对路径
- [x] `Compositor.fps` 属性可用（当前代码 `c.fps` 在 exporter.py line 148, 237 已在使用）

---

## 3. 当前状态

### F2 — `_on_export()` line 920

```python
# 当前代码（崩溃路径）
audio = self._recorded_data.get("audio")  # _recorded_data is None → AttributeError
```

### F8 — `_build_audio_filtergraph()` lines 364-369, 386-387

```python
# 当前代码（错误: start/end 同时用于 atrim 和 adelay）
# 原始音频:
chain = f'[0:a]atrim=start={clip.start}:end={clip.end},...'
delay = round(clip.start * 1000)
chain += f',adelay={delay}|{delay}{label}'

# 额外音频:
source_start = r.start_ms / 1000.0
source_end = r.end_ms / 1000.0
parts.append(f'[{idx}:a]atrim=start={source_start}:end={source_end},...,adelay={delay}|{delay}{label}')
```

`AudioRegion` 有 `start_ms/end_ms`（时间线位置）和 `source_start_ms/source_end_ms`（源截取区间），但当前代码只用了 `start_ms/end_ms`。

### F9 — FPS 混用

```python
# _export_mp4() line 128: r=s.fps          # ← 应改为 c.fps
# _on_export() line 909: fps=dialog.gif_fps_value if is_gif else self.config.default_fps  # ← 应改为 compositor.fps
# _build_gif_output() line 257: r=s.fps    # ← 应改为 c.fps
```

---

## 4. Red → Green → Refactor 实施步骤

### 🔴 RED — 编写失败测试

#### Step 1: `tests/test_exporter.py` — FPS 测试

```python
def test_mp4_export_uses_compositor_fps_not_settings_fps():
    """
    Red: compositor.fps=60, settings.fps=30 → 导出输入 r=60。
    当前: 使用 settings.fps → 时长计算错误。
    """
    ...

def test_gif_export_uses_compositor_fps_not_settings_fps():
    """
    Red: compositor.fps=60, settings.fps=30 → GIF 输入 r=60。
    当前: _build_gif_output 使用 settings.fps → 时长计算错误。
    """
    ...

def test_export_with_fps_30_project_duration_correct():
    """
    Red: 30 FPS 项目，total_frames=90 → duration=90/30=3.0s
    """
    ...

def test_export_with_fps_60_project_duration_correct():
    """
    Red: 60 FPS 项目，total_frames=120 → duration=120/60=2.0s
    """
    ...
```

#### Step 2: `tests/test_exporter.py` — 音频 source/timeline time 分离测试

```python
def test_atrim_uses_source_interval_not_timeline_interval():
    """
    Red: AudioRegion(source_start_ms=0, source_end_ms=5000, start_ms=2000, end_ms=7000)
    → atrim=start=0:end=5, adelay=2000|2000
    当前: atrim=start=2:end=7 → 音源截取错误。
    """
    ...

def test_moved_audio_region_is_synced_with_video():
    """音频移动到非零播放头后导出音画同步"""
    ...

def test_trimmed_audio_uses_correct_source_range():
    """裁剪音频头尾后导出使用正确的源区间"""
    ...
```

#### Step 3: `tests/test_main_window.py` — 打开项目导出不崩溃测试

```python
def test_export_from_opened_project_does_not_crash_with_null_recorded_data():
    """
    Red: 加载已保存项目后 _recorded_data is None，导出应不崩溃。
    当前: line 920 .get("audio") 抛 AttributeError。
    """
    ...
```

**验证命令:** `pytest tests/test_exporter.py tests/test_main_window.py -q -k "export"` → 预期新增测试 FAIL

---

### 🟢 GREEN — 最小实现

#### Step 4: `core/exporter.py` — F9: FPS 统一使用 compositor.fps

**改动范围:**

| 位置 | 当前代码 | 修改为 |
|------|---------|--------|
| `_export_mp4()` line 128 | `r=s.fps` | `r=c.fps` |
| `_build_gif_output()` line 248 | `r=self._compositor.fps` | 保持不变（已正确） |
| `_build_gif_output()` line 257 | `r=s.fps` | `r=self._compositor.fps` |
| `_export_mp4()` line 184 | `fps={s.fps}` (debug) | `fps={c.fps}` |

**关键：** `compositor.fps` 已在 `_export_mp4()` 中作为 `c.fps` 可用（line 148: `total / c.fps`），无需新增属性。

---

#### Step 5: `core/exporter.py` — F8: 音频 source/timeline time 分离

**文件:** `core/exporter.py`  
**方法:** `_build_audio_filtergraph()` (line 332-416)

**原始音频处理 (lines 358-377):**

```python
# 当前（line 360-364）:
chain = (
    f'[0:a]atrim=start={clip.start}:end={clip.end},'
    'asetpts=PTS-STARTPTS'
)

# 修改为:
source_start = getattr(clip, 'source_start', clip.start)
source_end = getattr(clip, 'source_end', clip.end) or clip.end
chain = (
    f'[0:a]atrim=start={source_start}:end={source_end},'
    'asetpts=PTS-STARTPTS'
)
```

**额外音频处理 (lines 379-388):**

```python
# 当前（line 382-387）:
source_start = r.start_ms / 1000.0
source_end = r.end_ms / 1000.0
parts.append(
    f'[{idx}:a]atrim=start={source_start}:end={source_end},'
    f'asetpts=PTS-STARTPTS{vol},adelay={delay}|{delay}{label}')

# 修改为:
src_start = r.source_start_ms / 1000.0
src_end_val = r.source_end_ms if r.source_end_ms is not None else r.end_ms
src_end = src_end_val / 1000.0
parts.append(
    f'[{idx}:a]atrim=start={src_start}:end={src_end},'
    f'asetpts=PTS-STARTPTS{vol},adelay={delay}|{delay}{label}')
```

**契约:** 
- `atrim` 始终使用 `source_start_ms/source_end_ms`（源区间）
- `adelay` 始终使用 `start_ms`（时间线位置）

---

#### Step 6: `app/main_window.py` — F2: `_on_export` 空值安全

**文件:** `app/main_window.py`  
**方法:** `_on_export()` (line 876-946)

**改动:** 替换 line 877 的检查和 line 920 的音频获取：

```python
def _on_export(self):
    # Line 877-881 替换: 不受 _recorded_data 是否 None 限制
    has_frames = self._compositor._frames is not None
    has_project = self._project is not None
    if not has_frames and not has_project:
        self._show_notification("无法导出", "请先录制一段视频或打开一个项目", "warning")
        return

    # ... 中间代码保持不变 ...

    # Line 920-923 替换为:
    audio_data = None
    if self._recorded_data:
        audio_info = self._recorded_data.get("audio")
        if audio_info:
            audio_data = audio_info.get("mixed") or audio_info.get("data")
    elif self._project and self._project.source:
        # 从持久化 WAV 加载（T07 提供的能力）
        wav_audio = self._load_audio_from_wavs(self._project, self._current_project_path)
        if wav_audio:
            audio_data = wav_audio.get("mixed") or wav_audio.get("mic") or wav_audio.get("system")
            settings.samplerate = wav_audio.get("samplerate", 44100)

    if audio is not None:  # 原有代码继续
        settings.samplerate = audio.samplerate

    # Line 909 FPS 修改:
    settings = ExportSettings(
        ...
        fps=self._compositor.fps,  # ← 替换 self.config.default_fps / dialog.gif_fps_value
        ...
    )
```

---

#### Step 7: `tests/test_exporter.py` — 更新固化错误行为的现有测试

**位置:** `test_exporter.py:107-134`（atrim/adelay 测试）

将断言中的 `atrim=start=...:end=...` 更新为使用 source 区间而非 timeline 区间。

---

### 🔵 REFACTOR — 无行为变更的收敛

#### Step 8: 统一 fps 引用消除 settings.fps 依赖

**文件:** `core/exporter.py`

`ExportSettings.fps` 字段保留（用于序列化/UI），但 `_export_mp4()` 和 `_export_gif()` 中所有 `s.fps` 引用替换为 `c.fps`。唯一剩余的 `s.fps` 引用在 GIF 路径的 `r=s.fps`（`_build_gif_output()` line 257）— 也需要改为 `r=self._compositor.fps`。

```python
# _build_gif_output line 248 (已正确):
r=self._compositor.fps

# _build_gif_output line 257 (修改):
# 当前: r=s.fps
# 改为: r=self._compositor.fps
```

**最终效果:** `ExportSettings.fps` 仅作为 UI 回显值，实际渲染使用 `compositor.fps`。

---

## 5. 接口/契约

### FPS 时间基准契约

| 导出格式 | 输入帧率 | 输出时长 |
|---------|---------|---------|
| MP4 | `ffmpeg.input(..., r=compositor.fps)` | `total_frames / compositor.fps` |
| GIF | `ffmpeg.input(..., r=compositor.fps)` | `total_frames / compositor.fps` |

**不做 FPS 转换/重采样。**

### AudioRegion source time / timeline time 契约

```
AudioRegion {
    source_start_ms, source_end_ms  → atrim 参数（源文件截取区间）
    start_ms, end_ms                → adelay 参数（时间线放置位置）
}
```

### `_on_export` 音频获取优先级

```
1. self._recorded_data["audio"] 存在 → 使用
2. self._project.source.audio_mic/audio_system WAV → 动态加载 → 混音
3. 都不存在 → audio_data=None → 导出无声视频
```

---

## 6. 数据模型变化

**无新字段/表。** `AudioRegion` 已有 `source_start_ms/source_end_ms/start_ms/end_ms`。

---

## 7. 测试指引

### 单元测试 (test_exporter.py)

```python
class TestExportFps:
    def test_mp4_input_rate_equals_compositor_fps(self):
        """mock ffmpeg.input 调用，验证 r=compositor.fps"""
    def test_gif_input_rate_equals_compositor_fps(self):
        """mock _build_gif_output，验证 ffmpeg.input r=compositor.fps"""
    def test_duration_calculation_uses_compositor_fps(self):
        """total_frames / compositor.fps"""
    def test_duration_independent_of_settings_fps(self):
        """settings.fps=30, compositor.fps=60 → duration=total/60"""

class TestAudioTimeSeparation:
    def test_atrim_uses_source_start_end(self):
        """验证 atrim=start=source_start_ms/1000:end=source_end_ms/1000"""
    def test_adelay_uses_timeline_start(self):
        """验证 adelay=start_ms|start_ms"""
    def test_moved_audio_region_sync(self):
        """region 移动后导出音画同步"""
    def test_trimmed_audio_region_source_range(self):
        """裁剪后 atrim 使用裁剪后的源区间"""
```

### 集成测试 (test_main_window.py)

```python
def test_export_from_saved_project_no_crash(self, qtbot, tmp_projects_dir):
    """保存项目 → 重新打开 → _recorded_data is None → 导出不崩溃"""

def test_export_from_saved_project_has_video(self, qtbot, tmp_projects_dir):
    """保存项目 → 重新打开 → 导出 → 输出文件存在且大小 > 0"""
```

---

## 8. 验收标准

- [ ] 首页项目卡片 → 打开项目 → 导出不崩溃（`_recorded_data is None` 时优雅处理）
- [ ] 移动音频片段到非零播放头 → 导出音画同步
- [ ] 裁剪音频头尾 → 导出只使用裁剪后的源区间
- [ ] 变速视频 + 音频 → 导出音画同步
- [ ] 60 FPS 项目导出 → 时长 = total_frames / 60（与 settings.fps 无关）
- [ ] 30 FPS 项目导出 → 时长 = total_frames / 30
- [ ] MP4 输入 `r=compositor.fps`，GIF 输入 `r=compositor.fps`
- [ ] `pytest tests/test_exporter.py -q` 全部通过
- [ ] `pytest tests/test_main_window.py -q -k "export"` 全部通过
- [ ] 现有音频测试（`test_exporter.py:107-134`）已更新为正确契约
- [ ] 全量 `pytest -q` 0 failed

---

## 9. 边界情况与风险

| 边界/风险 | 处理策略 |
|-----------|---------|
| `_recorded_data is None` 且 `_project.source` 无 WAV 路径 | audio_data=None，导出无声视频 |
| `AudioRegion.source_end_ms is None` | 使用 `end_ms` 作为源结束 |
| Clip 没有 `source_start`/`source_end` 属性 | `getattr(clip, 'source_start', clip.start)` 回退 |
| `compositor.fps` 变化后重新导出 | 始终使用当前 compositor.fps，不做历史记录 |
| GIF FPS 修改后与 MP4 不一致 | 统一使用 `compositor.fps`，`_build_gif_output` line 257 `r=self._compositor.fps` |

---

## 10. 任务级验证命令

```bash
# Step 1-3 (Red): 确认新增测试失败
pytest tests/test_exporter.py -q -k "fps or atrim or source"
pytest tests/test_main_window.py -q -k "export_from_saved"

# Step 4-7 (Green): 实现后验证
pytest tests/test_exporter.py -q
pytest tests/test_main_window.py -q -k "export"

# Step 8 (Refactor): 全量回归
pytest tests/ -q

# 手动验收
python main.py
# 1. 录制 30fps → 导出 → 检查时长
# 2. 录制 60fps → 导出 → 检查时长
# 3. 保存 → 重启 → 打开 → 导出（不崩溃）
```

---

## 11. TDD 切片汇总

| 切片 | 步骤 | 验证 |
|------|------|------|
| 🔴 Red | Step 1-3 编写失败测试 | `pytest -q -k "fps or atrim or export_from_saved"` → FAIL |
| 🟢 Green | Step 4-7 修复 F9 + F8 + F2 | `pytest -q -k "fps or atrim or export"` → PASS |
| 🔵 Refactor | Step 8 统一 fps 引用 | `pytest -q` → 0 failed |

---

*本文档由 @architect 基于技术方案 v1.0、任务图、ADR-007 和现有代码 `core/exporter.py:128,248,257,332-416`, `app/main_window.py:877,909,920` 编写。*
