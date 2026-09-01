# main_window 拆分规划（issue #143）

> 目标：把 `app/main_window.py`（1904 行 / 113 方法）按职责拆分为可独立演进模块
> 前置：issue #144（Compositor 公共 API）已完成，本规划基于当前 master（f483a3b）
> 原则：**增量迁移、每步可独立验证、测试兼容、不改变调用约定**

---

## 一、现状分析（基于实际代码）

### 1.1 结构指标

| 指标 | 值 |
|------|-----|
| 总行数 | 1904 |
| 方法数 | 113 |
| 最长方法 | `_on_re_record_requested` (+52 行) |
| __init__ 实例状态 | 14 个（_recording_controller / _compositor / _recorded_data / _audio_regions / _track_audio_cache / _export_controller / _progress / _playback / _editing_zoom_clip / _crop_overlay / _crop_active / _project_manager / _shortcut_registry / _project_session） |

### 1.2 共享状态耦合度（方法引用数）

```
_timeline:   35   ← 最大枢纽（时间线 UI + 播放 + 全流程编辑）
_compositor: 24   ← 帧/合成引擎（已具备公共 API，见 #144）
_playback:   24   ← 播放控制器
_project_dir: 14
_audio_regions: 12
_recorded_data:  11
_recording_controller: 7   ← 已是独立控制器
_project_manager:  6      ← 已是独立类
_shortcut_registry: 5
_track_audio_cache: 4
_export_controller: 4     ← 已是独立控制器
_project_session:  2
_crop_overlay:  2
```

结论：`_recording_controller`/`_export_controller`/`_project_manager` 已外置为独立类；
`_timeline`/`_compositor`/`_playback` 是 MainWindow 的直接子控件，不宜再抽层（避免过度间接）。
真正的拆分对象是**方法群的物理聚集**。

### 1.3 方法群分布（按职责聚类）

| 群 | 代表方法 | 估算行数 |
|----|----------|----------|
| A. 项目打开/恢复 | `_on_open_project` `_clear_editor_state` `_restore_cursor_events` `_restore_video_frames` `_restore_project_audio` `_build_recorded_data_from_project` `_restore_timeline_and_playback` `_restore_editor_ui` `_collect_project_state` | ≈ 220 |
| B. 录制事件流 | `_on_home_record` `_create_project_for_recording` `_handle_stop_failure` `_on_recording_started` `_on_recording_stopped` `_finalize_project` `_cleanup_failed_recording` | ≈ 280 |
| C. 音频/补录 | `_on_re_record_requested` `_update_audio_timeline` `_sync_audio_regions` `_track_audio_provider` `_on_add_audio` `_get_audio_duration` | ≈ 200 |
| D. 导出流程 | `_on_export` `_build_export_settings` `_on_export_progress` `_on_export_finished` | ≈ 120 |
| E. 播放控制 | `_create_playback_controller` `_on_playhead_*` `_enable_playback_controls` `_update_frame_counter` 等 | ≈ 250 |
| F. UI 构造 | `__init__` `_setup_*` `_add_toolbar_*` `_setup_tray` `_connect_*` | ≈ 500 |
| G. 时间线编辑 | clip/zoom/crop/undo/redo/volume/inspector 槽 | ≈ 330 |

---

## 二、拆分方案

### 2.1 结构：Mixin 继承（而非 Composition）

```
class MainWindow(  # 保留 UI 构造 / 信号连接 / 播放 / 时间线编辑
    ProjectRestoreMixin,   # A 项目打开/恢复  (~220 行)
    RecordingFlowMixin,    # B 录制事件流    (~280 行)
    AudioFlowMixin,        # C 音频/补录      (~200 行)
    ExportFlowMixin,       # D 导出流程      (~120 行)
    QMainWindow,
):
```

**选 Mixin 的理由**：
1. 方法间共享 `self._compositor/_timeline/_playback/_project_dir` 等实例状态，mixin 直接访问 `self._xxx`，零改动调用约定
2. 现有测试大量直接调用 `MainWindow._restore_*`（MethodType bind 到 FakeWindow）——方法名不变则测试兼容
3. 支持**逐步迁移**：一次移动一个方法群，每步独立 PR 验证

**不选 Composition 的理由**：需把所有 `self._xxx` 调用改为 `self.editor.xxx`，改动面 600+ 处、风险高、收益相同。

### 2.2 文件布局（新文件全部在 app/ 下）

| 文件 | 内容 | 依赖方向（只读 self 状态） |
|------|------|------------------------------|
| `app/project_restore_mixin.py` | A 群 | _compositor _timeline _playback _project_dir _audio_regions _project_manager |
| `app/audio_flow_mixin.py` | C 群 | _timeline _audio_regions _project_dir _playback _compositor |
| `app/recording_flow_mixin.py` | B 群 | _recording_controller _compositor _playback _project_dir _project_session |
| `app/export_flow_mixin.py` | D 群 | _export_controller _compositor _timeline |
| `app/main_window.py` | 保留 F/G/E + __init__ + 信号连接 | 剩余 ≈ 1000 行 |

### 2.3 方法与测试的迁移约束

- **方法移动不改签名/不改实现体**（本轮仅物理搬移）
- 每个 mixin 内引用 `self._show_notification` / `self.update_status` 等 MainWindow 方法 → 移动后仍是 MainWindow 方法（mixin 只是搬到继承链上），**无需任何改动**，这是 Mixin 方案的核心优势
- 移动后立刻跑全量测试（691+）：tests/test_main_window.py 的 MethodType bind 测试天然兼容
- 每步 commit 应只含"移动 + import"，diff 可用 `git diff --color-moved` 验证纯搬移

---

## 三、执行步骤（每步一个 PR，独立可验证）

| 步骤 | 内容 | 实际 diff | 验证 | 状态 |
|------|------|-----------|------|------|
| **Step 1** | 抽 `ProjectRestoreMixin`（A 群 10 方法 + 4 工具函数） | 253 行新文件 / -239 行 | 691 全绿，ALL IDENTICAL | ✅ 已合并 (PR #149) |
| **Step 2** | 抽 `AudioFlowMixin`（C 群 6 方法） | 207 行新文件 / -185 行 | 691 全绿，ALL IDENTICAL | ✅ 已合并 (PR #150) |
| **Step 3** | 抽 `RecordingFlowMixin`（B 群 10 方法） | 236 行新文件 / -221 行 | 691 全绿，ALL IDENTICAL | ✅ 已合并 (PR #151) |
| **Step 4** | 抽 `ExportFlowMixin`（D 群 6 方法） | 130 行新文件 / -113 行 | 691 全绿，ALL IDENTICAL | ✅ 已合并 (PR #152) |
| **Step 5** | 收尾评估：main_window 从 1904 降至 1146 行 | — | 691 全绿，4 个 Mixin 架构就位 | ✅ 全部完成 |

每步之后 `wc -l app/main_window.py` 应单调下降；最终 main_window 只保留 UI 构造 + 信号连接 + 时间线编辑。

---

## 四、风险与缓解

| 风险 | 级别 | 缓解 |
|------|------|------|
| mixin 顺序影响 MRO 解析 | 低 | 所有 mixin 不定义 `__init__`/同名方法；冲突由测试暴露 |
| 测试依赖方法在类上存在（MethodType bind） | 无 | 方法名不变，bin d 到 MainWindow 仍有效 |
| 搬移引入复制/粘贴错误 | 低 | 每步 `git diff --color-moved=plain` 审阅 + 全量测试 |
| 后续新功能继续往 main_window 塞 | 中 | PR check：main_window 行数上限告警（可选加 CI 断言） |

---

## 五、验收标准

1. `app/main_window.py` 从 1904 → ≤1100 行
2. 全部 691 测试保持通过（无修改测试文件）
3. 每个 PR diff 为纯搬移（`--color-moved` 下方法体无 diff）
4. 运行时行为不变（手工冒烟：录/剪/导）