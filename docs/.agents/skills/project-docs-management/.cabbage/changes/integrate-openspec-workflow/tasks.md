---
change: integrate-openspec-workflow
cabbage_stage: implementation
change_type: feature
---

# Preparation

- [x] 确认项目结构与 OpenSpec 规范融合设计方案。

# Tasks

- [x] 重构 `cabbage_cli/core.py`：实现 `verify_stage` 与 `sync_change_to_docs`。
- [x] 重构 `cabbage_cli/cli.py`：支持 `cabbage verify`、`cabbage sync`，并在 `archive` 中集成自动同步。
- [x] 升级 `cabbage_cli/assets/templates/` 模板库，融入 Requirements & Scenarios。
- [x] 同步更新 `.cabbage/tooling/cabbage_cli/` vendored CLI 副本。
- [x] 更新 `SKILL.md`、`README.md`、`references/` 与 `docs/` 文档。
- [x] 编写并更新自动化单测套件 `tests/test_cabbage.py` 等。

# Verification

- [x] 运行 `python3 -m unittest discover tests` 确认全部通过。
- [x] 运行 `python3 -m cabbage_cli validate integrate-openspec-workflow` 确认无误。
- [x] 运行 `python3 -m cabbage_cli sync integrate-openspec-workflow` 验证规范沉淀。
- [x] 确认 implementation gate 与 merge gate 均顺利通过。
