## Parent
Part of #27

## 任务信息
- **Task ID:** T16
- **Slug:** cursor-interpolation-cache
- **类型:** perf
- **Batch:** B10

## 依赖
depends-on: #41

## 描述
统一光标插值实现并缓存时间索引。

修复范围：
1. `core/compositor.py`：`_interpolate_cursor_raw()` 复用 `_interpolate_cursor()` 的二分逻辑，删除线性扫描版本
2. `core/compositor.py`：可选优化 — `load_frames_data()` 中缓存 `_frame_times` 二分索引
3. `core/camera.py`：`_interpolate()` 预计算 `_event_times: list[float]` 数组，使用 `bisect` 替代线性扫描
4. `core/camera.py`：`_calc_speed()` 复用缓存的 `_event_times`

## 验收标准
- [ ] `_interpolate_cursor_raw()` 使用二分查找（与 `_interpolate_cursor()` 逻辑一致）
- [ ] `camera._interpolate()` 使用 `bisect` + 预计算时间数组
- [ ] `pytest tests/test_compositor.py -q` 全部通过
- [ ] `pytest tests/test_camera.py -q` 全部通过
- [ ] 光标位置和相机缩放与之前完全一致（不引入行为变更）

## 输出文件
- `core/compositor.py` — 统一二分插值 + 缓存优化
- `core/camera.py` — bisect + 事件时间缓存
- `tests/test_compositor.py` — 添加二分查找正确性测试（如需）
- `tests/test_camera.py` — 添加缓存行为测试（如需）

## 需求追踪
- F20（统一光标插值 + 缓存时间索引）
- US-4（可维护架构）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
