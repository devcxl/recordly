## Parent
Part of #27

## 任务信息
- **Task ID:** T06
- **Slug:** project-atomic-save
- **类型:** fix
- **Batch:** B2

## 依赖
depends-on: #31

## 描述
实现 `Project.save()` 原子写入，防止进程中断或磁盘写失败损坏唯一项目元数据。

方案：使用 `tempfile.mkstemp` 创建同目录临时文件，写入完整 JSON 后 `os.replace` 原子替换。写入失败时原 `project.json` 不受影响。

```python
fd, tmp_path = tempfile.mkstemp(dir=project_dir, prefix=".project-", suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, target_path)
except Exception:
    try: os.unlink(tmp_path)
    except OSError: pass
    raise
```

## 验收标准
- [ ] `Project.save()` 使用临时文件 + `os.replace` 原子替换
- [ ] 写入过程中模拟磁盘满/权限错误 → 原 `project.json` 内容不变
- [ ] `pytest tests/test_project.py -q` 全部通过
- [ ] 新增测试：原子保存成功、写入中途失败后原文件可读
- [ ] 项目目录中不残留 `.project-*.tmp` 文件（正常流程和异常流程）

## 输出文件
- `core/project.py` — `Project.save()` 原子写入实现
- `tests/test_project.py` — 新增原子保存测试

## 需求追踪
- F14（项目元数据原子保存）
- US-2（项目持久化与重新打开）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
