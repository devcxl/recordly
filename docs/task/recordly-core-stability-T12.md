## Parent
Part of #27

## 任务信息
- **Task ID:** T12
- **Slug:** extract-export-controller
- **类型:** refactor
- **Batch:** B7

## 依赖
depends-on: #36
depends-on: #37
depends-on: #38

## 描述
从 `MainWindow` 提取 `ExportController`。

职责：拥有 QThread + ExportWorker 生命周期管理。确保 finished 信号在所有路径恰好发出一次（复用 T09 的鲁棒性保证）；统一取消/清理协议。通过 T10 的 `ProjectSession` 获取音频数据路径和项目 FPS。

公开接口：
- `export_progress: pyqtSignal(int)` 信号
- `export_finished: pyqtSignal(ExportResult)` 信号
- `start_export(compositor, project_session, settings)` 方法
- `cancel()` 方法
- `is_exporting: bool` 属性

迁移策略：替换 MainWindow 中 `_on_export` 的 QThread 创建/信号绑定/清理为 ExportController。MainWindow 只连接 `export_finished` 信号和创建进度框。

## 验收标准
- [ ] `app/export_controller.py` 通过全部单元测试
- [ ] `ExportController.export_finished` 在所有路径恰好发出一次
- [ ] `ExportController.cancel()` 完整执行进程终止 + 临时文件清理 + 不完整输出删除
- [ ] MainWindow._on_export() 简化为调用 `ExportController.start_export()`
- [ ] MainWindow._cancel_export() 简化为调用 `ExportController.cancel()`
- [ ] `pytest tests/test_export_controller.py -q` 全部通过
- [ ] 现有导出测试不退化

## 输出文件
- `app/export_controller.py` — **新增**（~180 行，唯一 QObject Controller）
- `app/main_window.py` — 替换导出入口为 ExportController
- `tests/test_export_controller.py` — **新增**（finished 单次、取消清理、FFmpeg 失败）

## 需求追踪
- F15（导出清理统一）
- F18（ExportController 提取）
- US-3（正确导出）
- US-4（可维护架构）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
