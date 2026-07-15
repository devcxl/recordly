## Parent
Part of #27

## 任务信息
- **Task ID:** T14
- **Slug:** logging-unified
- **类型:** polish
- **Batch:** B9

## 依赖
depends-on: #40

## 描述
统一为 Python `logging` 模块，替换分散的 `print(file=sys.stderr)` 和 `__import__()` 动态导入日志调用。

修复范围：
1. `main.py` 添加 `logging.basicConfig`，`RECORDLY_DEBUG=1` 时 level=DEBUG 并输出到 stderr，默认 WARNING
2. `core/exporter.py` 移除 `_DEBUG` 常量和 `__import__` 动态导入，替换为 `logging.getLogger(__name__)`
3. `core/compositor.py` 移除 `compose_index()` 中每 60 帧的 stderr FPS debug 输出，替换为 `logger.debug`
4. `core/recorder.py` 中的 debug 输出替换为 logger

## 验收标准
- [ ] `RECORDLY_DEBUG=1` 时 debug 级别日志输出到 stderr
- [ ] 默认（无环境变量）时仅 Warning/Error 输出
- [ ] `core/exporter.py` 中无 `_DEBUG` 常量
- [ ] `core/compositor.py` 中无帧计数 stderr 输出
- [ ] 无 `__import__` 动态导入
- [ ] 不输出完整用户内容或音频数据到日志

## 输出文件
- `main.py` — `logging.basicConfig`
- `core/exporter.py` — _DEBUG → logging
- `core/compositor.py` — print → logger.debug
- `core/recorder.py` — print → logger

## 需求追踪
- F21（logging 统一）
- F22（移除无条件和动态导入输出）
- US-4（可维护架构）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
