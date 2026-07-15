# Recordly 核心稳定性 — T01: test-infra-cv2-mock

**Project:** Recordly
**Task ID:** T01
**Slug:** test-infra-cv2-mock
**Issue:** #28
**类型:** test-infra
**Batch:** B0（测试基础设施恢复）
**依赖:** 无

---

## 1. 目标

修复 `tests/conftest.py` 中无条件 `cv2` MagicMock 导致的测试副作用。当前 Mock 使 `cv2.imencode` 返回 MagicMock 对象而非 `(success, encoded)` 元组，导致帧存储测试和屏幕捕获测试失败。

**受影响测试（2 个）:**
- `tests/test_frames_data.py::TestLoadFramesData::test_load_frames_data_from_index`
- `tests/test_screen_capture.py::TestScreenCapture::test_disk_store_keeps_more_than_legacy_600_frame_limit`

**根本原因:** conftest.py:33-39 中的 `sys.modules['cv2'] = _cv2` 对所有测试生效，但 `_cv2.imencode` 没有返回值签名，导致依赖真实 `cv2.imencode` 的测试失敗。

---

## 2. 前置条件

- Python 3.11+
- `pytest` 可运行，当前 290 passed / 1 skipped
- 理解 `conftest.py` 的 sys.modules mock 机制
- 理解 `ScreenCapture._store_frame()` 依赖 `cv2.imencode`

---

## 3. TDD 实现步骤

### Red — 确认失败（当前状态）

```bash
pytest tests/test_frames_data.py::TestLoadFramesData::test_load_frames_data_from_index -q
# → FAILED: ValueError: not enough values to unpack (expected 2, got 0)
#   原因: cv2.imencode 返回 MagicMock，解包失败

pytest tests/test_screen_capture.py::TestScreenCapture::test_disk_store_keeps_more_than_legacy_600_frame_limit -q
# → FAILED: IndexError: too many indices for array
#   原因: cv2.imencode 在 _store_frame 内部被 mock 化
```

### Green — 分三步实现

#### Step 1: 移除 conftest.py 全局 cv2 mock（最核心改动）

**文件:** `tests/conftest.py`

删除第 32-39 行：

```python
# 删除以下整个 if 块：
# if 'cv2' not in sys.modules:
#     _cv2 = MagicMock()
#     _cv2.imread = MagicMock(return_value=None)
#     _cv2.imwrite = MagicMock(return_value=True)
#     _cv2.cvtColor = MagicMock()
#     _cv2.COLOR_BGR2RGB = 4
#     sys.modules['cv2'] = _cv2
```

> **关键判断:** 检查其他测试是否依赖全局 cv2 mock。搜索 `from cv2` 或 `import cv2` 的测试文件。依赖全局 mock 的测试需要添加局部 fixture。

**验证:** 
```bash
pytest tests/test_frames_data.py -q
# 目标: test_load_frames_data_from_index 通过
```

#### Step 2: 为 screen_capture 测试添加按需 cv2 mock

**文件:** `tests/test_screen_capture.py`

`test_disk_store_keeps_more_than_legacy_600_frame_limit` 在调用 `sc._store_frame()` 时需要真实的 `cv2.imencode`。移除全局 mock 后该测试应该直接通过——除非测试环境没有安装 cv2。

如果测试环境无 cv2，添加模块级 skip：

```python
import pytest
pytest.importorskip("cv2", reason="需要 OpenCV for _store_frame 测试")
```

**验证:**
```bash
pytest tests/test_screen_capture.py::TestScreenCapture::test_disk_store_keeps_more_than_legacy_600_frame_limit -q
# 目标: 通过（或环境中确实安装了 cv2）
```

> **注意:** `test_frames_data.py` 中 `test_load_frames_data_from_index` 显式 `import cv2`，移除全局 mock 后它可以使用真实的 cv2。如果 cv2 不可用，使用 `pytest.importorskip("cv2")` 优雅跳过。

#### Step 3: 搜索并修复依赖全局 cv2 mock 的其他测试

**命令:**
```bash
grep -rn "import cv2\|from cv2" tests/
grep -rn "cv2\." tests/
```

对每个引用了 `cv2` 的测试文件：
- 如果该测试不需要 mock（即环境有 cv2 或测试旨在使用真实 cv2）：无需改动
- 如果该测试原本依赖全局 MagicMock 的 cv2（例如只测试不涉及 imencode 时）：添加局部 fixture

**验证:**
```bash
pytest -q  # 全量测试
# 目标: cv2 相关测试不再因 MagicMock 副作用失败
```

### Refactor — 检查清单

- [ ] conftest.py 不再包含 `sys.modules['cv2']` 赋值
- [ ] 所有 cv2 mock 均为按需注入（fixture 或模块级 monkeypatch）
- [ ] 使用 cv2 的测试在 cv2 不可用时优雅跳过

---

## 4. 接口/契约

**本任务无公开接口变更。**

仅影响测试基础设施：
- `conftest.py` 删除全局 `cv2` mock
- 依赖 mock 的测试文件添加局部 fixture

---

## 5. 数据模型变化

无。

---

## 6. 测试指引

### 单元测试（本任务产出）

| 测试文件 | 测试 | 覆盖场景 |
|---------|------|---------|
| `tests/test_frames_data.py` | `test_load_frames_data_from_index` | 真实 cv2.imencode/imdecode 可用 |
| `tests/test_screen_capture.py` | `test_disk_store_keeps_more_than_legacy_600_frame_limit` | _store_frame 使用真实 cv2 |

### 回归测试

```bash
# 确认修复
pytest tests/test_frames_data.py tests/test_screen_capture.py -q

# 全量检查 cv2 相关副作用
pytest -q -k "cv2"
```

---

## 7. 验收标准

- [ ] `pytest tests/test_frames_data.py -q` 全部通过
- [ ] `pytest tests/test_screen_capture.py -q` 全部通过
- [ ] conftest.py 不再包含 `sys.modules['cv2'] = _cv2` 无条件 mock
- [ ] 使用 cv2 的模块在测试中通过 fixture 或模块级 monkeypatch 按需注入 mock
- [ ] 全量测试中 cv2 相关测试不再因 MagicMock 副作用失败
- [ ] 如果环境中无 cv2，相关测试用 `pytest.importorskip("cv2")` 优雅跳过

---

## 8. 边界情况与风险

| 场景 | 处理 |
|------|------|
| 测试环境没有安装 cv2 | 使用 `pytest.importorskip("cv2")` 跳过依赖 cv2 的测试 |
| cv2 已安装在测试环境 | 测试直接使用真实 cv2，无需任何 mock |
| 某些测试依赖 cv2 但不调用 imencode | 如确需 mock，使用 `monkeypatch.setattr(cv2, "imencode", ...)` 局部替换 |
| conftest.py 中其他 sys.modules mock (pynput/sounddevice/mss) | **不修改**，只移除 cv2 mock |

**风险:** 移除 cv2 mock 后，如果 CI 环境未安装 `opencv-python-headless`，测试会因 `import cv2` 失败而报错（ModuleNotFoundError，非测试失败）。缓解：确认 CI 已安装 opencv-python-headless。

---

## 9. 任务验证命令

```bash
# 本任务焦点测试
pytest tests/test_frames_data.py tests/test_screen_capture.py -q -v

# 全量回归
pytest -q

# 确认 conftest.py 无 cv2 mock
grep -n "cv2" tests/conftest.py
# 预期: 无输出 或 仅在注释中出现
```

---

## 关联文件

| 文件 | 操作 |
|------|------|
| `tests/conftest.py` | 删除 L32-39 cv2 MagicMock 块 |
| `tests/test_frames_data.py` | 如需，添加 `pytest.importorskip("cv2")` |
| `tests/test_screen_capture.py` | 如需，添加 `pytest.importorskip("cv2")` |

> **本任务仅修改测试文件，不触碰任何 `core/` 或 `app/` 业务代码。**
