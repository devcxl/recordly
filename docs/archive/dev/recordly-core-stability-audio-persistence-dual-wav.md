# T07: audio-persistence-dual-wav — 双音轨 WAV 持久化

**Project:** Recordly  
**Task ID:** T07  
**Slug:** audio-persistence-dual-wav  
**Issue:** #34  
**类型:** feature  
**Batch:** B3  
**依赖:** T05 (#32)

---

## 1. 目标

将录制时收集的麦克风和系统音频 numpy 数组分别持久化为项目目录下的 `audio_mic.wav` / `audio_system.wav`，并将相对路径写入 `SourceInfo.audio_mic` / `audio_system` 字段，随 `project.json` 原子保存。混音不持久化——播放/导出时动态混音。

---

## 2. 前置条件

- [x] T05 完成：录制入口统一，Recorder 暴露麦克风/系统音频数据
- [x] `Recorder.stop_recording()` 返回 dict 含 `mic_audio` 和 `system_audio` numpy 数组
- [x] `SourceInfo.audio_mic` 和 `audio_system` 字段已存在于 `core/project.py`

---

## 3. 当前状态

```text
_recorder.stop_recording() → dict{
    "frames": list[np.ndarray],
    "audio": AudioResult(mic=np.ndarray, system=np.ndarray, mixed=np.ndarray, samplerate=int),
    ...
}

MainWindow._finalize_project() → 只保存 frames.data/frames.idx + project.json
MainWindow._on_open_project() → 只加载 frames，不恢复音频
MainWindow._on_export() (line 920) → self._recorded_data.get("audio") → 打开项目时 _recorded_data is None → AttributeError
```

---

## 4. Red → Green → Refactor 实施步骤

### 🔴 RED — 编写失败测试（先写测试，确认失败）

#### Step 1: `tests/test_main_window.py` — 音频持久化集成测试（不可用状态）

```python
# 新增：测试录制后项目目录含 WAV 文件
def test_audio_persistence_writes_wav_files_after_recording(qtbot, tmp_path):
    """
    Red: 录制完成后项目目录应含 audio_mic.wav + audio_system.wav。
    当前不写入 → 断言 os.path.exists 失败。
    """
    ...

# 新增：测试 project.json 中 SourceInfo.audio_mic/audio_system 指向正确相对路径
def test_source_info_contains_audio_relative_paths(qtbot, tmp_path):
    """
    Red: project.json 的 source.audio_mic/audio_system 应为相对 WAV 路径。
    当前为空字符串 → 断言失败。
    """
    ...

# 新增：测试保存 → 重启 → 打开 → 音频数据恢复
def test_reopen_project_restores_audio_data(qtbot, tmp_path):
    """
    Red: 保存→重新打开→播放应有音频。
    当前 _on_open_project 不加载音频 → 断言失败。
    """
    ...
```

#### Step 2: `tests/test_recorder.py` — 音频数据收集接口测试

```python
def test_stop_recording_returns_separate_mic_and_system_audio():
    """
    Red: Recorder.stop_recording() 的返回 dict 应含独立的 mic_audio 和 system_audio 键。
    当前只有 "audio" 键 → 断言失败。
    """
    ...
```

#### Step 3: `tests/test_exporter.py` — 打开项目导出测试

```python
def test_export_from_reopened_project_has_audio():
    """
    Red: 打开已保存项目后导出，_on_export 不因 _recorded_data is None 崩溃。
    当前 line 920 的 .get("audio") 会导致 AttributeError → 断言错误。
    """
    ...
```

**验证命令:** `pytest tests/test_main_window.py tests/test_recorder.py tests/test_exporter.py -q -k "audio"`  → 预期新增测试 FAIL

---

### 🟢 GREEN — 最小实现使测试通过

#### Step 4: `core/recorder.py` — 暴露分离的音频数据

**文件:** `core/recorder.py`  
**位置:** `stop_recording()` 方法（当前 line 71-92）

**改动:** 在返回 dict 中新增 `mic_audio` 和 `system_audio` 键：

```python
def stop_recording(self):
    ...
    return {
        "frames": self.screen.get_frames(),
        "audio": AudioResult(
            mic=mic_audio, system=system_audio, mixed=mixed_audio,
            samplerate=..., channels=2
        ),
        "mic_audio": mic_audio,        # 新增: np.ndarray (samples, channels)
        "system_audio": system_audio,   # 新增: np.ndarray (samples, channels)
        "cursor_events": ...,
        "clicks": ...,
        "monitor_offset": ...,
    }
```

**不新增字段/类** — 只是扩展现有返回 dict。

---

#### Step 5: `core/project.py` — remove `_save_temp_wav` migration note

**文件:** `core/project.py` (无改动 — 仅确认 `SourceInfo` 字段已就绪)  
**确认:** `SourceInfo.audio_mic: str = ""` 和 `SourceInfo.audio_system: str = ""` 已存在于 line 169-170。`save()` (line 203-227) 已通过 `asdict(self.source)` 序列化。`load()` (line 229-255) 已通过 `SourceInfo(**data["source"])` 反序列化。字段管道已通。

---

#### Step 6: `app/main_window.py` — WAV 写入（录制完成时）

**文件:** `app/main_window.py`  
**目标方法:** `_finalize_project()` (当前 line 519-548)

**新 helper 方法（在 `_finalize_project` 中调用）:**

```python
import wave

def _save_audio_wavs(self, recorded_data: dict, project_dir: str):
    """将录音数据写入项目目录下的 WAV 文件。"""
    mic = recorded_data.get("mic_audio")
    system = recorded_data.get("system_audio")
    samplerate = recorded_data.get("audio").samplerate if recorded_data.get("audio") else 44100

    def _write_wav(filename, data):
        if data is not None and len(data) > 0:
            path = os.path.join(project_dir, filename)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(2 if data.ndim > 1 else 1)
                wf.setsampwidth(2)
                wf.setframerate(samplerate)
                int16 = (data * 32767).clip(-32768, 32767).astype(np.int16)
                wf.writeframes(int16.tobytes())
            return filename
        return None

    mic_path = _write_wav("audio_mic.wav", mic)
    system_path = _write_wav("audio_system.wav", system)
    return mic_path, system_path
```

**集成到 `_finalize_project()`:**

在 `project.save(...)` 之前调用：
```python
mic_rel, sys_rel = self._save_audio_wavs(self._recorded_data, self._current_project_path)
if project.source:
    project.source.audio_mic = mic_rel or ""
    project.source.audio_system = sys_rel or ""
elif mic_rel or sys_rel:
    project.source = SourceInfo(
        audio_mic=mic_rel or "",
        audio_system=sys_rel or "",
        duration=self._recorded_data.get("source_duration", 0),
        fps=self.config.default_fps,
    )
```

---

#### Step 7: `app/main_window.py` — WAV 读取（打开项目时）

**目标方法:** `_on_open_project()` (当前 line 1065+)

**新 helper 方法:**

```python
def _load_audio_from_wavs(self, project: Project, project_dir: str) -> dict | None:
    """从项目目录加载 WAV 音频，返回兼容 _recorded_data["audio"] 的结构。"""
    import wave
    mic_path = project.source.audio_mic if project.source else ""
    sys_path = project.source.audio_system if project.source else ""
    mic_data, sys_data = None, None
    sr = 44100

    def _read_wav(rel_path):
        if not rel_path:
            return None, sr
        abs_path = os.path.join(project_dir, rel_path)
        if not os.path.exists(abs_path):
            return None, sr
        with wave.open(abs_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            if wf.getnchannels() == 2:
                data = data.reshape(-1, 2)
            return data, wf.getframerate()

    mic_data, sr = _read_wav(mic_path)
    sys_data, _ = _read_wav(sys_path)

    if mic_data is not None or sys_data is not None:
        mixed = mix_audio_results(mic_data, sys_data) if (mic_data is not None and sys_data is not None) else (mic_data or sys_data)
        return {
            "mic": mic_data,
            "system": sys_data,
            "mixed": mixed,
            "samplerate": sr,
        }
    return None
```

**集成到 `_on_open_project()`:**

在 `self._recorded_data = None` 之后：
```python
# 恢复音频数据
audio_info = self._load_audio_from_wavs(project, project_dir)
if audio_info:
    self._recorded_data = {
        "audio": audio_info,
    }
```

---

#### Step 8: `app/main_window.py` — `_on_export` 空值安全修复

**目标方法:** `_on_export()` (line 876-946)

**改动:** 替换 line 920 `audio = self._recorded_data.get("audio")` 为安全版本，同时支持从 `SourceInfo` WAV 路径加载：

```python
# Line 920-923 替换为:
audio_data = None
if self._recorded_data and self._recorded_data.get("audio"):
    audio_info = self._recorded_data["audio"]
    audio_data = audio_info.get("mixed") or audio_info.get("mic") or audio_info.get("system")
elif self._project and self._project.source:
    # 从持久化的 WAV 路径加载
    audio_info = self._load_audio_from_wavs(self._project, self._current_project_path)
    if audio_info:
        audio_data = audio_info.get("mixed") or audio_info.get("mic") or audio_info.get("system")
        settings.samplerate = audio_info.get("samplerate", 44100)
```

---

### 🔵 REFACTOR — 无行为变更的重构

#### Step 9: 提取 WAV 工具函数

**文件:** `core/project.py`  
**新增 module-level helper:**

```python
def write_audio_wav(data: np.ndarray, path: str, samplerate: int) -> None:
    """将 numpy 音频数组写入 WAV 文件。"""
    import wave
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2 if data.ndim > 1 else 1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        int16 = (data * 32767).clip(-32768, 32767).astype(np.int16)
        wf.writeframes(int16.tobytes())

def read_audio_wav(path: str) -> tuple[np.ndarray, int]:
    """从 WAV 文件读取 numpy 音频数组和采样率。"""
    import wave
    with wave.open(path, "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if wf.getnchannels() == 2:
            data = data.reshape(-1, 2)
        return data, wf.getframerate()
```

MainWindow 中的 inline WAV 读写改为调用上述函数。

---

## 5. 接口/契约

### SourceInfo 字段契约

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `audio_mic` | `str` | 项目内相对路径或 `""` | 如 `"audio_mic.wav"` |
| `audio_system` | `str` | 项目内相对路径或 `""` | 如 `"audio_system.wav"` |

**不新增字段** — 复用已有 `SourceInfo.audio_mic` / `audio_system`。

### WAV 文件格式

| 属性 | 值 |
|------|-----|
| 编码 | PCM 16-bit signed integer |
| 声道 | 2（立体声）|
| 采样率 | 录制时音频设备的采样率（通常 44100 Hz）|
| 文件名 | `audio_mic.wav` / `audio_system.wav` |
| 位置 | 项目目录根 |
| 混音 | **不持久化**，播放/导出时动态混音 |

---

## 6. 数据模型变化

### Project JSON schema 变化

**无新增字段。** `source.audio_mic` / `source.audio_system` 字段已存在于 schema。唯一变化是从空字符串变为有效相对路径。

### 项目目录结构变化

```text
<project_dir>/
├── project.json          # source.audio_mic/audio_system 非空
├── frames.data
├── frames.idx
├── audio_mic.wav          # ← 新增
├── audio_system.wav       # ← 新增
└── thumbnail.png
```

---

## 7. 测试指引

### 单元测试 (test_project.py)

```python
def test_write_and_read_audio_wav_roundtrip(tmp_path):
    """写入 WAV → 读回 numpy → 验证数据一致。"""
    data = np.random.randn(44100, 2).astype(np.float32) * 0.1
    wav_path = str(tmp_path / "test.wav")
    write_audio_wav(data, wav_path, 44100)
    loaded, sr = read_audio_wav(wav_path)
    assert sr == 44100
    assert loaded.shape == data.shape
    np.testing.assert_allclose(loaded, data, atol=1e-3)
```

### 集成测试 (test_main_window.py)

```python
class TestAudioPersistence:
    def test_recording_produces_wav_files(self, qtbot, tmp_projects_dir):
        """录制 → 停止 → 项目目录含 audio_mic.wav + audio_system.wav"""
        
    def test_project_json_contains_audio_paths(self, qtbot, tmp_projects_dir):
        """project.json 中 source.audio_mic = "audio_mic.wav" """
        
    def test_reopen_project_restores_audio(self, qtbot, tmp_projects_dir):
        """保存 → 重新打开 → _recorded_data["audio"] 非 None"""
        
    def test_export_from_reopened_project_has_audio(self, qtbot, tmp_projects_dir):
        """打开项目 → 导出 → 不崩溃且有音轨"""
        
    def test_mic_only_or_system_only_recording(self, qtbot):
        """只有麦克风或只有系统音频时各自正确写入"""
        
    def test_no_audio_recording_has_empty_paths(self, qtbot):
        """无音频录制时 audio_mic/audio_system 为空字符串"""
```

### 测试 (test_exporter.py)

```python
def test_export_uses_wav_from_source_info_not_recorded_data():
    """导出时 _recorded_data is None 时从 SourceInfo WAV 路径加载音频"""
```

---

## 8. 验收标准

- [ ] 录制含麦克风 + 系统音频 → 项目目录含 `audio_mic.wav` + `audio_system.wav`
- [ ] `project.json` 中 `source.audio_mic` / `source.audio_system` 为有效相对路径
- [ ] 保存 → 重启 → 打开项目 → 时间线播放有音频
- [ ] 保存 → 重启 → 打开项目 → 导出 MP4 有音轨
- [ ] 仅麦克风/仅系统音频录制 → 对应 WAV 写入、另一字段为 `""`
- [ ] 无音频录制 → `audio_mic`/`audio_system` 均为 `""`
- [ ] `pytest tests/test_main_window.py -q -k "audio"` 全部通过
- [ ] `pytest tests/test_recorder.py -q` 全部通过
- [ ] `pytest tests/test_exporter.py -q -k "audio"` 全部通过
- [ ] 全量 `pytest -q` 0 failed

---

## 9. 边界情况与风险

| 边界/风险 | 处理策略 |
|-----------|---------|
| 录制时仅一个音频源可用 | 只写入有数据的 WAV，另一个字段保持 `""` |
| 音频 numpy 数组为 None 或空 | `_write_wav` 在 `len(data)==0` 或 `data is None` 时跳过，不创建空 WAV |
| WAV 文件过大（10min ≈ 100MB） | 桌面场景可接受；未来可考虑 FLAC 压缩（Out-of-Scope） |
| 音频采样率不一致 | 使用录制时实际采样率，不做重采样 |
| 旧项目 `audio_mic`/`audio_system` 为空 | `_load_audio_from_wavs` 优雅处理空路径，不报错 |
| P1 阶段迁移到 ProjectSession | T07 的 WAV 读写将从 MainWindow 迁移到 `ProjectSession.save_audio()`/`load_audio()`，需保持参数签名兼容 |

---

## 10. 任务级验证命令

```bash
# Step 1-3 (Red): 确认新增测试失败
pytest tests/test_main_window.py -q -k "audio"  # 预期 FAIL
pytest tests/test_recorder.py -q -k "audio"      # 预期 FAIL

# Step 4-8 (Green): 实现后验证
pytest tests/test_main_window.py -q -k "audio"
pytest tests/test_recorder.py -q
pytest tests/test_exporter.py -q -k "audio"

# Step 9 (Refactor): 全量回归
pytest tests/ -q

# 手动验收
python main.py  # 录制 → 保存 → 重启 → 打开 → 导出 → 检查音轨
```

---

## 11. TDD 切片汇总

| 切片 | 步骤 | 验证 |
|------|------|------|
| 🔴 Red | Step 1-3 编写失败测试 | `pytest -q -k "audio"` → FAIL |
| 🟢 Green | Step 4-8 最小实现 | `pytest -q -k "audio"` → PASS |
| 🔵 Refactor | Step 9 提取 WAV helpers | `pytest -q` → 0 failed |

---

*本文档由 @architect 基于技术方案 v1.0、任务图、ADR-007 和现有代码 `core/project.py:169-170`, `app/main_window.py:519-548,920` 编写。*
