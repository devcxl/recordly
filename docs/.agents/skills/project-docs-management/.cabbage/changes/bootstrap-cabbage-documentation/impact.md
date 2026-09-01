---
change: bootstrap-cabbage-documentation
cabbage_stage: impact
change_type: feature
---

# Change Summary

项目使用自身提供的 Cabbage 工作流管理项目文档：初始化 `.cabbage/`、`docs/` 和 GitHub Actions 配置，并以本变更记录自举过程。主要影响项目维护者、开发 Agent 和代码审查者的文档编写、验证与合并流程，不改变 CLI 对外功能。

# Impact Matrix

| Area | Impact | Notes |
|---|---|---|
| Product | Yes | 新增产品现状和自举需求文档，项目贡献流程加入文档治理 |
| Architecture | Yes | 记录 Cabbage 自举结构、文档与门禁之间的职责关系 |
| API | No | 不新增或修改任何程序接口 |
| Database | No | 项目不引入数据库或结构迁移 |
| Security | No | 不改变权限、凭据、信任边界或敏感数据处理 |
| Testing | Yes | 固化 Python 回归测试和文档验证策略 |
| Deployment | Yes | 新增 GitHub Actions 文档门禁和 VuePress 构建流程 |
| Operations | No | 不新增运行时服务、告警、值班或操作手册要求 |
| Data | No | 不新增业务数据、迁移或保留策略 |
| Performance | No | 不改变运行时代码路径或性能目标 |

# Impact Details

- **Product**：新增项目概览、产品定位等当前状态文档，并规定后续代码变更通过 `.cabbage/changes/` 留存可审核材料。消费者是维护者、开发 Agent 和审查者。
- **Architecture**：新增架构现状文档，说明 `.cabbage/` 变更记录、`docs/` 当前状态资料、CLI 门禁及 CI 的协作关系。没有新增运行时组件或数据流。
- **Testing**：将 `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` 作为 Python 回归验证命令，同时校验阶段文档结构、占位内容和门禁状态。
- **Deployment**：新增 `.github/workflows/cabbage.yml`，并要求使用 pnpm 安装和构建 VuePress 文档站点。当前 `.git` 无效，`cabbage ci --base` 和分支保护暂不可验证。

# Risks

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| 当前 Git 元数据无效 | High | 无法验证 diff 驱动的 CI 检查，也无法确认分支保护生效 | 恢复有效 Git 仓库后补跑 `cabbage ci --base`，并将 Cabbage job 配置为必需状态检查 | 项目维护者 |
| 文档站点依赖未安装 | Medium | VuePress 构建无法在当前环境完成 | 使用 pnpm 安装锁定依赖后执行 `cabbage docs build` | 项目维护者 |
| 后续变更绕过自举流程 | Medium | 文档逐步失真，门禁失去治理作用 | 在贡献流程和 CI 中持续要求 change 记录及当前状态文档同步 | 项目维护者 |

# Documentation Updates

- `docs/00-overview/README.md`：项目定位、核心能力和文档导航。
- `docs/01-product/README.md`：产品目标、用户与使用场景。
- `docs/03-architecture/README.md`：CLI、配置、工作流、变更记录和 CI 的结构关系。
- `docs/08-testing/README.md`：测试分层、命令和验证边界。
- `docs/11-ci-cd/README.md`：Cabbage CI 与文档站点构建流程。
- `docs/12-release/README.md`：发布前置条件、验证和回滚原则。
