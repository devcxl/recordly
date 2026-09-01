---
name: "T6: MainWindow 缩放创建集成"
depends_on: ["T5: Timeline 缩放块创建入口"]
labels: ["enhancement", "ready-for-agent"]
worktree_root: ".worktree/mainwindow-zoom-integration/"
issue: 85
---

## 目标

将缩放轨右键请求和现有双击空白入口统一接入命令栈创建流程，创建默认 zoom Clip 后自动选中并显示现有 `ZoomOverlay`。

## TDD 红绿步骤

### Red

在 `tests/test_main_window.py` 先增加失败测试：

1. `_connect_timeline_signals()` 幂等连接 `zoom_add_requested` 到创建 handler。
2. 右键请求和双击空白均调用 Timeline `add_clip()`，不再直接 append。
3. 默认 Clip：start 为点击时间、end 为 `min(start + 2.0, duration)`、content 为 `手动缩放`、`transition_duration == 0.4`。
4. rect 位于画面中央，尺寸按 `zoom_rect_ratio`，宽高比与项目画面一致。
5. 使用 `add_clip()` 返回对象设置 `_editing_zoom_clip`，显示 Overlay 并同步 compositor。
6. undo 删除后 Overlay 隐藏；redo 恢复完整数据。既有 Clip 编辑路径不新增命令。

### Green

- 在 Timeline 信号连接表中增加 `zoom_add_requested`，保持 disconnect/connect 幂等模式。
- 重构 `_on_zoom_double_clicked()`：新建时找到 zoom Track 索引、构造默认 Clip、调用 `self._timeline.add_clip()` 并使用返回对象。
- 既有 Clip 路径只补齐空 rect，不创建 AddClipCommand。
- 继续复用现有 compositor、playback seek、`show_zoom_rect()` 和 `rect_changed` 连接逻辑。
- 继续由 `_on_clips_changed()` 在 undo 后检测编辑对象不存在并隐藏 Overlay。

## 精确实现范围

- 修改：`app/main_window.py`
- 修改：`tests/test_main_window.py`
- 只回归、不修改：`tests/test_preview_widget.py`、`ui/preview_widget.py`
- 不修改：Project schema、compositor 实现、导出管线。
- 不新增工具栏入口、关键帧、曲线或缩放倍数输入。

## 验收标准

- [ ] 右键和双击空白复用同一创建流程。
- [ ] 默认持续时间、尾部截断、矩形、文案和 transition_duration 正确。
- [ ] 新 Clip 自动选中并立即显示可编辑 Overlay。
- [ ] compositor 和 playback 预览同步。
- [ ] 创建、undo、redo 形成一个命令栈步骤并恢复完整数据。
- [ ] 双击/单击编辑已有 zoom Clip 的行为不回归。

## 验证命令

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_main_window.py -k "zoom or timeline_signal"
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py tests/test_main_window.py tests/test_preview_widget.py
QT_QPA_PLATFORM=offscreen pytest -q
git diff --check
```

## Worktree

- 路径：`.worktree/mainwindow-zoom-integration/`
- 分支：`feat/mainwindow-zoom-integration`
- 基线：#84 实现 PR 合入后的 `master`

## 对应 PR

PR body 必须包含：

```text
Closes #85
```
