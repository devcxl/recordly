# Recordly 核心稳定性 — T03: project-schema-frame-style

**Project:** Recordly
**Task ID:** T03
**Slug:** project-schema-frame-style
**Issue:** #30
**类型:** fix + refactor
**Batch:** B0（测试基础设施恢复）
**依赖:** 无

---

## 1. 目标

三合一修复：

1. **Project.load() schema 严格验证** — 拒绝未知字段（如旧版 CursorSettings 的 `size/theme/color`、旧版 FrameStyle 的 `margin/radius`），缺失 optional 字段使用 dataclass 默认值。当前不做历史项目迁移（Out-of-Scope）
2. **FrameStyle.bg_color 统一** — 运行时类型统一为 `tuple[int, int, int]`；JSON 持久化统一为 `#RRGGBB` 字符串。`Project.save()` encode tuple→str，`Project.load()` 校验并 decode str→tuple
3. **测试更新** — `test_default_values_for_legacy_project` 更新为测试当前 schema 行为（拒绝旧字段、接受当前格式）

---

## 2. 前置条件

- 理解 `core/project.py` 中 `Project.load()` 和 `Project.save()` 的实现
- 理解 `core/frame_style.py` 中 `FrameStyle` dataclass（`bg_color` 当前声明为 `tuple = (26, 26, 26)`）
- 理解 `_load_frame_style()` 当前逻辑（L258-263）— 兼容 tuple → str 转换，但这是临时迁移代码

---

## 3. TDD 实现步骤

### Red — 确认失败

```bash
pytest tests/test_data_persistence.py::TestDataPersistenceRoundtrip::test_default_values_for_legacy_project -q
# → FAILED: TypeError: CursorSettings.__init__() got unexpected keyword argument 'size'
#   原因: 旧 JSON 含有 {"cursor": {"size": 24, "theme": "...", "color": "..."}}
#        这些字段在当前 CursorSettings 中不存在（已移除）

pytest tests/test_frame_style.py -q 2>/dev/null || echo "需检查 FrameStyle 测试"
```

### Green — 分五步实现

#### Step 1: Project.load() 添加 schema 严格验证（`core/project.py`）

在 `Project.load()` 中，对 JSON 数据中的顶层键和已知子对象键做校验：

**当前代码（L229-255）:**
```python
@classmethod
def load(cls, path: str) -> "Project":
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    proj = cls()
    proj.version = data.get("version", "1.0")
    # ... 所有字段使用 data.get() 读取，不检查多余键
```

**修改为:**
```python
@classmethod
def load(cls, path: str) -> "Project":
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ── Schema 严格验证 ──
    KNOWN_TOP_KEYS = {
        "version", "created_at", "name", "modified_at", "duration",
        "thumbnail_path", "source", "timeline", "cursor", "frame_style",
        "annotations", "audio_regions", "crop_region", "aspect_ratio",
        "cursor_events", "click_events", "monitor_offset", "frame_count",
    }
    unknown_keys = set(data.keys()) - KNOWN_TOP_KEYS
    if unknown_keys:
        raise ValueError(
            f"project.json 包含未知字段: {', '.join(sorted(unknown_keys))}。"
            f"项目格式不兼容，请使用支持的 Recordly 版本打开。"
        )

    KNOWN_CURSOR_KEYS = {"smooth", "trail", "ripple", "sway", "blur", "style"}
    cursor_data = data.get("cursor", {})
    unknown_cursor = set(cursor_data.keys()) - KNOWN_CURSOR_KEYS
    if unknown_cursor:
        raise ValueError(
            f"project.json cursor 字段包含未知键: {', '.join(sorted(unknown_cursor))}"
        )

    KNOWN_FRAMESTYLE_KEYS = {
        "background", "bg_color", "bg_gradient", "bg_wallpaper",
        "padding", "corner_radius", "shadow", "shadow_offset",
        "shadow_blur", "shadow_opacity",
    }
    frame_data = data.get("frame_style", {})
    unknown_frame = set(frame_data.keys()) - KNOWN_FRAMESTYLE_KEYS
    if unknown_frame:
        raise ValueError(
            f"project.json frame_style 字段包含未知键: {', '.join(sorted(unknown_frame))}"
        )

    # ── 加载逻辑（原有逻辑，使用 data.get() 提供默认值） ──
    proj = cls()
    proj.version = data.get("version", cls.VERSION)
    # ... 其余字段保持不变
```

> **关键设计:** 未知字段检测在展开 dataclass 之前执行，避免 TypeError。使用 `.get()` 为缺失 optional 字段提供默认值。

#### Step 2: 实现 bg_color 的 encode/decode 边界编解码（`core/project.py`）

**在 `Project.save()` 中 encode:**

`FrameStyle.bg_color` 运行时为 `tuple[int, int, int]`。`json.dump` + `asdict` 会将其序列化为 `[26, 26, 26]`（JSON 数组）。需要在保存前编码为 `#RRGGBB` 字符串。

修改 `Project.save()` 中 frame_style 的处理：

```python
def save(self, path: str):
    # ... 构建 data 字典 ...
    frame_style_dict = asdict(self.frame_style)
    # bg_color encode: tuple → "#RRGGBB"
    bg = self.frame_style.bg_color
    if isinstance(bg, tuple) and len(bg) == 3:
        frame_style_dict["bg_color"] = f"#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}"
    
    data = {
        # ...
        "frame_style": frame_style_dict,
        # ...
    }
    # ... 写入 JSON
```

**在 `Project.load()` 中 decode:**

修改 `_load_frame_style()` 函数，移除临时的 tuple→str 迁移兼容代码，改为严格的 `#RRGGBB` decode：

```python
import re

_HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')


def _load_frame_style(data: dict) -> FrameStyle:
    """加载 FrameStyle，bg_color 从 #RRGGBB 字符串解码为 tuple[int,int,int]"""
    bg_color = data.get("bg_color")
    if isinstance(bg_color, str):
        if not _HEX_COLOR_RE.match(bg_color):
            raise ValueError(f"无效的 bg_color 格式: '{bg_color}'，需要 #RRGGBB")
        r = int(bg_color[1:3], 16)
        g = int(bg_color[3:5], 16)
        b = int(bg_color[5:7], 16)
        data = {**data, "bg_color": (r, g, b)}
    elif isinstance(bg_color, (list, tuple)) and len(bg_color) == 3:
        # 运行时直接传入的 tuple（非 JSON 路径），保留
        data = {**data, "bg_color": tuple(bg_color)}
    else:
        data.pop("bg_color", None)  # 缺失时使用 dataclass 默认值
    
    return FrameStyle(**data)
```

> **注意:** 旧版 `_load_frame_style` 中的 `isinstance(bg_color, (list, tuple))` 分支保留作为运行时兼容（直接从代码创建 FrameStyle 时可能传入 tuple），但不再处理 JSON 中的旧数组格式。

#### Step 3: 更新 `core/frame_style.py` 的类型注解

确保 `bg_color` 的类型注解明确为 `tuple`：

```python
@dataclass
class FrameStyle:
    """帧样式配置"""
    background: str = "solid"
    bg_color: tuple = (26, 26, 26)  # ← 已经是 tuple，无需修改
    # ... 其余字段不变
```

> **当前代码已经是 `tuple = (26, 26, 26)`，无需修改。** 只需确认测试中验证此类型。

#### Step 4: 更新 `test_default_values_for_legacy_project`（`tests/test_data_persistence.py`）

**当前测试（L62-92）:** 使用包含旧字段的 JSON（`cursor` 有 `size/theme/color`，`frame_style` 有 `margin/radius`），期望加载不报错且使用默认值。

**修改为:** 测试两个行为：
1. **当前格式 JSON（不含未知字段）** → 成功加载，缺失 optional 字段使用默认值
2. **含未知字段的 JSON** → `Project.load()` 抛 `ValueError`

```python
def test_unknown_fields_rejected(self):
    """含未知 cursor/frame_style 字段的 JSON 被拒绝"""
    legacy = {
        "version": "1.1",
        "created_at": "2026-01-01",
        "name": "old_project",
        "modified_at": "2026-01-01",
        "duration": 10.0,
        "thumbnail_path": "",
        "source": None,
        "timeline": [],
        "cursor": {"smooth": True, "size": 24, "theme": "macos-dark"},  # size/theme 未知
        "frame_style": {"background": "solid", "margin": 40},  # margin 未知
        "annotations": [],
        "audio_regions": [],
        "crop_region": None,
        "aspect_ratio": "native",
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(legacy, f)
        path = f.name
    try:
        with pytest.raises(ValueError, match="未知"):
            Project.load(path)
    finally:
        os.unlink(path)

def test_missing_optional_fields_use_defaults(self):
    """缺失 optional 字段的当前格式 JSON 使用默认值"""
    current_format = {
        "version": "1.1",
        "created_at": "2026-01-01",
        "name": "minimal_project",
        "modified_at": "2026-01-01",
        "duration": 10.0,
        "thumbnail_path": "",
        "source": None,
        "timeline": [],
        "cursor": {},           # 全部 optional，使用默认值
        "frame_style": {},       # 全部 optional，使用默认值
        "annotations": [],
        "audio_regions": [],
        "crop_region": None,
        "aspect_ratio": "native",
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(current_format, f)
        path = f.name
    try:
        p = Project.load(path)
        assert p.cursor_events == []
        assert p.click_events == []
        assert p.monitor_offset == [0, 0]
        assert p._frame_count == 0
    finally:
        os.unlink(path)
```

#### Step 5: 添加 bg_color 编解码测试（`tests/test_project.py`）

```python
def test_bg_color_roundtrip_as_hex_string(self):
    """bg_color 在 JSON 中存储为 #RRGGBB，运行时为 tuple"""
    import re
    p = Project()
    p.frame_style.bg_color = (255, 128, 0)
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        p.save(path)
        
        # JSON 中验证格式
        with open(path) as f:
            data = json.load(f)
        assert re.match(r'^#[0-9A-Fa-f]{6}$', data["frame_style"]["bg_color"])
        assert data["frame_style"]["bg_color"] == "#ff8000"
        
        # 加载后运行时类型
        loaded = Project.load(path)
        assert isinstance(loaded.frame_style.bg_color, tuple)
        assert loaded.frame_style.bg_color == (255, 128, 0)
    finally:
        os.unlink(path)
```

### Refactor — 检查清单

- [ ] `_load_frame_style()` 不再处理旧版 tuple 迁移（`bg_color` JSON 中只接受 `#RRGGBB` 字符串）
- [ ] `KNOWN_*_KEYS` 常量集中定义，方便版本升级时对照
- [ ] `Project.VERSION = "1.1"` 保持不变

---

## 4. 接口/契约

### Project.load() 行为变更

| 场景 | 旧行为 | 新行为 |
|------|--------|--------|
| JSON 含未知顶层键 | 忽略（不报错） | `ValueError` 含字段名列表 |
| JSON cursor 含旧字段 (size/theme/color) | `TypeError` 崩溃 | `ValueError` "cursor 字段包含未知键" |
| JSON frame_style 含未知字段 (margin/radius) | `TypeError` 或静默忽略 | `ValueError` "frame_style 字段包含未知键" |
| JSON 缺失 cursor_events | 默认 `[]` | 默认 `[]`（不变） |
| JSON 缺失 frame_count | 默认 `0` | 默认 `0`（不变） |

### FrameStyle.bg_color 编解码契约

| 方向 | 格式 |
|------|------|
| 运行时 | `tuple[int, int, int]`，例如 `(26, 26, 26)` |
| JSON | `"#RRGGBB"` 字符串，例如 `"#1a1a1a"` |
| `Project.save()` | tuple → `f"#{r:02x}{g:02x}{b:02x}"` |
| `Project.load()` | 校验 `^#[0-9A-Fa-f]{6}$` → 解码为 tuple |

---

## 5. 数据模型变化

无新增字段。`FrameStyle` class 签名不变。

---

## 6. 测试指引

### 新增/修改测试

| 文件 | 测试 | 类型 |
|------|------|------|
| `tests/test_data_persistence.py` | `test_unknown_fields_rejected` | 新增 — 验证未知字段拒绝 |
| `tests/test_data_persistence.py` | `test_missing_optional_fields_use_defaults` | 修改 — 替代旧的 legacy 测试 |
| `tests/test_project.py` | `test_bg_color_roundtrip_as_hex_string` | 新增 — bg_color 编解码 |

### 回归测试

```bash
pytest tests/test_data_persistence.py -q -v
pytest tests/test_project.py -q -v
pytest tests/test_frame_style.py -q -v   # 如果存在
```

---

## 7. 验收标准

- [ ] `pytest tests/test_data_persistence.py -q` 全部通过
- [ ] `pytest tests/test_project.py -q` 全部通过
- [ ] `Project.load()` 对未知顶层字段抛 `ValueError` 并包含字段名
- [ ] `Project.load()` 对未知 cursor/frame_style 子字段抛 `ValueError`
- [ ] `Project.load()` 对缺失 optional 字段使用默认值
- [ ] `FrameStyle.bg_color` 运行时 `isinstance(x, tuple)` 为真
- [ ] `FrameStyle.bg_color` JSON 中匹配 `^#[0-9A-Fa-f]{6}$`
- [ ] 旧 CursorSettings (`size/theme/color`) 和旧 FrameStyle (`margin/radius`) 被安全拒绝

---

## 8. 边界情况与风险

| 场景 | 处理 |
|------|------|
| `bg_color` 为 None | `save()` 中 `isinstance(bg, tuple)` 为 False，跳过 encode；JSON 中值为 null |
| `bg_color` 为 `"#RRGGBB"` 字符串传入 FrameStyle dataclass | `_load_frame_style` 处理 str→tuple；`FrameStyle.__init__` 接受 str（dataclass 不做类型强制）；运行时行为需确认 |
| `bg_color` 为不合法 HEX 字符串（如 `#XYZ`） | `_load_frame_style` 中 `_HEX_COLOR_RE` 不匹配 → `ValueError` |
| JSON 中 `cursor` 为 null | `data.get("cursor", {})` 会返回 null（不是 {}）；需要在 `.get("cursor")` 后检查类型 |
| 项目目录中有旧格式 project.json | `Project.load()` 报错，UI 显示明确提示，当前会话状态不变（T04 实现 UI 层安全打开） |

**风险:** 严格拒绝未知字段后，任何手动编辑过 `project.json` 的项目可能无法打开。缓解：错误信息明确列出未知字段名，帮助用户定位问题。本轮不做迁移。

---

## 9. 任务验证命令

```bash
# 核心验证
pytest tests/test_data_persistence.py tests/test_project.py tests/test_frame_style.py -q -v

# 全量回归
pytest -q

# 手动验证 bg_color
python -c "
from core.project import Project
import tempfile, os
p = Project()
p.frame_style.bg_color = (100, 200, 50)
path = os.path.join(tempfile.mkdtemp(), 'test.json')
p.save(path)
import json
with open(path) as f: d = json.load(f)
print('JSON bg_color:', d['frame_style']['bg_color'])  # 应为 #64c832
p2 = Project.load(path)
print('Runtime bg_color:', p2.frame_style.bg_color)     # 应为 (100, 200, 50)
assert isinstance(p2.frame_style.bg_color, tuple)
print('OK')
"
```

---

## 关联文件

| 文件 | 操作 |
|------|------|
| `core/project.py` | `Project.load()` 添加 schema 验证 + `Project.save()` 添加 bg_color encode |
| `core/frame_style.py` | 确认 bg_color 类型注解（可能无需改动） |
| `tests/test_data_persistence.py` | 更新 `test_default_values_for_legacy_project` → `test_missing_optional_fields_use_defaults` + 新增 `test_unknown_fields_rejected` |
| `tests/test_project.py` | 新增 `test_bg_color_roundtrip_as_hex_string` |
