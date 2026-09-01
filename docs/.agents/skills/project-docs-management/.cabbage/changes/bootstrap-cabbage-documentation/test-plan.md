---
change: bootstrap-cabbage-documentation
cabbage_stage: tests
change_type: feature
---

# Strategy

验证重点是自举文件能被项目自身 CLI 正确识别、适用阶段和当前状态文档满足门禁、既有 Python 行为无回归，以及 VuePress 文档站点可构建。测试通过公开 CLI 命令和文件输出观察结果，不直接修改内部状态。Git diff 集成因当前 `.git` 无效只能记录为受限项，不能视为已通过。

| Level | Scope | Test seam | Owner |
|---|---|---|---|
| Unit/Regression | CLI 解析、模板、阶段状态和门禁既有行为 | `python -m unittest` 测试结果 | 项目维护者 |
| Integration | 自举 change 的结构、标题、影响矩阵和阶段状态 | `cabbage validate` 与 `cabbage gate` 退出码 | 项目维护者 |
| Build | VuePress 配置、Markdown 和 Mermaid 生产构建 | `cabbage docs build` 生成 `docs/.vuepress/dist/` | 项目维护者 |
| Manual | 当前状态文档内容、CI 配置和已知限制 | 文件评审与残留占位扫描 | 代码审查者 |

# Test Environment and Data

从项目根目录执行测试，使用仓库内 `cabbage_cli` 和 `.cabbage/` 数据，不需要账号或业务测试数据。Python 测试设置 `PYTHONDONTWRITEBYTECODE=1`，避免生成字节码文件。文档构建需要 pnpm 及 `docs/package.json` 声明的依赖，构建产物位于 `docs/.vuepress/dist/`，不纳入变更提交。GitHub Actions 和分支保护需要有效 Git 仓库及远程托管环境，当前不具备。

# Cases

| ID | Scenario | Level | Expected result | Priority |
|---|---|---|---|---|
| T-1 | 运行完整 Python 回归测试 | Unit/Regression | `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` 全部通过 | High |
| T-2 | 校验自举 change | Integration | `cabbage validate bootstrap-cabbage-documentation` 返回成功且没有结构或占位错误 | High |
| T-3 | 检查实现前门禁 | Integration | 必需的 requirement、impact、design 等前置阶段完成后 implementation gate 通过 | High |
| T-4 | 检查合并门禁 | Integration | 所有激活阶段与当前状态文档完成后 merge gate 通过 | High |
| T-5 | 构建文档站点 | Build | pnpm 依赖可用时 `cabbage docs build` 成功并生成站点产物 | High |
| T-6 | 扫描未处理占位内容 | Manual | 自举文档不存在禁用占位关键字或模板提示 | High |
| T-7 | 检查影响矩阵 | Manual | product、architecture、testing、deployment 为 true，其余项为 false，并与 impact 文档一致 | Medium |
| T-8 | 验证 Git diff CI | Integration | 当前环境明确报告因 `.git` 无效而未执行，不产生误报 | Medium |

# Regression Coverage

- `tests/` 中现有 CLI 单元测试覆盖初始化、模板生成、阶段完成、占位门禁和验证行为。
- 全量 unittest 用于确认新增治理文件没有改变 `cabbage_cli` 既有行为。
- `cabbage validate` 和阶段 gate 覆盖 workflow 标题契约、签名及依赖关系。
- 文档构建覆盖 VuePress 配置、Markdown 解析和 Mermaid 集成。

# Non-functional Testing

| Quality attribute | Method | Threshold |
|---|---|---|
| 可维护性 | 人工检查文档导航、职责边界和重复内容 | 所有必需领域有单一明确入口，change 与当前状态文档职责不混淆 |
| 安全性 | 扫描新增配置和文档，确认没有凭据或敏感信息 | 0 个明文密钥、令牌或个人数据 |
| 可复现性 | 使用文档中给出的原始命令在项目根目录执行 | Python 测试和本地门禁结果稳定；文档构建在 pnpm 依赖可用时稳定 |
| 性能 | N/A：仅新增静态配置和文档，不改变运行时性能路径 | 不设运行时阈值 |

# Entry and Exit Criteria

- Entry: `.cabbage/`、`docs/`、`.github/workflows/cabbage.yml` 和自举 change 文件已生成，所有计划内容已填写。
- Exit: 本地可执行的 validate、gate 和 Python 测试全部通过；pnpm 可用时文档构建通过；占位扫描为零；Git 集成限制已在验证报告中明确记录。

# Risks

- 当前 `.git` 无效，无法执行可信的 `cabbage ci --base` 或验证分支保护；恢复有效仓库后补测，并在完成前保持该项为未验证。
- pnpm 或依赖可能尚未安装，导致文档构建受环境限制；在具备依赖安装条件的环境中补跑并记录命令输出。
- 人工评审才能判断文档语义是否准确；自动门禁只负责结构、占位和状态一致性，因此由代码审查者复核关键内容。
