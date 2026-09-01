---
change: integrate-openspec-workflow
cabbage_stage: api
change_type: feature
---

# Overview

Cabbage CLI 命令行接口规范更新：包含子命令参数结构、标准输出格式与退出码定义。

# Contract

## Operations

| Method or event | Path or topic | Purpose | Authentication | Idempotency |
|---|---|---|---|---|
| CLI Command | `cabbage verify <change> <stage>` | 验证并锁定指定阶段产物签名 | 本地权限 | 幂等（内容未改动时状态保持 done） |
| CLI Command | `cabbage sync <change>` | 同步变更规范至 `docs/` 当前状态目录 | 本地权限 | 幂等覆盖 |
| CLI Command | `cabbage archive <change>` | 校验门禁、同步文档并归档变更工作区 | 本地权限 | 幂等移动 |

## Inputs and Outputs

| Name | Location | Type | Required | Validation or semantics |
|---|---|---|---|---|
| `change` | CLI arg | string | Yes | kebab-case 格式的变更标识符 |
| `stage` | CLI arg | string | Yes | 对应工作流中存在的 stage id |
| `--json` | CLI flag | boolean | No | 以 JSON 结构化输出结果 |

# Error Model

| Code or condition | Meaning | Client action | Retryable |
|---|---|---|---|
| Exit Code 0 | 命令执行成功 / 校验通过 | 进入后续步骤 | Yes |
| Exit Code 1 | 门禁检查未通过 / 静态校验失败 | 检查报告并补全要求 | Yes |
| Exit Code 2 | 参数错误 / 存在未处理的占位符 / 依赖未满足 | 根据报错提示修正产物 | Yes |

# Compatibility

- 废除原有的 `cabbage complete`，CLI 参数解析器不再提供该子命令。
- 所有其他命令（`init`, `adopt`, `new`, `status`, `next`, `impact`, `validate`, `gate`, `archive`, `ci`, `docs`）保持语法兼容。

# Security

CLI 操作均限于当前项目根目录下，防止相对路径穿越（`..` 逃逸项目目录会被拒绝）。

# Observability

支持 `--json` 输出结构化数据供 AI Agent 与 CI 流水线解析。
