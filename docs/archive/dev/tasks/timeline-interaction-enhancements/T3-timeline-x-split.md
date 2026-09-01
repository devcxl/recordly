---
name: "T3: Timeline X 播放头切割"
depends_on: ["T1: AddClipCommand 命令基础", "T2: MainWindow Space 播放快捷键"]
labels: ["enhancement", "ready-for-agent"]
worktree_root: ".worktree/timeline-x-split/"
issue: 82
---

## 目标

Timeline 获得焦点时，X 自动查找播放头严格落在内部的首个视频 Clip，复用现有切割命令；无目标时通过 MainWindow 状态栏给出非阻塞提示。

## TDD 红绿步骤

### Red

先补充失败测试：

1. `tests/test_timeline.py`：未选中 Clip 时，`Qt.NoModifier + X` 切割播放头下视频 Clip。
2. 覆盖轨道顺序/Clip 顺序确定性、仅音频覆盖、播放头等于 start/end、无目标、组合修饰键。
3. 验证 source 范围、undo/redo 与 S 路径一致；无目标时命令栈和选择不变，仅发固定状态文案。
4. `tests/test_main_window.py`：`status_message` 到 `update_status()` 的连接重复调用后仍只有一次。

### Green

- `ui/timeline.py` 新增 `status_message(str)`。
- 增加私有查询方法，按轨道和 Clip 列表顺序匹配 `track.type == clip.type == "video"` 且 `start < playhead < end`。
- `keyPressEvent()` 只处理无修饰键 X；命中后调用 `_split_clip()`，未命中发 `播放头下无视频片段`。
- `app/main_window.py::_connect_timeline_signals()` 幂等连接状态信号到 `update_status()`。

## 精确实现范围

- 修改：`ui/timeline.py`
- 修改：`app/main_window.py`
- 修改：`tests/test_timeline.py`
- 修改：`tests/test_main_window.py`
- 不修改：`core/commands.py` 中的 `SplitClipCommand`
- 不实现音频切割、多选切割或 MainWindow 全局 X 快捷键。

## 验收标准

- [ ] X 无需预先选择 Clip，且只在 Timeline 焦点内生效。
- [ ] 只切割视频轨道，边缘不产生零宽片段。
- [ ] 多目标时选择规则确定且可测试。
- [ ] 无目标提示准确，模型、选择和 undo 栈均不变化。
- [ ] 切割后的 source 映射及 undo/redo 正确。

## 验证命令

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py -k "x_key or playhead_video"
QT_QPA_PLATFORM=offscreen pytest -q tests/test_main_window.py -k "timeline_signal"
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py tests/test_main_window.py
git diff --check
```

## Worktree

- 路径：`.worktree/timeline-x-split/`
- 分支：`feat/timeline-x-split`
- 基线：#80、#81 的实现 PR 均合入后的 `master`

## 对应 PR

PR body 必须包含：

```text
Closes #82
```
