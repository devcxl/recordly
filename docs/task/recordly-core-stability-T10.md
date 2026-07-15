## Parent
Part of #27

## 任务信息
- **Task ID:** T10
- **Slug:** extract-project-session
- **类型:** refactor
- **Batch:** B5

## 依赖
depends-on: #33
depends-on: #35

## 描述
从 `MainWindow` 提取 `ProjectSession` 类。

职责：拥有当前项目目录、Project 模型和媒体资源路径契约。迁移以下 P0 阶段分散在 MainWindow 和 Project 模块的职责：
- 项目目录路径管理（替代 `_current_project_path`）
- 原子 JSON 保存（复用 T06 的 `Project.save()` 原子写入）
- WAV 音频文件路径管理和读写（迁移 T07 的 MainWindow WAV helper 逻辑到 `save_audio()` / `load_audio()` 方法）
- `project.json` → 项目目录路径规范化（替代 T04 的路径处理逻辑，提供 `normalize_path()` 静态方法）

公开接口：
- `__init__(project_dir: str)`
- `project_dir`, `project`, `project_file`, `frames_data_path` 属性
- `create(projects_dir, name)` / `load(project_dir)` 类方法
- `save(...)`, `save_audio(...)`, `load_audio()` 方法
- `normalize_path(input_path)` 静态方法

迁移策略：先加后切 — 在 MainWindow 中同时保留 `_current_project_path` 和 `_project_session`，通过 ProjectSession 读写后逐步移除直接路径操作。`_on_open_project` 使用独立临时 ProjectSession 校验后再替换（安全拒绝协议）。

## 验收标准
- [ ] `app/project_session.py` 通过全部单元测试
- [ ] `ProjectSession.save()` 使用 T06 的原子写入
- [ ] `ProjectSession.load()` 使用 T03 的 schema 验证
- [ ] `ProjectSession.save_audio()` / `load_audio()` 正确读写项目目录下的 WAV 文件
- [ ] `ProjectSession.normalize_path()` 将 `project.json` 文件路径规范化为目录路径
- [ ] `pytest tests/test_project_session.py -q` 全部通过
- [ ] 现有 MainWindow 测试不退化（渐进引入，不破坏已有行为）
- [ ] ProjectSession 纯 Python（非 QObject），可独立测试

## 输出文件
- `app/project_session.py` — **新增**（~180 行）
- `app/main_window.py` — 渐进引入 ProjectSession（保留旧路径兼容）
- `core/project.py` — 如需，暴露公共接口给 ProjectSession
- `tests/test_project_session.py` — **新增**（单元测试）
- `tests/test_main_window.py` — 更新以适配渐进引入

## 需求追踪
- F14（原子保存复用）
- F16（ProjectSession 提取）
- US-4（可维护架构）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
