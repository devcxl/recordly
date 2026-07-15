## Parent
Part of #27

## 任务信息
- **Task ID:** T03
- **Slug:** project-schema-frame-style
- **类型:** fix+refactor
- **Batch:** B0

## 依赖
无

## 描述
修复 `test_default_values_for_legacy_project` 测试失败，并统一 `FrameStyle.bg_color` 的运行时类型与序列化格式契约。

1. **Project.load() schema 验证：** 当前 `Project.load()` 直接将 JSON 字典展开到 dataclass，旧 `CursorSettings` 的 `size/theme/color` 字段导致 `TypeError`。本任务限定当前 schema：拒绝未知字段并抛 `ValueError`（含明确错误信息），缺失 optional 字段使用 dataclass 默认值。**本轮不实现历史项目迁移**（Out-of-Scope）。
2. **测试更新：** `test_default_values_for_legacy_project` 需更新为测试当前 schema 验证行为（拒绝旧字段、接受当前格式）。
3. **FrameStyle.bg_color 统一：** 运行时类型统一为 `tuple[int,int,int]`，JSON 持久化统一为 `#RRGGBB` 字符串。`Project.save()` 边界显式 encode tuple→str，`Project.load()` 边界校验 `^#[0-9A-Fa-f]{6}$` 后 decode str→tuple。拒绝旧 `margin/radius` 等未知字段。

## 验收标准
- [ ] `pytest tests/test_data_persistence.py -q` 全部通过（当前 1 failed）
- [ ] `pytest tests/test_project.py -q` 全部通过
- [ ] `pytest tests/test_frame_style.py -q` 全部通过
- [ ] `Project.load()` 对未知字段抛 `ValueError` 并包含字段名
- [ ] `Project.load()` 对缺失 optional 字段使用默认值
- [ ] `FrameStyle.bg_color` 运行时 `isinstance(x, tuple)` 为真，JSON 中匹配 `^#[0-9A-Fa-f]{6}$`
- [ ] 旧 CursorSettings 和 FrameStyle 未知字段被安全拒绝（当前 schema 限定）

## 输出文件
- `core/project.py` — `Project.load()` schema 验证 + `Project.save()` bg_color encode
- `core/frame_style.py` — bg_color 类型注解和边界处理（如需）
- `tests/test_data_persistence.py` — 更新为测试当前 schema 行为

## 需求追踪
- F1（测试基线恢复）
- F4（无效项目处理）
- F24（FrameStyle.bg_color 统一）
- US-2（项目持久化验证）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
