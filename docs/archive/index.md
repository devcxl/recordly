# 归档区

本目录保存已完成变更的历史工作记录。归档内容为**不可变历史**：不回头改写、不删除；新事实通过当前状态文档或新的决策记录表达。

## 结构

| 目录 | 内容 |
|---|---|
| [`archive/design/`](design/index.md) | 已完成变更的任务图（Task DAG），如核心稳定性、数据持久化、交互重构 |
| [`archive/dev/`](dev/index.md) | 开发工作记录：任务分解（`tasks/`）、交接文档（`handoff/`）、开发笔记 |
| [`archive/review/`](review/index.md) | 里程碑评审报告与代码审查记录（事件型记录，包含审查对象版本） |
| [`archive/task/`](task/index.md) | 核心稳定性任务清单（T01–T17）与录制往返链路修复任务 |

## 与变更工作区的关系

- `archive/` 与 `.cabbage/changes/` 不同：前者是长期保留的项目文档，后者是变更工作区元数据。
- 本归档区由人工采纳迁移建立；后续变更的产物将通过 `cabbage archive` 自动归档。

## 参考

- 迁移说明与初始分类清单见 `00-overview/index.md` 与迁移报告。