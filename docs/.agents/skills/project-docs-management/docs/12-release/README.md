# 发布说明

Cabbage 当前版本为 `0.1.0`，项目已具备 Python 包元数据、wheel 构建能力和本地安装脚本，但尚未配置自动化包发布或 GitHub Release 流程。

## 发布物

| 发布物 | 当前形式 |
| --- | --- |
| Python 包 | 项目名 `project-docs-cabbage`，包含 `cabbage_cli` 与内置 assets |
| 命令行入口 | `cabbage = cabbage_cli.cli:main` |
| 本地安装入口 | `scripts/install.sh` 在用户可执行目录创建 `cabbage` 启动脚本 |
| 项目内工具副本 | `cabbage init` 默认复制到 `.cabbage/tooling/cabbage_cli/` |
| 文档站点 | `docs/` 下的 VuePress 静态站点，可构建但当前不自动部署 |

## 兼容性基线

- Python：3.10 及以上。
- 运行依赖：PyYAML 6.0 及以上。
- 当前包版本与 `cabbage --version`：`0.1.0`。
- 文档构建环境：Node.js 22、pnpm 10。

## 发布前检查

发布候选版本至少应通过：

```bash
python -m unittest discover -s tests -v
python -m compileall -q cabbage_cli tests
python -m build
cabbage docs build
```

还应在隔离环境安装生成的 wheel，并验证：

```bash
cabbage --version
cabbage init --no-vendor-cli
```

对于受 Cabbage 管理的发布变更，发布前还必须完成所有已激活阶段并通过：

```bash
cabbage validate <change-id>
cabbage gate <change-id> merge
```

## 版本与变更记录

版本号同时存在于 `pyproject.toml` 和 `cabbage_cli/__init__.py`，发布时必须保持一致。变更文档保存在 `.cabbage/changes/`，完成后通过 `cabbage archive <change-id>` 移入按年份组织的归档目录。

## 回滚原则

- 尚未发布的构建失败：修复后重新构建，不复用未验证产物。
- 已发布包存在缺陷：发布新的修复版本，不覆盖既有版本。
- workflow 或模板导致项目门禁异常：回退相关变更，并重新同步 `.cabbage/tooling/` 中的 vendored CLI。
- 文档站点构建失败：阻止合并或部署，不绕过 VuePress 构建检查。

## 当前边界

仓库尚未定义版本递增策略、变更日志生成、制品签名、包仓库发布、Git tag 或 Release 自动化。这些能力引入前应先形成独立的发布流程设计和可回滚验证。
