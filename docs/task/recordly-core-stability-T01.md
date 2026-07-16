## Parent
Part of #27

## 任务信息
- **Task ID:** T01
- **Slug:** test-infra-cv2-mock
- **类型:** test-infra
- **Batch:** B0

## 依赖
无

## 描述
修复 `tests/conftest.py:33-39` 中无条件 `cv2` MagicMock 导致帧存储测试失败的问题。当前 MagicMock 使 `cv2.imencode` 返回 MagicMock 对象而非 `(success, encoded)` 元组，导致 `core/screen_capture.py:69` 解包失败。

修复范围：
- 移除 conftest.py 中全局 `sys.modules['cv2'] = _cv2` 无条件 mock
- 改为在需要 mock 的测试中按需注入（fixture 或模块级 monkeypatch）
- 帧存储测试中确保真实的 `cv2.imencode`/`imdecode` 可用

## 验收标准
- [ ] `pytest tests/test_frames_data.py -q` 全部通过（当前 1 failed）
- [ ] `pytest tests/test_screen_capture.py -q` 全部通过（当前 1 failed）
- [ ] conftest.py 不再包含 `sys.modules['cv2'] = _cv2` 无条件 mock
- [ ] 使用 cv2 的模块在测试中通过 fixture 或模块级 monkeypatch 按需注入 mock
- [ ] 全量测试中 cv2 相关测试不再因 MagicMock 副作用失败

## 输出文件
- `tests/conftest.py` — 移除 cv2 MagicMock
- `tests/test_frames_data.py` — 如需，添加局部 cv2 mock fixture
- `tests/test_screen_capture.py` — 如需，添加局部 cv2 mock fixture

## 需求追踪
- F1（测试基线恢复）
- US-2（项目持久化验证）

## 技术方案参考
- docs/prd/recordly-core-stability.md
- docs/design/recordly-core-stability.md
- docs/design/recordly-core-stability-task-graph.md
- docs/adr/007-project-session-recording-export-controllers.md
