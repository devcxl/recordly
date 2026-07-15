## 审查报告

### 变更概述
- **PR**: #19 `feat/main-window-refactor` → `master`
- **Issue**: #17 — T2: 重构 MainWindow 双页架构与交互流程
- **修改文件数**：2
  - `app/main_window.py` — 重构双页架构、菜单、工具栏、录制流程
  - `ui/home_page.py` — 补充 `project_deleted` / `project_renamed` 信号转发
- **风险等级**：中

### 变更摘要

本次 PR 将 MainWindow 从"编辑器 ↔ 项目文件"双页改为"首页 → 编辑器"双页架构：

1. 新 `_setup_home_page()` 替代 `_setup_project_interface()`，使用 `HomePage` 组件
2. 移除"视图"菜单，文件菜单按页面动态显隐（首页：设置；编辑器：保存/导出/返回首页）
3. 工具栏仅在编辑器页可见，通过 `_switch_to_home` / `_switch_to_editor` 控制
4. 录制流程：首页确认弹窗 → 最小化 → QTimer 延迟开始录制 → 停止后自动导出 → 切换编辑器
5. 新增"帮助"菜单（关于）
6. 删除旧代码：`_nav_edit_action`、`_nav_project_action`、`_on_nav_page_changed`、`view_menu`

---

### 发现问题

**[HIGH] `_on_open_project` 未调用 `_switch_to_editor()`，导致工具栏和菜单可见性不更新**

- **文件**：`app/main_window.py`（PR 分支第 1092 行）
- **问题**：`_on_open_project` 在末尾直接调用 `self._stacked_widget.setCurrentWidget(self._editor_interface)` 切换页面，而未调用 `self._switch_to_editor()`。由于旧架构中工具栏始终可见，此代码在原系统中正确；但在新双页架构中，工具栏默认为隐藏状态，`setCurrentWidget` 不会触发任何可见性更新逻辑（`currentChanged` 信号在新代码中已无连接）。

  受影响的路径：**首页点击项目卡片** → `_on_open_project` → 编辑器显示但工具栏隐藏，菜单项仍为首页模式（"保存/导出/返回首页"不可见，"设置"仍可见）。

- **修复建议**：

```python
# app/main_window.py ~1091-1092，将：
        # 切换到编辑器界面
        self._stacked_widget.setCurrentWidget(self._editor_interface)

# 改为：
        # 切换到编辑器界面
        self._switch_to_editor()
```

  `_switch_to_editor()` 内部已完整处理工具栏可见性 + 菜单可见性更新，直接复用更为安全。

---

**[LOW] `ProjectGallery` 导入未使用**

- **文件**：`app/main_window.py`（PR 分支第 32 行）
- **问题**：`from ui.project_gallery import ProjectGallery` 在 MainWindow 中不再被使用（旧代码在 `_setup_project_interface` 中创建 `ProjectGallery` 实例，该方法已删除）。`HomePage` 内部自行管理 `ProjectGallery`。
- **修复建议**：移除该 import。

---

**[LOW] `_on_home_record` 提示文案与开发文档不一致**

- **文件**：`app/main_window.py`（PR 分支 `_on_home_record` 方法）
- **问题**：开发文档写的是"你可以按系统快捷键停止录制"，实际代码为"你可以通过托盘图标停止录制"。后者与实际行为（托盘图标停止）一致，属正向偏差，不要求修改。标注供信息对齐。

---

### 变更符合方案的部分 ✅

| 验收标准 | 状态 | 说明 |
|---------|------|------|
| 启动后默认显示首页，工具栏不可见 | ✅ | `_setup_navigation` 末尾设置 toolbar 隐藏 + 首页为 index 0 |
| 首页点击"开始录制"弹出确认对话框 | ✅ | `_on_home_record` 使用 `QMessageBox.question` |
| 确认后窗口最小化，开始录制 | ✅ | `showMinimized()` + `QTimer.singleShot(500, _toggle_record)` |
| 停止录制后自动创建项目并切换到编辑器 | ✅ | `_on_auto_export_finished` 中调用 `_switch_to_editor()` + `showNormal()` + `raise_()` |
| 首页点击项目卡片切换到编辑器 | ⚠️ | 见 [HIGH] 问题 — 切换发生但工具栏/菜单未更新 |
| 编辑器菜单"返回首页"切换到首页，项目列表已刷新 | ✅ | `_switch_to_home` 调用 `refresh_projects()` 再切换 |
| 编辑器菜单"文件→导出"功能正常 | ✅ | `self._menu_export` 连接 `self._on_export`，页面正确时可见 |
| 工具栏按钮功能正常 | ✅ | 按钮创建逻辑未变，仅在编辑器页可见 |
| 菜单栏按页面正确显示菜单项 | ✅ | `_update_menu_visibility` 按 currentWidget 判断 |

---

### 残留旧代码引用检查

| 旧引用 | 状态 |
|--------|------|
| `_project_interface` | ✅ 已完全移除 |
| `_nav_edit_action` | ✅ 已完全移除 |
| `_nav_project_action` | ✅ 已完全移除 |
| `_on_nav_page_changed` | ✅ 已完全移除 |
| `_setup_project_interface` | ✅ 已完全移除 |
| `_refresh_project_gallery` | ✅ 已完全移除（替换为 `_refresh_home_page`） |
| `view_menu`（"视图"菜单） | ✅ 已完全移除 |
| `_project_gallery` | ✅ 已完全移除 |

> 注意：当前工作目录 `app/main_window.py` 为 `master` 分支（含旧代码），以上检查基于 PR diff + worktree 分支源码。

---

### `home_page.py` 变更审查

```diff
+ project_deleted = pyqtSignal(str)
+ project_renamed = pyqtSignal(str, str)
...
+ self._gallery.project_deleted.connect(self.project_deleted.emit)
+ self._gallery.project_renamed.connect(self.project_renamed.emit)
```

- ✅ 信号链路：`ProjectCard` → `ProjectGallery` → `HomePage` → `MainWindow`
- ✅ `MainWindow` 中 `_on_project_deleted` / `_on_project_renamed` 已改为调用 `_refresh_home_page()`

---

### 测试建议

- **现有测试**: `tests/test_main_window.py` 包含 7 个单元测试，覆盖 `_update_frame_counter`、`_create_playback_controller`、`_get_recording_duration`、`_on_recording_started` error 恢复、timeline 信号幂等性、zoom clip 选择、cursor 配置等。不涉及本次重构的方法。
- **建议补充**：
  1. `_switch_to_home` / `_switch_to_editor` 的 toolbar/菜单状态验证（方法级 mock 测试，无需实际 QWidget）
  2. `_on_home_record` 确认弹窗的逻辑分支测试（Yes / No 两种路径）
  3. `_on_home_open_project` 文件选择取消路径（空 path 不调用 `_on_open_project`）
  4. `_on_open_project` 调用 `_switch_to_editor()` 的验证（修复后）

---

### 审查结论

- [ ] 通过 — 无 Critical/High 问题
- [ ] 有条件通过 — 仅 Medium 及以下问题
- [x] **不通过 — 存在 High 问题需修复**

**必须修复**：`_on_open_project` 中的 `setCurrentWidget` 替换为 `_switch_to_editor()`，确保从首页点击项目卡片时工具栏和菜单可见性正确更新。

修复后可直接合并，无需二次审查。
