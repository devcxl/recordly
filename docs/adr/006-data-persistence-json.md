# ADR-006: 录制数据持久化到 Project JSON

**日期:** 2026-07-15
**状态:** Accepted

## 背景

录制完成后，`_auto_create_project` 仅保存 name/duration/source 三个字段到 Project。cursor_events、click_events、camera 状态、timeline、crop_region 等编辑数据全部丢失。`_on_save_project` 是空函数。

## 决策

采用 JSON 直存方案，在 Project dataclass 中新增字段，通过 `asdict()` 序列化到 project.json：

1. 新增字段：cursor_events、click_events、monitor_offset
2. 新增方法 `_collect_project_state(project)` 收集 compositor 和编辑器状态
3. `_auto_create_project` 创建后调用 `_collect_project_state` 再 `save`
4. `_on_save_project` 重写为真正的持久化
5. `_on_open_project` 增强恢复逻辑

## 理由

- 沿用现有 JSON + dataclass 方案，无新依赖
- cursor_events 数据量可控（数千条 ≈ 几百KB）
- 向后兼容（旧 project.json 缺少新字段用默认值）

## 备选方案

1. **独立二进制文件存储** — 增加复杂度，破坏项目自包含性
2. **SQLite 替代 JSON** — 过度设计，当前数据规模不适合

## 影响

- `core/project.py` 新增 3 个字段
- `app/main_window.py` 新增 `_collect_project_state` 方法
- 已有 project.json 保持兼容（新字段可选）
