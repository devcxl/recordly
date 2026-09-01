---
change: bootstrap-cabbage-documentation
cabbage_stage: requirement
change_type: feature
---

# Goal

本项目当前提供文档治理工具，但项目自身尚未采用同一套工作流管理需求、设计、测试和发布资料。此次变更将 Cabbage 应用于自身仓库，建立可验证、可持续演进的文档基线，使后续项目变更也必须经过项目对外倡导的文档门禁。

# Users and Use Cases

| User or actor | Need | Primary use case |
|---|---|---|
| 项目维护者 | 统一维护项目现状文档和变更记录 | 通过 `cabbage new`、`complete`、`gate` 和 `validate` 管理一次变更的完整生命周期 |
| 开发 Agent | 在实现前获得明确需求、设计和测试约束 | 读取 `.cabbage/changes/` 中的阶段文档，满足实现门禁后再修改代码 |
| 代码审查者 | 获得可追溯且能够自动校验的评审材料 | 在合并前检查变更文档、当前状态文档及 CI 门禁结果 |

# Scope

## In Scope

- 初始化 `.cabbage/` 配置、工作流定义和项目内工具副本。
- 初始化 `docs/` VuePress 文档站点骨架并补充项目当前状态文档。
- 生成 `.github/workflows/cabbage.yml`，将文档校验和构建纳入 CI。
- 使用 `bootstrap-cabbage-documentation` 变更记录本次自举过程，并完成适用的阶段文档。
- 验证本地 Cabbage 门禁、Python 测试和文档构建路径。

## Out of Scope

- 不修改 Cabbage CLI 的业务功能、命令接口或模板格式。
- 不新增 API、数据库、数据处理、安全、运维或性能能力。
- 不在本次变更中修复当前无效的 `.git` 元数据。
- 不在 Git 托管平台配置分支保护；该配置需在仓库 Git 状态恢复并推送后进行。

# Requirements

| ID | Requirement | Priority | Rationale |
|---|---|---|---|
| R-1 | 仓库必须包含可被 CLI 识别的 `.cabbage/config.yaml` 和工作流定义 | Must | 保证项目能够使用自身命令执行阶段管理和门禁校验 |
| R-2 | 仓库必须包含 `docs/` 文档站点骨架和产品、架构、测试、CI/CD、发布等当前状态文档 | Must | 为读者提供与变更记录分离的现状入口 |
| R-3 | 仓库必须包含 Cabbage GitHub Actions 工作流 | Must | 为恢复有效 Git 仓库后的自动化文档门禁提供基础 |
| R-4 | 自举变更必须声明 `product`、`architecture`、`testing`、`deployment` 为有影响，其余影响项为无影响 | Must | 激活与实际变更范围一致的阶段和当前状态文档要求 |
| R-5 | Python 回归测试必须能通过指定命令执行，文档站点必须使用 pnpm 构建 | Must | 固化可复现的代码和文档验证方式 |
| R-6 | 必须明确记录无效 `.git` 导致 `cabbage ci --base` 和分支保护暂不可验证 | Must | 防止将未执行的外部集成检查误报为已通过 |

# Acceptance Criteria

- [ ] 给定项目根目录，检查时能够找到 `.cabbage/`、`docs/` 和 `.github/workflows/cabbage.yml`。
- [ ] 给定自举变更，执行 `cabbage validate bootstrap-cabbage-documentation` 时不存在结构、标题或占位内容错误。
- [ ] 给定已完成的实现前阶段，执行 `cabbage gate bootstrap-cabbage-documentation implementation` 时门禁通过。
- [ ] 执行 `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` 时全部测试通过。
- [ ] 在已安装 pnpm 依赖的环境中执行 `cabbage docs build` 时 VuePress 站点成功生成。
- [ ] 验证报告明确说明当前 `.git` 无效，因此没有宣称 `cabbage ci --base` 或分支保护已通过验证。

# Success Metrics

| Metric | Baseline | Target | Measurement window |
|---|---|---|---|
| 自举所需基础目录与 CI 文件覆盖率 | 0% | 100% | 本变更合并前 |
| 激活阶段文档的未处理占位数 | 模板初始状态存在多个 | 0 | 每次阶段完成及合并前 |
| Python 回归测试通过率 | 以执行结果为准 | 100% | 本变更完成验证时 |
| 必需当前状态文档覆盖率 | 0% | 100% | 合并门禁执行前 |

# Dependencies and Constraints

- 文档站点依赖 pnpm 安装依赖并执行 VuePress 构建。
- Python 验证环境必须能够从项目根目录导入 `cabbage_cli`。
- 当前 `.git` 不是有效 Git 仓库，依赖 Git diff 的 `cabbage ci --base` 暂不可执行，分支保护也无法配置或验证。
- 现有 CLI 契约、英文标题和 frontmatter 必须保持不变。

# Risks

| Risk | Impact | Mitigation |
|---|---|---|
| 文档与实现后续不同步 | 自举只形成一次性材料，无法持续提供治理价值 | 将 Cabbage 门禁纳入日常变更流程，并由 CI 检查当前状态文档 |
| 无效 Git 元数据掩盖 CI 集成问题 | 基于 diff 的检查和分支保护可能在恢复 Git 后暴露问题 | 明确记录限制，恢复 Git 后补跑 `cabbage ci --base` 并配置必需状态检查 |
| pnpm 依赖不可用 | 无法验证 VuePress 生产构建 | 在具备 pnpm 和依赖缓存或网络访问的环境中执行构建并保存结果 |

# Open Questions

- N/A：本次自举范围和验证边界已经确定；Git 集成验证属于环境恢复后的明确后续动作，不是待决设计问题。
