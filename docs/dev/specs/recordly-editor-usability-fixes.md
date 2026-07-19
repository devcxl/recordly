# 编辑器可用性修复与快捷键配置 — 技术方案

**日期：** 2026-07-19  
**状态：** Draft  
**关联：** Parent Issue #105 / `docs/prd/recordly-editor-usability-fixes.md`

---

## 1. 目标、范围与结论

本方案在现有 Python 3.11 + PyQt5、`TimelineWidget` 命令栈和 `AppConfig` 配置体系上增量实现：

1. X 快捷键按轨道、片段顺序切割播放头覆盖的非 zoom 片段，因此覆盖 `video`、`audio`、`audio_extra`。
2. 所有通过 `_split_clip()` 发起的切割完成后选中右半段；右半段可按既有移动路径拖动并写入 `MoveClipCommand`。
3. 新增纯 Python 的快捷键注册表；设置页以草稿方式编辑 12 个绑定，保存到现有 `QSettings("Recordly", "Recordly")`，关闭设置后立即重新绑定。

不新增 HTTP/IPC 接口、项目 JSON 字段、领域模型或第三方依赖；不修改 `SplitClipCommand`、`MoveClipCommand` 的数据结构。

### 1.1 本轮不做

- 多选、跨轨移动、片段重叠检测、快捷键预设、导入导出、JKL、zoom 片段的 X 切割。
- 将主录制音轨的独立时间线编辑语义扩展到导出管线；详见 [风险 R1](#91-风险与缓解)。
- 通过全局 `eventFilter` 拦截键盘事件，或引入新的 Controller/事件总线。

### 1.2 已确认的现状与根因

| 项目 | 现状 | 方案结论 |
|---|---|---|
| X 切割 | `_find_playhead_video()` 同时限制 `Track.type` 和 `Clip.type` 为 `video` | 改为 `_find_playhead_clip()`，只排除 zoom，保留严格开区间。 |
| 右半段拖动 | `SplitClipCommand` 在 `clip_index + 1` 插入右段；`_split_clip()` 未更新选择态 | 切割成功后设置 `_selected_track` 与 `_selected_clip = clip_index + 1`。 |
| 拖动路径 | 片段主体点击已记录 `_drag_orig_start/end/source_*`；移动可向左右且只由时间线边界 clamp | 不改 `_hit_test`、`_drag_state` 或 `MoveClipCommand`。共享边缘仍是 resize 命中区，右半段主体点击/拖动不受影响。 |
| 快捷键 | Timeline 的 `keyPressEvent()` 与 MainWindow 的三个 `QShortcut`、菜单提示均硬编码 | 键位和显示文本全部从注册表读取；动作处理函数保持在原组件。 |

`_hit_edge()` 在两个刚切开的片段共享边界上会优先命中左段右边缘，这是既有且符合“边缘拖拽”的语义，不是右段主体无法移动的根因。本轮不改变边缘优先级，测试会覆盖右段主体的点击、向左和向右拖动。

---

## 2. 技术选型与架构原则

| 决策 | 选择 | 理由 |
|---|---|---|
| 快捷键定义 | `core/shortcuts.py` 中的静态注册表 + 纯字符串校验 | 12 个 action 的 ID、显示名、分类、默认键位和生效范围只有一个事实源；`core` 不导入 PyQt。 |
| 键位格式 | `QKeySequence.PortableText` 字符串 | 可写入 `QSettings`，跨平台稳定；显示时转 `NativeText`。例如方向键持久化为 `Left`/`Right`，而不是 Unicode 箭头。 |
| 配置归属 | `AppConfig.shortcuts: dict[str, str]`，按 `shortcuts/<action_id>` 写入现有 `QSettings` | 快捷键是机器级用户偏好，不属于项目；复用现有配置加载、保存和测试模式。 |
| 窗口级触发 | MainWindow 按实际键序列分组创建 `QShortcut`，使用 `Qt.WindowShortcut` 且关闭 auto-repeat | 延续 ADR `2026-07-19-undo-redo-shortcuts.md` 的安全边界，支持设置后立即重绑。 |
| 时间线触发 | `TimelineWidget.keyPressEvent()` 将事件规范化后查询注册表 | 保持 Timeline 焦点边界，不使用全局监听；X/S/删除/裁剪/微移仍只在时间线获得焦点时生效。 |
| 设置修改 | `SettingsDialog` 使用本地草稿，点击窗口“保存”时一次性校验、持久化、应用 | 与现有设置窗口的保存/取消语义一致；取消不会部分修改快捷键。 |

`QShortcut.setKey()` 支持在运行时更换 `QKeySequence`；`Qt.WindowShortcut` 仅在父窗口所属的活动顶层窗口中触发。本方案继续使用这两个 Qt 机制，不以 `QAction` 或 `eventFilter` 处理输入。

---

## 3. 快捷键注册表、数据模型与持久化

### 3.1 `core/shortcuts.py`

该模块为纯 Python 模块，不能导入 PyQt、`AppConfig`、`MainWindow` 或 `TimelineWidget`。它只表达动作目录、当前绑定和冲突校验；Qt 键盘事件解析留在 UI 层。

```python
@dataclass(frozen=True)
class ShortcutAction:
    action_id: str
    display_name: str
    category: str
    default_keys: str          # QKeySequence.PortableText
    scope: Literal["window", "timeline"]


@dataclass(frozen=True)
class ShortcutValidation:
    ok: bool
    code: str | None = None
    conflicting_action_id: str | None = None


class ShortcutRegistry:
    def actions(self, scope: str | None = None) -> tuple[ShortcutAction, ...]: ...
    def binding(self, action_id: str) -> str: ...
    def bindings(self) -> dict[str, str]: ...
    def validate(self, action_id: str, portable_text: str) -> ShortcutValidation: ...
    def replace_bindings(self, bindings: Mapping[str, str]) -> ShortcutValidation: ...
    def reset_binding(self, action_id: str) -> ShortcutValidation: ...
    def reset_all(self) -> None: ...
```

`validate()` 忽略同一 `action_id` 当前占用的键位；其他 action 使用相同规范化字符串即为冲突。`replace_bindings()` 必须先完整校验，再替换内存映射，避免半更新。

### 3.2 固定 action 目录

| action_id | 显示名称 | 分类 | `scope` | 默认 PortableText | 处理器 |
|---|---|---|---|---|---|
| `play_pause` | 播放/暂停 | 播放控制 | `window` | `Space` | `MainWindow._on_play_toggle` |
| `undo` | 撤销 | 全局 | `window` | `Ctrl+Z` | `MainWindow._on_undo` |
| `redo` | 重做 | 全局 | `window` | `Ctrl+Shift+Z` | `MainWindow._on_redo` |
| `redo_alt` | 重做（备用） | 全局 | `window` | `Ctrl+Y` | `MainWindow._on_redo` |
| `split_at_playhead` | 在播放头处切割 | 时间线编辑 | `timeline` | `X` | `TimelineWidget.split_at_playhead` |
| `split_selected` | 切割选中片段 | 时间线编辑 | `timeline` | `S` | `TimelineWidget.split_selected` |
| `delete_clip` | 删除选中片段 | 时间线编辑 | `timeline` | `Delete` | `TimelineWidget.delete_selected` |
| `delete_clip_alt` | 删除选中片段（备用） | 时间线编辑 | `timeline` | `Backspace` | `TimelineWidget.delete_selected` |
| `trim_in` | 裁剪入点 | 时间线编辑 | `timeline` | `I` | `TimelineWidget.trim_in` |
| `trim_out` | 裁剪出点 | 时间线编辑 | `timeline` | `O` | `TimelineWidget.trim_out` |
| `nudge_left` | 微移左移 0.5s | 时间线编辑 | `timeline` | `Left` | `TimelineWidget.nudge_selected(-0.5)` |
| `nudge_right` | 微移右移 0.5s | 时间线编辑 | `timeline` | `Right` | `TimelineWidget.nudge_selected(0.5)` |

`scope` 是运行时路由元数据，不是项目数据。两个 redo 和两个 delete action 保持不同 `action_id`，使用户可分别配置两个备用入口，但它们可复用同一个处理器。

### 3.3 `AppConfig` 与 QSettings

`AppConfig` 新增 `shortcuts` 字段，默认值由 `ShortcutRegistry` 的目录生成，不能写成可变的 dataclass 共享默认值。

加载与保存契约：

| 时机 | 行为 |
|---|---|
| `AppConfig.load()` | 对目录中的每一个 action 读取 `shortcuts/<action_id>`；缺失值使用目录默认值。UI 层用 `QKeySequence` 解析失败或为空时回退默认值，不中断应用启动。 |
| `AppConfig.save()` | 写入全部 12 个 `shortcuts/<action_id>` 与既有配置，并调用 `sync()`；不写 project.json。 |
| 单行恢复默认 | 只在设置草稿中替换目标 action 为 `default_keys`，仍须通过冲突校验。 |
| 全部恢复默认 | 草稿整体替换为 12 个唯一的默认值，二次确认后等待窗口“保存”统一落盘。 |

手工修改 QSettings 造成的重复绑定不在设置页正常路径中：启动不崩溃，运行时按 action 目录顺序分发同一个键序列的所有 action；下次在设置页保存前，`replace_bindings()` 会拒绝未消除的重复项。这满足 PRD 的“运行时两个动作都生效”，同时正常 UI 永远不产生冲突。

### 3.4 内部错误码与用户反馈

本功能没有网络 API；下表为注册表/设置对话框的同步结果码，而非 HTTP 错误码。

| 代码 | 触发条件 | UI 行为 | 状态变更 |
|---|---|---|---|
| `SHORTCUT_UNKNOWN_ACTION` | action_id 不在固定目录 | 开发期断言/记录，不对用户展示 | 不改草稿、配置或运行时绑定。 |
| `SHORTCUT_EMPTY_SEQUENCE` | 捕获到纯修饰键或空序列 | “请按下包含非修饰键的快捷键” | 不改草稿。 |
| `SHORTCUT_INVALID_SEQUENCE` | `QKeySequence` 无法解析持久化值或捕获值 | 加载时静默回退默认；编辑时提示重新输入 | 加载不写回，编辑不改草稿。 |
| `SHORTCUT_CONFLICT` | 新键位已被另一个 action 占用 | “与「{display_name}」冲突，请重新设置” | 不改草稿、QSettings 或运行时绑定。 |

### 3.5 设置页交互

`SettingsDialog` 新增“快捷键” Tab，建议窗口由固定 `520 × 420` 改为最小 `720 × 560` 并允许纵向伸缩。Tab 内使用可滚动表格：分类、操作、当前快捷键、编辑、恢复默认；底部提供“恢复全部默认”。

`ShortcutCaptureDialog` 可作为 `settings_dialog.py` 内的私有 `QDialog`，避免新增 UI 模块：

1. 双击快捷键单元格或点击“编辑”打开对话框，焦点固定在捕获区域。
2. `keyPressEvent()` 忽略单独的 Ctrl/Alt/Shift/Meta；Esc 取消；其他按键用 `QKeySequence(modifiers | key)` 规范化为 PortableText，并用 NativeText 回显。
3. 点击捕获框“确定”时调用草稿注册表的 `validate()`；冲突或非法不关闭对话框。
4. 捕获成功只更新设置窗口草稿。点击主设置窗口“保存”时，将草稿交给实际注册表和 `AppConfig.shortcuts`，调用 `AppConfig.save()`，再 `accept()`；“取消”丢弃草稿。

这使文本输入控件永远不会被编辑器快捷键抢占：窗口级快捷键继续复用 `_is_editor_active_and_safe()`，时间线快捷键只在 Timeline 获得焦点时收到事件，捕获对话框自身为 modal。

---

## 4. 状态与数据流

### 4.1 应用启动与配置更新

```text
AppConfig.load()
  └─ QSettings shortcuts/<action_id> × 12 + 默认回退
       └─ MainWindow 创建 ShortcutRegistry(config.shortcuts)
            ├─ TimelineWidget.set_shortcut_registry(registry)
            └─ _rebind_window_shortcuts()
                 └─ 按 PortableText 分组创建 QShortcut(WindowShortcut, autoRepeat=False)

设置窗口保存
  └─ 草稿完整校验 → registry.replace_bindings()
       → config.shortcuts = registry.bindings() → config.save() → QSettings.sync()
       → MainWindow._rebind_window_shortcuts()
       → _refresh_undo_redo_state() 更新菜单/ToolTip 显示的键位
```

窗口级分组意味着一个键序列只创建一个 `QShortcut`；激活时按 action 目录顺序调用该组 handler。正常设置页不会保存重复值，分组仅保证外部重复配置不会触发 Qt 的 ambiguous shortcut 行为。

### 4.2 时间线快捷键路由

```text
QKeyEvent（TimelineWidget 有焦点）
  → 将 modifiers + key 转为 PortableText
  → registry.actions(scope="timeline") 的绑定匹配
  → action_id → 已有 Timeline 行为
       split_at_playhead → split_at_playhead()
       split_selected    → _split_clip(selected_track, selected_clip)
       delete_*          → delete_selected()
       trim_in/out       → trim_in() / trim_out()
       nudge_*           → nudge_selected(±0.5)
  → 消费事件；无匹配则 super().keyPressEvent(event)
```

`nudge_selected()` 必须在构造 `MoveClipCommand` 时显式传入当前 `source_start/source_end` 作为 old/new 值。原因是现有方向键构造器依赖默认 `0.0/None`，会在已经拆分或变速的片段上破坏 ADR `2026-07-17-timeline-trim-source-sync.md` 的 source 映射。本调整不改命令数据结构，只保证配置化迁移不保留该数据回归。

### 4.3 X 切割音频与选择态

```text
split_at_playhead action
  → TimelineWidget._find_playhead_clip()
       按 track_index 升序，再按 clip_index 升序
       跳过 track.type == "zoom" 或 clip.type == "zoom"
       命中条件：clip.start < playhead < clip.end
  ├─ 无命中：status_message("播放头下无片段")；模型与 undo/redo 栈不变
  └─ 命中：(track_index, clip_index)
       → _split_clip(track_index, clip_index)
            → _push_undo(SplitClipCommand(...))
                 → execute(): 复用现有 speed/source 换算，插入右段
                 → clips_changed
                      → MainWindow._on_clips_changed()
                      → compositor、音频区域、undo/redo UI 同步
            → _select_clip(track_index, clip_index + 1)
```

严格开区间继续阻止在片段边缘生成零长度片段。`SplitClipCommand` 保持唯一的 source 映射实现：

```text
split_source = source_start + (playhead - start) × speed
```

因此 `audio` 和 `audio_extra` 的分割与视频一样保留 `source_start`、`source_end` 和 `speed`；切割本身一键 undo/redo。

选择态是瞬态 UI：首次切割自动选中右半段；undo 后右段消失，既有 `_validate_selection()` 清除选择；redo 不强制重新选中，不把选择信息塞入命令对象或项目数据。

### 4.4 右半段拖动

```text
鼠标按下右半段主体
  → _hit_test() → selected = (track, right_index)
  → _drag_state = "move"，保存 _drag_orig_*（含 source）
鼠标移动
  → 计算原始 start + dt，仅按 [0, duration - clip_duration] clamp
  → 既有视频同轨 8px 吸附可修正位置，不阻止左/右移动
鼠标释放
  → _make_move_cmd() 生成 MoveClipCommand（完整 source 字段）
  → 进入 undo 栈，clips_changed 一次
```

不新增重叠检查；右段越过左段是允许的。`source_start/source_end` 在纯移动中保持不变，故素材时间与片段内相对位置不变。

---

## 5. 模块边界与预计影响

| 模块 | 文件 | 职责 | 不负责 |
|---|---|---|---|
| 快捷键目录/校验 | `core/shortcuts.py`（新增） | action 元数据、默认绑定、映射快照、冲突校验 | PyQt 事件、QSettings、业务 handler。 |
| 配置持久化 | `app/config.py` | `shortcuts` 加载、默认回退、保存和 `sync()` | UI 捕获、冲突提示。 |
| 快捷键设置 UI | `ui/settings_dialog.py` | 草稿、表格、捕获、恢复默认、错误提示 | 创建 `QShortcut`、执行编辑动作。 |
| 窗口级路由 | `app/main_window.py` | `QShortcut` 生命周期、焦点守卫、全局 handler 分发、菜单/ToolTip 文本刷新 | 时间线命令细节、键位持久化规则。 |
| 时间线路由与切割 | `ui/timeline.py` | Timeline 键位匹配、非 zoom 查询、右段选择、nudge source 保留 | QSettings、播放控制、导出策略。 |
| 命令与项目 | `core/commands.py`、`core/project.py` | 保持现有 split/move/JSON 行为 | 本轮不修改。 |

预计新增/修改生产文件为 5 个：`core/shortcuts.py`、`app/config.py`、`ui/settings_dialog.py`、`app/main_window.py`、`ui/timeline.py`。测试位于既有 `tests/test_config.py`、`tests/test_main_window.py`、`tests/test_timeline.py`，以及新增 `tests/test_shortcuts.py`。

---

## 6. 内部接口契约

| 提供方 | 接口 | 输入 | 输出/副作用 | 失败语义 |
|---|---|---|---|---|
| `ShortcutRegistry` | `binding(action_id)` | 已注册 ID | PortableText 字符串 | 未知 ID 为 `SHORTCUT_UNKNOWN_ACTION`。 |
| `ShortcutRegistry` | `validate(action_id, keys)` | ID、非空规范化字符串 | `ShortcutValidation` | 返回 `EMPTY`、`INVALID` 或 `CONFLICT`，不修改状态。 |
| `ShortcutRegistry` | `replace_bindings(bindings)` | 12 个 action 的完整映射 | 原子替换内存映射 | 任一非法/冲突则整批不替换。 |
| `TimelineWidget` | `set_shortcut_registry(registry)` | 只读/共享 registry | 后续 `keyPressEvent` 使用最新映射 | 初始化前使用默认目录，不能抛给用户。 |
| `TimelineWidget` | `split_at_playhead()` | 无 | 成功切割并选择右段，或发状态消息 | 无目标时不发 `clips_changed`、不改变选择或历史。 |
| `MainWindow` | `_rebind_window_shortcuts()` | 当前 registry | 销毁旧窗口级绑定、创建新分组绑定 | 无效持久化值已在配置加载时回退。 |
| `SettingsDialog` | 快捷键 Tab 保存 | 草稿绑定 | 复制到 registry/config，`config.save()` 后 `Accepted` | 校验失败留在对话框并展示对应提示。 |

本地桌面功能不定义请求/响应 JSON、HTTP 状态码或外部版本协商协议。

---

## 7. 迁移与兼容性

1. **用户配置兼容。** 旧版本没有 `shortcuts/*` 键；缺失即使用本方案目录的默认值，无迁移脚本。首次成功保存会写入 12 个键。
2. **持久化范围。** 快捷键仅存在 QSettings，不进入 `project.json`，复制/打开旧项目不会改变快捷键；符合 ADR-006 的项目 JSON 向后兼容原则。
3. **行为兼容。** 默认值保持现有 Space、Ctrl+Z、Ctrl+Shift+Z、Ctrl+Y、X、S、Delete、Backspace、I、O、Left、Right 行为。X 无目标的状态栏文案从“播放头下无视频片段”统一为“播放头下无片段”。
4. **命令兼容。** 继续复用 `SplitClipCommand` 和 `MoveClipCommand`，undo/redo 栈、`clips_changed` 和 source 映射均不变；不改 Clip/Track schema。
5. **平台兼容。** 保存 PortableText，显示 NativeText；由 Qt 处理 macOS 上 Cmd/Ctrl 映射，未添加系统判断。

### 7.1 ADR 兼容性检查

| ADR | 结论 |
|---|---|
| `005-home-editor-dual-view.md` | 窗口级动作仍经 `_is_editor_active_and_safe()` 限定编辑器页，首页不触发。 |
| `006-data-persistence-json.md` | 不增加 project.json 字段；用户偏好留在 QSettings。 |
| `007-project-session-recording-export-controllers.md` | `MainWindow` 只做 UI 编排；注册表不持有 Controller 或业务状态。 |
| `2026-07-17-timeline-trim-source-sync.md` | Split 复用既有 source 公式；nudge 补传 source 字段，避免破坏其不变量。 |
| `2026-07-19-timeline-interaction-routing-and-snapping.md` | Space/undo/redo 继续 WindowShortcut+守卫；Timeline 编辑动作继续在 widget 内处理；8px 吸附不变。 |
| `2026-07-19-undo-redo-shortcuts.md` | 保留 `QShortcut` 而非 `QAction` 输入处理；菜单仅展示当前绑定。 |

无冲突 ADR。

---

## 8. 测试策略与验收

### 8.1 自动化测试

| 范围 | 用例 |
|---|---|
| `tests/test_shortcuts.py` | 目录恰有 12 个唯一 ID；默认键位唯一；按 scope 查询；同一 action 覆盖自身旧键位允许；跨 action 冲突拒绝；单行/全部恢复默认；整批替换原子性。 |
| `tests/test_config.py` | 缺失 `shortcuts/*` 回退默认；12 个改动后的 PortableText 往返 QSettings fake；非法值回退默认；旧配置字段继续加载。 |
| `tests/test_timeline.py` | X 在 `audio`、`audio_extra` 和 `video` 各自正确切割；按轨道/片段顺序取第一个；zoom 排除；边界不切；无目标不改状态且文案正确；S 切音频无退化；X 自定义为 K 后 K 生效、X 不生效。 |
| `tests/test_timeline.py` | 切割后选中右段；右段主体可点击高亮并向左、向右拖动；释放只入一个 `MoveClipCommand`；undo/redo 恢复；source 字段保持；nudge 已拆分片段不重置 source。 |
| `tests/test_main_window.py` | 窗口级 binding 使用 `WindowShortcut`、关闭 auto-repeat；安全守卫拦截首页/非活跃窗口/modal/popup/输入焦点；设置保存后旧键失效、新键触发；undo/redo 菜单和 ToolTip 展示当前主/备用键位。 |
| `tests/test_main_window.py` / 设置测试 | 快捷键 Tab 显示 12 行；捕获 Ctrl+Shift+K；纯修饰键拒绝；冲突弹窗并保留草稿；单行恢复、全量恢复二次确认；取消不修改 config/registry；保存后调用重绑。 |

### 8.2 手工验收

1. 打开含 video、audio、audio_extra 的项目，分别把播放头置于片段内部并触发 `split_at_playhead`；确认右段被选中、source 分界正确、undo/redo 正常。
2. 切割视频后点击右段中部，分别向左、向右拖动；确认不被左段阻挡、不异常截断，保存重开后位置保持。
3. 在设置中把 X 改为 K，保存并关闭；K 切割、X 不再切割。重启应用后仍为 K。
4. 尝试把 K 分配给已有动作；确认提示冲突且原绑定不变。验证单行恢复和全部恢复默认。
5. 在项目名称等输入框、设置/导出弹窗和首页按窗口级快捷键；确认不控制播放、撤销或重做。

### 8.3 验证命令

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_shortcuts.py tests/test_config.py tests/test_timeline.py tests/test_main_window.py
QT_QPA_PLATFORM=offscreen pytest -q
git diff --check
```

---

## 9. 风险、假设与不确定项

### 9.1 风险与缓解

| ID | 风险 | 缓解 |
|---|---|---|
| R1 | 现有导出器根据 video clips 裁剪原始录制音频；普通 `audio` Track 的切割当前不单独驱动导出 | 本期验收限定为 Timeline 模型、source 数据和 undo/redo 正确；若产品要求“只切音频即改变导出”，需新 Issue 设计原声轨与视频轨的独立导出语义。 |
| R2 | 快捷键配置化遗漏菜单、ToolTip 或任一硬编码分支 | action 目录驱动输入绑定与展示，测试遍历完整目录并验证默认行为。 |
| R3 | QSettings 被手工写入非法或重复键位 | 非法值加载回退默认；重复值启动不崩溃、运行时确定性分发，设置页保存前强制消除冲突。 |
| R4 | 设置取消造成运行时快捷键提前改变 | 捕获和恢复都只改草稿；仅主设置窗口保存后替换实际 registry。 |
| R5 | 方向键迁移重置已拆分片段的 source 字段 | 用 `nudge_selected()` 显式传递 old/new source 字段，并加回归测试。 |
| R6 | 设置 Tab 在小窗口或高 DPI 下不可用 | 取消固定小尺寸，使用最小尺寸、滚动表格和布局伸缩。 |

### 9.2 假设与待确认项

1. 当前有效轨道类型为 `video`、`audio`、`audio_extra`、`zoom`；为满足“仅排除 zoom”和未来非 zoom 可切片段的确定性规则，`_find_playhead_clip()` 不按 video/audio 再过滤。若 text/camera 轨道未来需要不可切割语义，应新增显式 `is_splittable` 领域属性并单独决策。
2. 本期“音频可切割”验收是片段与 source 区间操作正确，不改变 R1 所述现有主录制音频导出规则。
3. 一个 QKeySequence 只捕获一个组合键，不支持 Emacs 式多步 chord；PRD 的“下一次按键组合”与此一致。
4. 外部重复配置的多动作顺序为固定 action 目录顺序；正常用户不应依赖该异常状态，因为设置 UI 会拒绝它。

---

## 10. 实施 DAG 建议

每项为单人约 2–4 小时的垂直切片：

```text
T1  快捷键目录、校验与 QSettings 持久化
 ├─ T2  设置页快捷键 Tab、捕获与恢复默认
 ├─ T3  MainWindow 窗口级重绑、菜单/ToolTip 刷新
 └─ T4  Timeline 配置路由、音频切割、右段选择与 nudge source 修复
      \         |         /
       └────────┴────────┘
                    ↓
T5  端到端 GUI 回归、重启持久化与手工验收
```

| 任务 | 依赖 | 交付与完成条件 |
|---|---|---|
| T1 | 无 | `core/shortcuts.py`、`AppConfig.shortcuts` 与单元测试；旧 QSettings 缺失键回退默认。 |
| T2 | T1 | 12 行表格、捕获、冲突提示、单行/全量恢复、取消不落盘的 GUI 测试。 |
| T3 | T1 | 运行时 WindowShortcut 重绑、焦点守卫和动态菜单/ToolTip 的测试。 |
| T4 | T1 | Timeline 路由替代硬编码；audio/audio_extra 切割、右段选中/拖动、nudge source 回归测试。 |
| T5 | T2、T3、T4 | offscreen 定向/全量测试通过，完成第 8.2 节手工验收。 |
