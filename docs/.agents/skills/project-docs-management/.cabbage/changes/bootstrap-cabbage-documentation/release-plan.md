---
change: bootstrap-cabbage-documentation
cabbage_stage: release
change_type: feature
---

# Release Summary

本次发布将 Cabbage 文档治理基础设施、自举 change、项目当前状态文档和 GitHub Actions 配置纳入仓库。它不发布运行时服务或改变 CLI 接口；发布窗口为本变更合并时，负责人为项目维护者，主要受影响对象是后续贡献者、开发 Agent 和审查者。

# Preconditions

- [x] release 之前的全部激活阶段已完成；`cabbage validate` 已通过，merge gate 在发布阶段结束前执行。
- [x] `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` 全部通过（14/14）。
- [x] 已人工复核 `docs/` 当前状态资料与项目实现一致。
- [x] pnpm 依赖可用时，`cabbage docs build` 已成功执行。
- [x] 已在发布记录中注明当前 `.git` 无效以及尚未验证的 `cabbage ci --base` 和分支保护。

# Deployment

| Order | Action | Owner | Success signal |
|---|---|---|---|
| 1 | 完成本地 Cabbage 阶段与内容校验 | 项目维护者 | validate 和适用 gate 返回成功 |
| 2 | 执行 Python 全量回归测试 | 项目维护者 | unittest 全部通过且退出码为 0 |
| 3 | 使用 pnpm 构建 VuePress 文档站点 | 项目维护者 | `cabbage docs build` 成功生成 `docs/.vuepress/dist/` |
| 4 | 合并 `.cabbage/`、`docs/` 和 `.github/workflows/cabbage.yml` | 项目维护者 | 仓库默认分支包含完整自举资料 |
| 5 | Git 仓库恢复后启用 Cabbage 必需状态检查 | 仓库管理员 | `cabbage ci --base` 在 CI 中通过且分支保护阻止失败提交 |

# Rollback

## Triggers

- 新增配置导致现有 Python 测试失败且无法在发布窗口内修复。
- VuePress 站点无法由锁定依赖稳定构建。
- Cabbage 门禁错误阻止与文档无关的正常项目变更。
- 当前状态文档包含会误导使用者的重大事实错误。

## Steps

1. 项目维护者暂停将 Cabbage job 设为必需状态检查，避免继续阻塞合并。
2. 回退本变更新增的 `.github/workflows/cabbage.yml`、`docs/` 和 `.cabbage/` 自举内容。
3. 重新执行 Python 回归测试，确认项目恢复至发布前行为。
4. 保存失败日志和问题描述；本变更不迁移业务数据，无需执行数据恢复。

# Verification

| Check | Method | Expected result | Owner |
|---|---|---|---|
| Change 结构与内容 | `cabbage validate bootstrap-cabbage-documentation` | 无结构、标题、状态或占位错误 | 项目维护者 |
| 实现与合并门禁 | `cabbage gate bootstrap-cabbage-documentation implementation` 及 merge gate | 所有适用门禁返回成功 | 项目维护者 |
| Python 回归 | `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` | 所有测试通过 | 项目维护者 |
| 文档生产构建 | `cabbage docs build` | pnpm 构建成功并生成 `docs/.vuepress/dist/` | 项目维护者 |
| Git 集成 | 恢复有效 Git 后执行 `cabbage ci --base <base>` | CI 检查返回成功；当前发布标记为尚未验证 | 仓库管理员 |

# Monitoring

本变更不部署运行时服务，因此没有运行时仪表盘或告警。合并后的首个变更周期内观察本地 CLI 输出、Python 测试、VuePress 构建和 GitHub Actions Cabbage job；任一必需检查持续失败或错误放行缺少文档的代码变更时，由项目维护者暂停门禁并按回滚步骤处理。

# Communication

在合并说明中通知维护者和贡献者：后续重要变更必须通过 `.cabbage/changes/` 管理，并同步对应 `docs/` 当前状态资料。发布说明列出本地验证结果、pnpm 文档构建状态，以及当前 `.git` 无效导致 `cabbage ci --base` 与分支保护尚未验证。问题由项目维护者在仓库问题跟踪渠道受理。
