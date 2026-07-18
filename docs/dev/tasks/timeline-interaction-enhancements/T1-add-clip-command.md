---
name: "T1: AddClipCommand 命令基础"
depends_on: []
labels: ["enhancement", "ready-for-agent"]
worktree_root: ".worktree/timeline-add-clip-command/"
issue: 80
---

## 目标

在纯数据命令层新增通用 `AddClipCommand`，支持固定索引插入、撤销删除和完整数据重做，为后续缩放块创建提供统一命令栈基础。

## TDD 红绿步骤

### Red

在 `tests/test_timeline.py::TestTimelineCommands` 先增加失败测试：

1. 首次 `execute()` 未指定索引时追加 Clip，并记录实际索引。
2. 指定 `clip_index` 时在固定位置插入。
3. `undo()` 删除同一索引；删除前把已修改的 `rect` 等字段回写到 `clip_data`。
4. 再次 `execute()` 恢复相同 `id`、`rect`、`transition_duration` 和索引。

确认失败原因为 `AddClipCommand` 尚不存在，而非 fixture 或环境错误。

### Green

在 `core/commands.py` 增加最小 dataclass：

- 字段：`track_index`、`clip_data`、`clip_index: int | None = None`。
- 首次执行时仅在索引为空时取轨道尾部索引，始终从 `clip_data` 重建 `Clip`。
- 撤销时先用当前 Clip 的 `asdict()` 刷新 `clip_data`，再删除该索引。
- 依赖现有 LIFO undo 栈，不增加额外 ID 查询或容错层。

目标测试通过后运行 `tests/test_timeline.py` 回归。

## 精确实现范围

- 修改：`core/commands.py`
- 修改：`tests/test_timeline.py`
- 不修改：`ui/timeline.py`、`app/main_window.py`、`core/project.py`
- 不新增模型、schema、Qt 依赖或命令注册表。

## 验收标准

- [ ] `AddClipCommand` 继承 `UndoCommand`。
- [ ] append 和固定索引插入均正确。
- [ ] undo/redo 后 Clip 的完整序列化字段保持一致。
- [ ] undo 前对 Clip 的矩形修改可在 redo 后恢复。
- [ ] 既有 Move/Delete/Split/Composite 命令测试不回归。

## 验证命令

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py -k "add_clip_command"
QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py
git diff --check
```

## Worktree

- 路径：`.worktree/timeline-add-clip-command/`
- 分支：`feat/timeline-add-clip-command`
- 基线：Planning PR 合入后的 `master`

## 对应 PR

PR body 必须包含：

```text
Closes #80
```
