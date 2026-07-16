# 时间线裁剪功能 — 任务清单

## DAG

```mermaid
graph TD
  T1["T1: MoveClipCommand 扩展 source 字段"] --> T2["T2: mouseMoveEvent 更新 source"]
  T1 --> T3["T3: _make_move_cmd 捕获 source 变更"]
  T2 --> T4["T4: mousePressEvent 捕获 drag_orig_source"]
  T5["T5: 边缘 hover 光标 (F2)"]
  T6["T6: CompositeCommand (F3)"]
  T6 --> T7["T7: trim_in/trim_out + keyPressEvent"]
  T4 --> T8["T8: 集成测试"]
  T5 --> T8
  T7 --> T8
```

## Batch 执行计划

| Batch | 任务 | 并行度 | 依赖 |
|-------|------|--------|------|
| 1 | T1, T5, T6 | 3 | 无 |
| 2 | T2, T3 | 2 | T1 |
| 3 | T4, T7 | 2 | T2, T6 |
| 4 | T8 | 1 | T4, T5, T7 |

## 文件影响范围

所有任务仅涉及两个文件：
- `core/commands.py` — T1, T6
- `ui/timeline.py` — T2, T3, T4, T5, T7, T8
