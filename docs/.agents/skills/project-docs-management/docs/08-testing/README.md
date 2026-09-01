# 测试说明

当前自动化测试基线为 14 项 `unittest`，覆盖核心门禁、Cabbage 重命名契约、文档构建依赖契约和全部模板结构。测试不依赖外部服务，主要在临时目录中验证真实文件系统行为。

## 执行方式

```bash
python -m unittest discover -s tests -v
```

Python 语法检查可独立执行：

```bash
python -m compileall -q cabbage_cli tests
```

## 覆盖范围

| 测试文件 | 数量 | 主要覆盖 |
| --- | ---: | --- |
| `tests/test_cabbage.py` | 4 | 未编辑模板拒绝完成、旧占位兼容、完成态校验、门禁与 `stale` 传播 |
| `tests/test_cabbage_rename.py` | 6 | 包和模块入口、初始化路径、项目元数据、文档构建依赖、vendored CLI 可执行性 |
| `tests/test_templates.py` | 4 | 核心及专项模板结构、workflow 标题契约、影响矩阵同步行 |

## 关键行为断言

- 草稿可被普通校验读取，但含占位提示的文档不能完成阶段。
- 完成依赖链后可以通过合并门禁；修改上游需求会使相关下游阶段变为 `stale`。
- `cabbage init` 生成 `.cabbage/config.yaml` 和 `.github/workflows/cabbage.yml`。
- `pyproject.toml` 只暴露 `cabbage` 命令与 `cabbage_cli` 包。
- 内置模板包含评审所需章节，并满足各 workflow 的必需标题契约。

## 当前测试边界

以下行为目前主要依赖实现审查或工作流集成验证，尚无对应的独立自动化测试：

- `ci --base` 对真实 Git diff、归档删除和当前状态目录规则的全部分支；
- 本地 Markdown 断链、路径越界和 Mermaid 围栏异常的逐项回归；
- `archive` 的文件移动与冲突处理；
- `cabbage docs install/dev/build` 与完整 VuePress 构建链；
- GitHub 分支保护是否把 `cabbage` job 配置为必需检查。

新增行为时应优先写失败测试，再做最小实现并运行全量测试。涉及模板或 workflow 的变更还应验证所有模板标题契约，避免新建变更后才暴露结构不匹配。
