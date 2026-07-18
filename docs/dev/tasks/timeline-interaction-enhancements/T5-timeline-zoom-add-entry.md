---
name: "T5: Timeline 缩放块创建入口"
depends_on: ["T1: AddClipCommand 命令基础", "T4: Timeline 视频片段吸附与对齐线"]
labels: ["enhancement", "ready-for-agent"]
worktree_root: ".worktree/timeline-zoom-add-entry/"
issue: 84
---

## 目标

在缩放轨道空白内容区提供右键“添加缩放块”入口，并由 Timeline 提供基于 `AddClipCommand` 的统一 Clip 添加方法。

## TDD 红绿步骤

### Red

在 `tests/test_timeline.py` 先增加失败测试：

1. 仅 zoom Track、header 右侧、未命中 Clip 时，构造的菜单包含“添加缩放块”。
2. video/audio Track、header、已有 Clip 位置不包含该动作。
3. 触发动作时发出 `zoom_add_requested(float)`，时间由 x 转换并限制在 `[0, duration]`。
4. `add_clip()` 将命令推入 undo 栈，返回实际插入对象并设为当前选择；undo/redo 恢复完整字段。
5. 现有双击空白、双击已有 zoom Clip、单击选中测试继续通过。

### Green

- 新增 `zoom_add_requested(float)` 信号。
- 将菜单构造提取为不执行 `exec_()` 的私有方法，便于测试；`_show_context_menu()` 只负责展示。
- 根据 y 定位 Track 行，根据 x 排除 header，根据 `_hit_test()` 排除已有 Clip。
- 新增 `add_clip(track_index, clip) -> Clip`：从输入 Clip 序列化命令数据，经 `_push_undo()` 执行，选择并返回实际插入对象。
- 不在 Timeline 构造默认缩放矩形或持有 compositor。

## 精确实现范围

- 修改：`ui/timeline.py`
- 修改：`tests/test_timeline.py`
- 不修改：`app/main_window.py`、`ui/preview_widget.py`、`core/project.py`
- 保留 `zoom_double_clicked(float, object)` 及现有双击行为。

## 验收标准

- [ ] 右键动作命中规则完整且菜单测试不调用阻塞式 `exec_()`。
- [ ] 请求时间与点击位置一致并正确 clamp。
- [ ] `add_clip()` 复用 AddClipCommand 和 `_push_undo()`。
- [ ] 新 Clip 自动选中，创建可撤销/重做。
- [ ] 现有 zoom 交互不回归。

## 验证命令

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py -k "zoom and (context or add or double or selected)"
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py
git diff --check
```

## Worktree

- 路径：`.worktree/timeline-zoom-add-entry/`
- 分支：`feat/timeline-zoom-add-entry`
- 基线：#80、#83 的实现 PR 均合入后的 `master`

## 对应 PR

PR body 必须包含：

```text
Closes #84
```
