## Parent
Part of #27

## 任务信息
- **Task ID:** T09
- **Slug:** export-robustness
- **类型:** fix
- **Batch:** B5

## 依赖
depends-on: #35

## 描述
修复导出鲁棒性问题：

**F10 — ExportWorker finished 保证：** `run()` 所有路径（成功、失败、取消、异常）恰好发出一次 `finished` 信号。`run()` 顶层 try/except/finally 包裹，finally 统一清理资源。

**F11 — GIF stderr drain：** GIF 路径复用 MP4 已有的 `_start_stderr_reader()`，替换当前的 `process.stderr.read()` 阻塞读。

**F12 — 取消导出清理：** 取消路径执行 `process.terminate()` → `process.wait(timeout=5)`，删除临时 WAV 和不完整输出文件。

**F13 — mktemp → mkstemp：** `core/exporter.py:403,453` 中 `tempfile.mktemp()` 替换为 `tempfile.mkstemp()`。

## 验收标准
- [ ] FFmpeg 不存在时 → worker 发出 `finished(ExportResult(False, ...))`，线程退出，进度框关闭
- [ ] 渲染过程中 BrokenPipe → finished 信号发出，资源清理完整
- [ ] 其他未预期异常 → finished 信号发出，不挂死 UI
- [ ] GIF 大量 stderr 输出 → 不死锁，导出正常完成
- [ ] 取消导出 → 无残留 FFmpeg 进程、临时 WAV、不完整输出文件
- [ ] 全量 `tempfile.mktemp` 引用已替换为 `mkstemp`
- [ ] `pytest tests/test_exporter.py -q` 全部通过
- [ ] 新增测试：FFmpeg 不存在 × worker 结束、GIF 大量 stderr × 不死锁、取消 × 无残留

## 输出文件
- `core/exporter.py` — run() try/except/finally 重构 + GIF stderr drain + mktemp→mkstemp + 取消清理
- `tests/test_exporter.py` — 新增鲁棒性测试

## 需求追踪
- F10（finished 保证）
- F11（stderr drain）
- F12（取消清理）
- F13（mktemp 替换）
- US-3（正确导出）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
