## Parent
Part of #27

## 任务信息
- **Task ID:** T13
- **Slug:** main-window-slim-down
- **类型:** refactor
- **Batch:** B8

## 依赖
depends-on: #38
depends-on: #39

## 描述
MainWindow 从 1245 行缩减到 ≤800 行，并消除跨模块私有字段访问。

删除的职责（已迁移到对应 Controller）：

| 原 MainWindow 职责 | 迁移到 |
|-------------------|--------|
| `_current_project_path` 管理 | `ProjectSession.project_dir`（T10） |
| `_auto_create_project` / `_finalize_project` | `RecordingController`（T11）+ `ProjectSession.save()`（T10） |
| 录制启动/停止 2 套入口 | `RecordingController.start()` / `stop()`（T11） |
| 导出 QThread 创建/绑定/清理 | `ExportController.start_export()`（T12） |
| `_cancel_export` | `ExportController.cancel()`（T12） |
| `_on_export_finished` 线程清理 | `ExportController.export_finished` 信号（T12） |
| `_recorder.screen._store._offsets` 访问 | 移除（通过 ProjectSession 获取） |
| `_compositor._frames/_cursor_events/_click_events` 访问 | 通过 ProjectSession 获取 |
| `_timeline._tracks` 访问 | 通过公开方法 |
| `_playback._playing/_current_frame` 访问 | 通过公开方法 |

保留的职责：QStackedWidget 页面切换、菜单栏/工具栏可见性、信号绑定、播放控制、时间线同步、裁剪/缩放编辑、设置对话框。

## 验收标准
- [ ] `wc -l app/main_window.py` ≤ 800 行
- [ ] MainWindow 不直接访问 `_recorder.screen._store._offsets`
- [ ] MainWindow 不直接访问 `_compositor._frames/_cursor_events/_click_events/_clips`
- [ ] MainWindow 不直接访问 `_timeline._tracks`
- [ ] MainWindow 不直接访问 `_playback._playing/_current_frame`
- [ ] `pytest tests/test_main_window.py -q` 全部通过（不退化）
- [ ] 全量 `pytest -q` 通过

## 输出文件
- `app/main_window.py` — 1245 → ≤800 行，移除私有字段访问
- `tests/test_main_window.py` — 更新以适配信号绑定变更

## 需求追踪
- F19（MainWindow ≤800 行）
- US-4（可维护架构）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
