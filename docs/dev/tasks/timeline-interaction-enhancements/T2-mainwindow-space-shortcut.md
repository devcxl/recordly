---
name: "T2: MainWindow Space 播放快捷键"
depends_on: []
labels: ["enhancement", "ready-for-agent"]
worktree_root: ".worktree/mainwindow-space-shortcut/"
issue: 81
---

## 目标

在当前编辑窗口范围内用 Space 切换播放/暂停，复用 `MainWindow._on_play_toggle()`，同时保护首页、其他顶层窗口、弹窗和输入控件的按键语义。

## TDD 红绿步骤

### Red

在 `tests/test_main_window.py` 先增加失败测试：

1. 快捷键上下文为 `Qt.WindowShortcut`，auto-repeat 关闭。
2. 编辑器页且 MainWindow 活跃、无 modal/popup、非输入焦点时，只调用一次 `_on_play_toggle()`。
3. 首页、非活动窗口、active modal、active popup 时不调用。
4. `QLineEdit`、`QTextEdit`、`QPlainTextEdit`、`QAbstractSpinBox` 子类、`QComboBox` 获得焦点时不调用。

### Green

在 `app/main_window.py`：

- 由 MainWindow 持有 Space `QShortcut`，使用 `Qt.WindowShortcut` 并关闭 auto-repeat。
- 增加最小私有处理方法，按 Spec 顺序检查编辑器页、活动窗口、modal/popup、输入焦点。
- 守卫通过后只调用现有 `_on_play_toggle()`；不复制播放状态逻辑。

目标测试通过后回归既有播放测试。

## 精确实现范围

- 修改：`app/main_window.py`
- 修改：`tests/test_main_window.py`
- 不修改：`ui/timeline.py`、`ui/preview_widget.py`、`PlaybackController`
- 不引入全局 event filter 或 `Qt.ApplicationShortcut`。

## 验收标准

- [ ] Space 在编辑器预览和时间线区域均可触发播放切换。
- [ ] 所有页面、窗口、modal/popup、输入焦点守卫生效。
- [ ] 长按 Space 不连续翻转状态。
- [ ] 无帧时继续沿用 `_on_play_toggle()` 的无操作语义。
- [ ] 工具栏按钮文字、暂停和继续播放行为不回归。

## 验证命令

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_main_window.py -k "space or play"
QT_QPA_PLATFORM=offscreen pytest -q tests/test_main_window.py
git diff --check
```

## Worktree

- 路径：`.worktree/mainwindow-space-shortcut/`
- 分支：`feat/mainwindow-space-shortcut`
- 基线：Planning PR 合入后的 `master`

## 对应 PR

PR body 必须包含：

```text
Closes #81
```
