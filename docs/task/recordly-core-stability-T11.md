## Parent
Part of #27

## 任务信息
- **Task ID:** T11
- **Slug:** extract-recording-controller
- **类型:** refactor
- **Batch:** B6

## 依赖
depends-on: #32
depends-on: #37

## 描述
从 `MainWindow` 提取 `RecordingController`。

职责：拥有录制生命周期状态机。所有录制入口（首页按钮、托盘菜单）通过 RecordingController 统一调度，复用 T05 建立的统一录制逻辑。内部使用 T10 的 `ProjectSession.create()` 创建项目目录。

状态机：
```
IDLE → STARTING → RECORDING → STOPPING → IDLE
                  ↓ (异常)       ↓ (异常)
               FAILED         RECOVERY
```

公开接口：
- `state: RecordingState` 属性
- `start(project_dir=None) -> ProjectSession` 方法
- `stop() -> dict` 方法
- `set_callbacks(on_state_changed, on_error)` 回调注册
- `cleanup()` 强制清理

迁移策略：替换 MainWindow 中所有直接 `recorder.start()`/`recorder.stop()` 调用为 `RecordingController.start()`/`stop()`。MainWindow 只响应 `on_state_changed` 回调更新 UI。录制失败恢复逻辑从 MainWindow 迁移到 Controller 内部。

## 验收标准
- [ ] `app/recording_controller.py` 通过全部单元测试
- [ ] 状态机覆盖 5 种状态 × 3 种异常路径 = 15 个测试用例
- [ ] 首页录制、托盘录制均通过 RecordingController 统一入口
- [ ] 启动失败 → FAILED 状态 + 错误回调 + 项目清理与 T05 行为一致
- [ ] 停止失败 → RECOVERY 状态 + 有帧时保留项目
- [ ] `pytest tests/test_recording_controller.py -q` 全部通过
- [ ] 现有 MainWindow 录制测试不退化
- [ ] RecordingController 纯 Python（非 QObject）

## 输出文件
- `app/recording_controller.py` — **新增**（~200 行）
- `app/main_window.py` — 替换录制入口为 RecordingController 调用
- `tests/test_recording_controller.py` — **新增**（状态机全覆盖测试）
- `tests/test_main_window.py` — 更新录制流程测试

## 需求追踪
- F17（RecordingController 提取）
- US-1（可靠录制与恢复）
- US-4（可维护架构）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
