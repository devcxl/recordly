---
name: "project-model-fields"
depends_on: []
labels: ["backend"]
worktree_root: ".worktree/project-model-fields/"
---

## 目标

在 `core/project.py` 的 `Project` 类中新增 4 个字段：`name`、`modified_at`、`duration`、`thumbnail_path`。

## 实现要点

1. 在 `Project.__init__()` 中初始化新字段，设默认值
2. 在 `Project.save()` 中序列化新字段
3. 在 `Project.load()` 中反序列化新字段，用 `data.get()` 兜底兼容旧文件
4. 更新 `tests/test_project.py` 添加字段序列化/反序列化测试

## 验收标准

- `save()` → `load()` 往返后新字段值正确保留
- 加载旧版 JSON（无新字段）不报错，默认值生效
- 所有现有测试通过

## Worktree
- 路径: `.worktree/project-model-fields/`
- 分支: `feat/project-model-fields`
- 创建时机: `/code` 阶段首次执行时自动创建
- 清理时机: PR 合并后自动删除