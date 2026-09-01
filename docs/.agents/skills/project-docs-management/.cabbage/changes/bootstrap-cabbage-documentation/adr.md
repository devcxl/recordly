---
change: bootstrap-cabbage-documentation
cabbage_stage: adr
change_type: feature
---

# Status

Accepted，决定日期：2026-08-29，负责人：项目维护者。

# Context

项目以 Cabbage 提供可执行的文档工作流门禁，却没有使用该能力治理自身文档。这使项目的产品定位、架构、测试和发布知识主要散落在 README、Skill 说明和实现中，也无法通过真实项目检验初始化、阶段状态、当前状态文档及 CI 的协作。方案必须复用现有 CLI 和模板，不引入新架构，同时接受当前 `.git` 无效造成的集成验证限制。

# Decision Drivers

- 能否以真实 change 验证项目自身的核心工作流。
- 能否区分变更过程文档与项目当前状态文档。
- 能否在不修改 CLI 功能的前提下落地。
- 是否提供可自动执行的测试和文档构建路径。
- 后续维护成本是否与项目规模相称。

# Considered Options

| Option | Benefits | Drawbacks | Outcome |
|---|---|---|---|
| 保持现状 | 无新增文件或维护流程 | 项目不能自证其文档治理价值，知识继续分散 | 拒绝 |
| 只初始化目录 | 成本低，可获得标准骨架 | 缺少真实阶段内容和当前状态资料，无法覆盖完整门禁 | 拒绝 |
| 使用 Cabbage 完整自举 | 复用现有工具，形成变更记录、现状资料和 CI 闭环 | 初次文档量较大，Git 与 pnpm 环境影响部分验证 | 选择 |
| 引入另一套外部文档治理工具 | 可能获得额外协作能力 | 增加依赖并削弱项目自身工具的验证意义 | 拒绝 |

# Decision

选择使用 Cabbage 完整自举：在仓库内维护 `.cabbage/` 配置、工作流、工具副本和 change 记录，以 `docs/` 保存当前状态资料，并通过 `.github/workflows/cabbage.yml` 定义自动化门禁。决定仅涉及项目文档治理方式，不改变 CLI 行为，不修复 Git 元数据，也不代替远程仓库的分支保护配置。

# Consequences

## Positive

- 项目对外倡导的文档工作流在自身仓库得到真实使用和持续验证。
- 需求、架构、测试和发布决策能够追溯到具体 change。
- 当前状态文档拥有稳定入口，并可根据影响矩阵自动检查。
- 本地门禁、Python 测试和 VuePress 构建形成可复现的验证链路。

## Negative

- 每次重要变更需要维护阶段文档和对应当前状态资料。
- 仓库新增 `.cabbage/`、`docs/` 和 CI 文件，评审范围扩大。
- 文档站点构建依赖 pnpm，Git 相关校验依赖有效仓库元数据。

## Risks

- 文档可能被形式化填写但语义失真；通过人工评审和验收标准降低风险。
- 当前无法验证 `cabbage ci --base` 与分支保护；恢复有效 Git 后必须补跑检查并配置必需状态检查。
- 自举配置可能随 CLI 演进而陈旧；后续 CLI 行为变更必须同步维护本项目配置和文档。

# Validation

本变更完成前检查 `.cabbage/`、`docs/` 和 CI 文件齐备，执行 `cabbage validate`、implementation/merge gate、`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`，并在 pnpm 依赖可用时执行文档构建。有效 Git 仓库恢复后补验 `cabbage ci --base` 和分支保护。若连续变更无法通过该流程或维护成本明显高于治理收益，则由项目维护者重新评审本决定。
