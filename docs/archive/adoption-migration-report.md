# Recordly 文档迁移报告（Cabbage 规范采纳）

**日期:** 2026-09-02（迁移时环境日期）
**类型:** Existing Project Documentation Adoption（SOP 2，受限执行）

## 一、背景与限制

- 目标：将项目既有文档迁移至 Cabbage 标准编号 docs 树（`.agents/skills/project-docs-management/references/directory-structure.md`）。
- 限制：`/home/devcxl/Projects/OtherProjects/recordly`（含 `.git`）在本环境为只读，`recordly/docs` 为可写挂载。因此本次仅执行**文档内容迁移 + 链接修复**；`.cabbage/` 初始化、`cabbage adopt/validate/docs build`、VitePress 骨架与 CI 留待可写环境补跑（见第五节）。
- 遵行规则：不重命名历史 ADR、不改写归档内容、每次迁移同步修复引用。

## 二、分类与迁移清单

按 `.agents/skills/project-docs-management/references/adoption.md` 的 action 语义：

### migrate（当前状态文档 → 标准树）

| 源目录 | 数量 | 目标 |
|---|---|---|
| `prd/` | 10 | `01-product/prd/`（PRD） |
| `design/`（非 task-graph） | 5 | `03-architecture/system-design/`（Tech Spec） |
| `dev/specs/` | 7 | `03-architecture/system-design/`（Tech Spec） |

### import（历史/不可变记录 → 归档或决策树）

| 源目录 | 数量 | 目标 | 理由 |
|---|---|---|---|
| `adr/` | 10 | `03-architecture/adr/` | 架构决策记录，不可变 |
| `design/*-task-graph.md` | 3 | `archive/design/` | 已完成变更的任务 DAG（工作区历史） |
| `dev/`（其余全部，含 `tasks/`、`handoff/`） | 43 | `archive/dev/` | 任务分解/交接/开发笔记 |
| `review/` | 7 | `archive/review/` | 事件型评审记录（含审查对象版本） |
| `task/` | 18 | `archive/task/` | 任务工作区历史 |

### 新增

| 文件 | 说明 |
|---|---|
| `00-overview/README.md` | 项目概览与文档导航入口 |
| `01-product/prd/README.md` | PRD 索引 |
| `03-architecture/system-design/README.md` | Tech Spec 索引 |
| `03-architecture/adr/README.md` | ADR 索引与命名说明 |
| `archive/README.md` | 归档区说明 |

**未删除任何内容**（Git 保留历史，全部文件迁入或归档）。

## 三、链接修复

- 项目文档内的引用一律为反引号文本路径 `docs/<dir>/<file>.md`（非 Markdown 链接），按新位置统一改写：
  - `docs/prd/` → `docs/01-product/prd/`
  - `docs/design/`（非 task-graph） → `docs/03-architecture/system-design/`
  - `docs/design/*-task-graph.md` → `docs/archive/design/`
  - `docs/adr/` → `docs/03-architecture/adr/`
  - `docs/dev/specs/` → `docs/03-architecture/system-design/`
  - `docs/dev/` → `docs/archive/dev/`
  - `docs/review/` → `docs/archive/review/`
  - `docs/task/` → `docs/archive/task/`
- 先例替换（task-graph）在通用规则之前执行，避免被 `docs/design/` 规则误改。

## 四、验证结果

- 项目文档 130 个 md 文件（125 原有 + 4 README + `00-overview/README.md` + 迁移报告）。
- 全部 28 个唯一 `docs/...` 文件引用与 61 个 Markdown 链接解析成功，0 残留旧路径。
- `.agents/` 内 skill 包自身引用（`00-overview/README.md`、`ADR-0001-*`、`08-testing/README.md` 等模板示例）未受影响。

## 五、后续补跑步骤（需项目根写权限）

```bash
# 1. 初始化 Cabbage（添加 .cabbage/、VitePress 骨架、CI wiring，不触碰现有文档）
cabbage init

# 2. 盘点：应显示 keep / 已迁移
cabbage adopt --json

# 3. 建立采纳基线变更记录
cabbage new feature adopt-existing-docs
#    填写 prd.md（迁移内容、剩余项）与 tasks.md（迁移批次），verify 各阶段

# 4. 站点构建验证
cabbage validate adopt-existing-docs
cabbage docs build

# 5. 合并基线 PR；随后启用 CI 门禁与分支保护（references/enforcement.md）
```

## 六、遗留说明

- `.agents/` 下 skill 包自带 `.cabbage/changes/`（bootstrap-cabbage-documentation 等）是技能作者的历史示例，不属于本项目文档，保持原样；若 `cabbage adopt` 内置扫描将其计入，请在盘点时忽略或删除。
- 项目根 `README.md` / `README.en.md` 为仓库首页，未纳入 docs 树；如需并入 `00-overview` 请另行决策。