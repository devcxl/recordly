## Parent
Part of #27

## 任务信息
- **Task ID:** T17
- **Slug:** function-length-limit
- **类型:** verify
- **Batch:** B11

## 依赖
depends-on: #42
depends-on: #43

## 描述
验证并修复所有新增/修改的函数不超过 50 行（PRD F25）。本任务为交叉验证 pass，不引入新功能。T15（QSS 提取）、T16（光标性能）、T14（logging）全部完成后，对所有修改文件中的函数行数做最终检查。

验证范围：本轮修改的所有文件中新增或修改的函数。如发现超出 50 行的函数，拆分重构。

## 验收标准
- [ ] 所有新增函数 ≤50 行
- [ ] 所有修改函数 ≤50 行
- [ ] 拆分重构不影响既有测试通过
- [ ] `pytest -q` 全量通过
- [ ] 最终审查无违规

## 输出文件
- 按需修改本轮涉及的文件中的超长函数

## 需求追踪
- F25（函数 ≤50 行）
- US-4（可维护架构）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
