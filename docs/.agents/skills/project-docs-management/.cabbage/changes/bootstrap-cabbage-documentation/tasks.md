---
change: bootstrap-cabbage-documentation
cabbage_stage: implementation
change_type: feature
---

# Preparation

- [x] 初始化前确认仓库尚未存在 `.cabbage/`、自举 `docs/` 和 Cabbage 工作流；基线 Python 测试 13/13 通过。
- [x] 记录当前 `.git` 目录无有效 Git 元数据，因此 `cabbage ci --base` 与分支保护仅能延期验证。

# Tasks

- [x] 运行 `python -m cabbage_cli init` 生成 `.cabbage/`、`docs/`、`.github/workflows/cabbage.yml` 及项目内 CLI 副本，并核对配置启用代码变更绑定和当前状态文档检查。
- [x] 创建 `bootstrap-cabbage-documentation` change，设置 product、architecture、testing、deployment 影响并完成 requirement、impact、design、adr、tests 阶段。
- [x] 填写 PRD、影响矩阵、技术方案、ADR、测试计划和发布计划；修正技术方案使远端 CI 约束与实际工作流一致。
- [x] 将 VuePress Mermaid 集成切换到官方 `@vuepress/plugin-markdown-chart`，补充 `sass-embedded`，并同步生成源、当前站点和 vendored 副本。
- [x] 将 `testing` 影响映射到 `docs/08-testing/`，并同步当前配置、生成源和 vendored CLI，确保 CI 强制测试现状文档同步。
- [x] 添加初始化依赖契约回归测试，覆盖 Mermaid 插件、SASS 预处理器和 vendored 资产一致性。
- [x] 补充 `docs/00-overview`、`01-product`、`03-architecture`、`08-testing`、`11-ci-cd`、`12-release` 当前状态文档并更新站点导航。
- [x] 使用 pnpm 生成 `docs/pnpm-lock.yaml`，保证 CI 的 `--frozen-lockfile` 可复现。

# Verification

- [x] `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`：14/14 通过（含新增依赖契约测试）。
- [x] `python -m cabbage_cli gate bootstrap-cabbage-documentation implementation`：返回 `ALLOWED`。
- [x] `PYTHONDONTWRITEBYTECODE=1 python -m cabbage_cli docs build`：VuePress 构建成功并生成 `docs/.vuepress/dist/`。
- [x] `python -m cabbage_cli validate bootstrap-cabbage-documentation`、发布前 gate 和 merge gate 均作为最终检查执行。
- [x] 已记录部署顺序、回滚触发条件、回滚步骤及 Git 集成延期项；本变更无运行时数据迁移。
