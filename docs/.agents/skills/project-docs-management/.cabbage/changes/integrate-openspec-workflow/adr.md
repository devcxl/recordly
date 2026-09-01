---
change: integrate-openspec-workflow
cabbage_stage: adr
change_type: feature
---

# Status

Accepted (2025-09-01) - Antigravity & Maintainers

# Context

随着项目文档演进，原有的 `complete` 命令常被用户误解为完成整个 Change；同时系统缺乏将局部变更增量自动汇聚到全局文档库的管道，导致长期维护时容易出现规范脱节。

# Decision Drivers

- 提升 CLI 命令语义的直观性与精确性。
- 降低维护全局当前状态文档（`docs/`）的人工心智负担。
- 融入 OpenSpec 的结构化场景范式（Given/When/Then）。

# Considered Options

| Option | Benefits | Drawbacks | Outcome |
|---|---|---|---|
| 保留 complete 兼职模式 | 兼容历史脚本 | 语义模糊，依然容易引起误解 | Rejected |
| 彻底替换为 verify 并增加自动 sync 沉淀 | 概念清晰、统一，自动化沉淀系统真理 | 需一次性调整已有调用 | Accepted |

# Decision

1. 废除 `cabbage complete`，统一采用 `cabbage verify <change> <stage>`。
2. 引入 `sync_change_to_docs` 并在 `archive` 门禁后自动执行全局文档同步。
3. 规范模板全面支持 Requirements & Scenarios 格式。

# Consequences

## Positive

- CLI 验收流程语义明确，与开发者的认知模型完全吻合。
- 变更归档时自动沉淀文档，保证全局 `docs/` 始终与代码演进同步。

## Negative

- 外部遗留脚本需将 `complete` 统一迁移至 `verify`。

## Risks

- 无重大架构风险。

# Validation

通过 `python3 -m unittest discover tests` 验证所有命令流转与自动同步断言。
