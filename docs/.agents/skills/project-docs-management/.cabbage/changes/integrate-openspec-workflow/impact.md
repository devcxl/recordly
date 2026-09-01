---
change: integrate-openspec-workflow
cabbage_stage: impact
change_type: feature
---

# Change Summary

在 Cabbage 核心工具与工作流中融入 OpenSpec 的 Spec-Driven 思想，全面将阶段验收动词升级为 `verify`，并新增 `sync` 命令和归档自动同步，影响产品规范模型、CLI 接口定义、架构设计与测试覆盖。

# Impact Matrix

| Area | Impact | Notes |
|---|---|---|
| Product | Yes | 规范化 Requirements & Scenarios 结构 |
| Architecture | Yes | 引入规范自动映射与同步架构机制 |
| API | Yes | CLI 命令接口重构（替换 complete 为 verify，新增 sync） |
| Database | No | 无数据库变更 |
| Security | No | 沿用现有文件系统与哈希签名安全边界 |
| Testing | Yes | 覆盖 verify、sync、archive 自动同步的全流程单测 |
| Deployment | No | 无需部署流水线调整 |
| Operations | No | 无生产运行变更 |
| Data | No | 无数据迁移 |
| Performance | No | 本地文件解析与合并，无性能影响 |

# Impact Details

- **Product**: 需求模板与设计指南全面采纳结构化规范与场景范式。
- **Architecture**: 在 `core.py` 增加 `STAGE_DOCS_MAPPING` 与 `sync_change_to_docs` 规范沉淀逻辑，连接变更工作区与 `docs/` 全局文档。
- **API**: CLI 子命令变更，`cabbage verify <change> <stage>` 替代原有命令，新增 `cabbage sync <change>`。
- **Testing**: 更新 `tests/test_cabbage.py` 等测试集，补充针对新工作流的断言。

# Risks

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| 旧习惯导致命令输入错误 | Low | Low | CLI 输出明确的用法提示与帮助文档 | Agent |

# Documentation Updates

- `README.md`
- `SKILL.md`
- `references/cli.md`
- `references/lifecycle.md`
- `references/validation.md`
- `integrations/agent-contract.md`
- `docs/00-overview/README.md`
