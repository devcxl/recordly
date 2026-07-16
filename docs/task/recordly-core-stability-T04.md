## Parent
Part of #27

## 任务信息
- **Task ID:** T04
- **Slug:** project-input-normalization
- **类型:** fix
- **Batch:** B1

## 依赖
depends-on: #28
depends-on: #29
depends-on: #30

## 描述
解决项目路径歧义问题。当前 `MainWindow._on_open_project()` 将 QFileDialog 返回的 `project.json` 文件路径直接传给 `ProjectManager.open_project()`，后者拼接 `/project.json` 导致路径 `.../project.json/project.json`。

修复范围：
1. 在 UI/Session 边界统一将输入规范化为项目目录：`project.json` 文件路径 → `os.path.dirname()` 取父目录
2. `MainWindow._on_open_project()` 文件选择器路径和首页项目卡片路径均经过规范化
3. `MainWindow._auto_create_project()` 确保 `_current_project_path` 始终是目录路径
4. 添加回归测试：选择 `project.json` 文件能正确打开项目；打开无效目录显示明确错误

## 验收标准
- [ ] 首页"打开项目"按钮 → 选择 `project.json` 文件 → 项目成功加载
- [ ] 首页项目卡片 → 点击卡片 → 项目成功加载
- [ ] 选择不存在的路径 → 错误提示，当前状态不变
- [ ] `_current_project_path` 始终是目录路径（无 `.json` 后缀）
- [ ] `pytest tests/test_main_window.py -q -k "open_project"` 通过
- [ ] 新增测试覆盖：文件选择器路径 → 目录规范化 → 加载成功

## 输出文件
- `app/main_window.py` — `_on_open_project()` 路径规范化逻辑
- `core/project_manager.py` — 如需要，适配目录路径契约
- `tests/test_main_window.py` — 新增路径规范化测试 + 修复已有测试

## 需求追踪
- F3（项目输入规范化）
- F4（无效项目打开）
- US-2（项目持久化与重新打开）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
