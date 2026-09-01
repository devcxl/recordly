---
change: integrate-openspec-workflow
cabbage_stage: requirement
change_type: feature
---

# Goal

将 OpenSpec 的核心理念（规范即真相、结构化 Requirements & Scenarios 场景范式、变更规范自动沉淀）融入 Cabbage 项目，同时将原本存在语义歧义的 `complete` 命令彻底重构为 `verify`，并新增 `cabbage sync` 与 `archive` 自动同步机制，消除变更完成后手动复制维护全局当前状态文档的负担。

# Users and Use Cases

| User or actor | Need | Primary use case |
|---|---|---|
| AI Agent | 准确理解系统当前行为并按明确场景实施需求变更 | 读取结构化 spec，编写代码并通过 `cabbage verify` 校验阶段签名 |
| 研发人员 / 维护者 | 简化阶段验收语义，并在归档时自动沉淀文档至全局目录 | 运行 `cabbage verify <stage>` 验收，运行 `cabbage archive` 一键自动同步并归档 |

# Scope

## In Scope

- 废除 `cabbage complete`，全面升级为 `cabbage verify <change> <stage>`。
- 引入结构化需求与验收场景（Requirement SHALL/MUST + Scenario GIVEN/WHEN/THEN）。
- 新增 `cabbage sync <change>` 命令，将变更中已验证的规范自动映射并沉淀至 `docs/` 编号目录。
- 增强 `cabbage archive <change>`：归档前自动触发规范同步，确保全局系统文档始终是最新的 Source of Truth。
- 更新项目全部文档、模板与自动化测试套件。

## Out of Scope

- 废除现有 Cabbage 严格门禁体系与内容签名校验机制（保持保留与强化）。
- 更改现有 `docs/` 的编号目录分类规则（保持现有分类）。

# Requirements

| ID | Requirement (SHALL/MUST) | Priority | Rationale |
|---|---|---|---|
| R-1 | CLI SHALL 废除 `complete` 并提供 `verify <change> <stage>` 验证阶段签名与合规性。 | Must | 解决动词歧义，准确表达阶段验证与签名锁定语义。 |
| R-2 | CLI SHALL 提供 `sync <change>` 将变更工作区的文档规范自动同步至 `docs/` 对应当前状态目录。 | Must | 消除手动跨目录搬运文档的重复工作。 |
| R-3 | `cabbage archive` SHALL 在通过归档门禁后自动执行规范同步再移入 archive 目录。 | Must | 确保归档时系统全局当前状态文档实时反映最新能力。 |
| R-4 | 模板体系 SHALL 支持 Requirements & Scenarios 结构化规范格式。 | Must | 提升 AI Agent 和人工的场景化验收可信度。 |

# Acceptance Criteria

### Scenario 1: Verify Stage Execution
- **GIVEN**: 变更工作区中存在符合格式且无占位符的阶段产物
- **WHEN**: 运行 `cabbage verify integrate-openspec-workflow requirement`
- **THEN**: CLI 成功输出 `verified integrate-openspec-workflow:requirement` 并记录状态签名
- [x] 验证阶段执行正常

### Scenario 2: Sync and Archive Propagation
- **GIVEN**: 变更工作区的所有前置阶段均已验证通过
- **WHEN**: 运行 `cabbage sync` 或 `cabbage archive`
- **THEN**: 系统自动在 `docs/01-product/` 等路径生成或更新对应的当前状态文档
- [x] 自动同步与归档沉淀生效

# Success Metrics

| Metric | Baseline | Target | Measurement window |
|---|---|---|---|
| 命令语义歧义度 | 存在 `complete` 误解 | 0 歧义，全面采用 `verify` | 变更发布后 |
| 文档同步耗时 | 手动复制需数分钟且易漏 | 0 手动耗时，CLI 毫秒级自动同步 | 归档执行阶段 |

# Dependencies and Constraints

- 运行环境需保持 Python 3.10+ 与 PyYAML 6.0+。
- 必须保持既有的签名防篡改与 VuePress 兼容性。

# Risks

| Risk | Impact | Mitigation |
|---|---|---|
| 开发者习惯了旧命令 | 执行 `complete` 报错 | 更新 CLI 帮助提示、SKILL.md、README.md 与全部文档 |

# Open Questions

- N/A（无遗留未决问题）。
