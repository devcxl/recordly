## Parent
Part of #27

## 任务信息
- **Task ID:** T15
- **Slug:** qss-extraction
- **类型:** polish
- **Batch:** B10

## 依赖
depends-on: #41

## 描述
将 `main.py:9-228` 中的 `DARK_STYLESHEET` 常量（228 行内联 QSS）完整移至 `resources/style.qss`，main.py 改为文件读取。不改变任何样式规则。

## 验收标准
- [ ] `resources/style.qss` 存在且内容与 `DARK_STYLESHEET` 完全一致
- [ ] `main.py` 中无 `DARK_STYLESHEET` 常量
- [ ] `main.py` 通过文件读取加载 QSS
- [ ] UI 视觉与之前完全一致（启动后对比截图）
- [ ] QSS 文件路径不存在时优雅降级（使用系统默认样式）

## 输出文件
- `resources/style.qss` — **新增**（~228 行）
- `main.py` — 移除 DARK_STYLESHEET，改用文件读取

## 需求追踪
- F23（QSS 提取）
- US-4（可维护架构）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
