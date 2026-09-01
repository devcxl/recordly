---
origin_change: integrate-openspec-workflow
change_type: feature
cabbage_stage: tests
synced_at: '2026-09-01T13:48:39.124012+00:00'
---

# Strategy

在 Python unittest 测试套件中覆盖命令生命周期、模板渲染、规范同步与门禁验证。

| Level | Scope | Test seam | Owner |
|---|---|---|---|
| Unit Test | `verify_stage` 与 `validate_markdown` | `cabbage_cli.core` | Agent |
| Integration Test | `cabbage sync` 与 `cabbage archive` 沉淀 | CLI subprocess & TempDirectory | Agent |

# Test Environment and Data

标准 Python 3.10+ 环境，使用 `unittest` 框架与临时目录（`tempfile.TemporaryDirectory`）做文件系统隔离。

# Cases

| ID | Scenario | Level | Expected result | Priority |
|---|---|---|---|---|
| T-1 | 未编辑占位符时执行 `verify_stage` | Unit | 抛出 `placeholder content remains` 异常 | High |
| T-2 | 填写真实内容后执行 `verify_stage` | Unit | 验证成功并记录哈希签名 | High |
| T-3 | 调用 `sync_change_to_docs` | Unit | 在 `docs/01-product/` 等对应路径生成规范文档 | High |
| T-4 | CLI 运行 `cabbage archive` | Integration | 自动同步文档并成功归档变更目录 | High |
| T-5 | CLI `--help` 检查子命令集合 | Integration | 包含 `verify`、`sync`，不包含 `complete` | High |

# Regression Coverage

- `tests/test_cabbage.py`: 验证工作流流转与门禁。
- `tests/test_templates.py`: 验证所有模板标题合规性。
- `tests/test_cabbage_rename.py`: 验证 CLI 入口与脚手架。
- `tests/test_adopt.py`: 验证存量文档导入与迁移。

# Non-functional Testing

| Quality attribute | Method | Threshold |
|---|---|---|
| 执行性能 | 执行全量单测套件 | 耗时 < 3s |
| 跨平台兼容 | 路径规范化处理 | 兼容 Windows/Linux 分隔符 |

# Entry and Exit Criteria

- Entry: 核心逻辑修改完毕，模板与文档同步就绪。
- Exit: `python3 -m unittest discover tests` 全部 21+ 项测试绿色通过。

# Risks

- 无已知未覆盖风险。
