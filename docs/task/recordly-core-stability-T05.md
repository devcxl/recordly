## Parent
Part of #27

## 任务信息
- **Task ID:** T05
- **Slug:** recording-unified-recovery
- **类型:** fix
- **Batch:** B2

## 依赖
depends-on: #31

## 描述
统一录制入口并实现完整的启动/停止失败恢复。

当前问题：
- 首页录制走 `_start_recording_from_home()` 绕过 `_on_recording_started()` 异常恢复
- 托盘录制绕过项目创建，可能覆盖旧项目或丢失录制
- `core/recorder.py` 启动失败 finally 清理可能覆盖原始异常

修复范围（P0 阶段，不依赖 ProjectSession）：
1. 合并首页和托盘录制入口为单一方法，参数化 `project_dir`
2. 所有入口通过现有 `ProjectManager` 目录创建逻辑生成唯一项目目录，禁止复用上一个项目路径（`_current_project_path`）
3. Recorder 启动失败：逆序清理已启动资源，重新抛原始异常
4. 录制启动失败且无帧时删除占位项目目录，恢复窗口
5. 停止失败但帧可读时保留恢复项目并恢复窗口
6. 数据不可读取时删除损坏项目并明确提示

> P1 阶段 T11 将提取 RecordingController，届时再收敛到统一状态机对象。

## 验收标准
- [ ] 首页录制启动失败 → 窗口恢复、状态栏提示错误、占位项目被清理
- [ ] 屏幕采集停止时失败 → 窗口恢复、有帧时项目保留
- [ ] 托盘录制创建新项目且不修改当前已打开项目
- [ ] 录制中退出应用 → 可恢复录制数据
- [ ] `pytest tests/test_recorder.py -q` 全部通过
- [ ] 新增测试：启动失败恢复 × 2 场景、停止失败恢复 × 2 场景
- [ ] Recorder.finally 块不覆盖原始异常

## 输出文件
- `app/main_window.py` — 合并录制入口（`_on_home_record`、`_on_tray_record`），统一恢复逻辑
- `core/recorder.py` — finally 块逆序清理 + 保留原始异常
- `tests/test_recorder.py` — 修复已有 + 新增失败恢复测试
- `tests/test_main_window.py` — 新增录制恢复流程测试

## 需求追踪
- F5（每次录制独立项目）
- F6（统一状态机）
- US-1（可靠录制与恢复）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
