---
id: T3
title: "MainWindow playhead_seek_play 信号集成 — 连接 + seek+play 槽函数"
depends_on: ["T2"]
estimated_effort: "2h"
assignee_type: "backend"
issue: "https://github.com/devcxl/recordly/issues/99"
---

## 目标

在 `MainWindow` 中连接 `TimelineWidget.playhead_seek_play` 信号，实现"双击空白区域 → Seek + 自动播放"的完整链路。

## 前提依赖

- T2 已完成：`TimelineWidget` 已有 `playhead_seek_play = pyqtSignal(float)` 信号定义

## 修改范围

**文件：** `app/main_window.py`

### 1. 信号连接（`_connect_timeline_signals`，L720-735）

在 `pairs` 元组中添加：

```python
(self._timeline.playhead_seek_play, self._on_playhead_seek_play),
```

插入位置：在 `(self._timeline.status_message, self.update_status),` 之前。

### 2. 新增槽函数 `_on_playhead_seek_play`

在 `_on_timeline_seek` 方法之后（约 L917 后）添加：

```python
def _on_playhead_seek_play(self, time_s: float):
    """双击空白区域 → Seek + Play"""

    # ── 焦点排除（与 _on_space_shortcut 保持同步）──
    if QApplication.activeWindow() is not self:
        return
    if QApplication.activeModalWidget() is not None:
        return
    if QApplication.activePopupWidget() is not None:
        return
    if isinstance(QApplication.focusWidget(), (
        QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
    )):
        return

    # ── 无帧时静默忽略 ──
    if not self._compositor.frames:
        return

    # ── Seek ──
    if self._playback:
        idx = int(time_s * self._compositor.fps)
        self._playback.seek(idx)
        self._update_frame_counter(idx)

    # ── 确保播放状态 ──
    if not self._playback:
        self._create_playback_controller()
        idx = int(time_s * self._compositor.fps)
        self._playback.play(idx)
    elif self._playback.is_paused:
        self._playback.pause()   # resume from pause
    elif not self._playback._playing:
        self._playback.play(self._playback.current_frame)

    self._btn_play.setText("⏸")
    self._btn_play.setToolTip("暂停")
```

**播放状态处理矩阵：**

| 当前播放状态 | 行为 |
|-------------|------|
| `_playback` 不存在 | 创建 → seek → play |
| 暂停 (`is_paused`) | seek → 恢复播放 |
| 停止 (`not _playing`) | seek → play |
| 正在播放 | seek（保持播放，不改变状态） |

### 3. 新增测试

**文件：** `tests/test_main_window.py`（若无则创建，或写到现有测试文件中）

| 测试用例 | 验证点 |
|----------|--------|
| `test_playhead_seek_play_emits_complete_chain` | 模拟双击 → 验证信号连接触发槽函数 |
| `test_playhead_seek_play_without_frames` | 无帧时不创建 playback，不崩溃 |
| `test_playhead_seek_play_without_playback_creates_and_plays` | 无 playback 时自动创建并播放 |
| `test_playhead_seek_play_resumes_from_pause` | pause 状态时 resume |
| `test_playhead_seek_play_focus_exclusion` | 焦点在输入框时不触发播放 |

> **注意：** `MainWindow` 的测试若涉及完整的 Qt 事件循环，需使用 `qapp` fixture（已在 `conftest.py` 中定义）。

## 焦点排除同步说明

本方法的守卫条件（activeWindow/modalWidget/popupWidget/focusWidget 检查）与 `_on_space_shortcut`（L327-340）**完全相同**。如有修改一方，必须同步修改另一方。后续若出现第三处相同检查，应抽取为公共方法 `_is_playback_shortcut_allowed()`。

## 边界条件

| 场景 | 预期行为 |
|------|----------|
| 焦点在输入框 | 不触发播放 |
| 有模态弹窗 | 不触发播放 |
| `frames` 为空 | 静默忽略 |
| 已有 `_playback` 且正在播放 | seek 到新位置，继续播放 |
| `_playback` 存在但已停止 | seek + play |
| 播放按钮状态 | 永远设为 "⏸"（对应播放中/暂停中状态） |

## 参考

- 技术方案：`docs/dev/specs/recordly-playhead-click-behavior.md` §3.4
- ADR：`docs/adr/2026-07-19-playhead-click-behavior.md` 决策 3
