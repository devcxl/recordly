# 开发文档: T2 - 重构 MainWindow 双页架构与交互流程

**Project:** Recordly 交互与页面架构重构
**Task ID:** T2
**Slug:** main-window-refactor
**Issue:** #17
**类型:** fullstack
**Batch:** 2
**依赖:** T1 (#16)

## 1. 目标
重构 `MainWindow`，实现"首页 → 编辑器"双页架构，完整录制→编辑交互流程。

## 2. 前置条件
- T1 完成（`ui/home_page.py` 存在）
- HomePage 组件可导入：`from ui.home_page import HomePage`

## 3. 实现步骤

### 3.1 导入 HomePage
```python
from ui.home_page import HomePage
```

### 3.2 初始化顺序调整
`__init__` 中：
1. `_setup_window()` — 不变
2. `_setup_interfaces()` — 创建 `_editor_interface` + `_home_page`（不再是 `_project_interface`）
3. `_setup_navigation()` — 创建 stacked_widget（首页 index 0，编辑器 index 1）+ 菜单栏 + 工具栏
4. `_setup_tray()` — 不变
5. `_check_deps()` — 不变
6. `_update_ui_state()` — 不变

### 3.3 创建首页界面（替代 `_setup_project_interface`）
```python
def _setup_home_page(self):
    self._home_page = HomePage(self._project_manager, self)
    self._home_page.record_requested.connect(self._on_home_record)
    self._home_page.open_project_requested.connect(self._on_home_open_project)
    self._home_page.project_opened.connect(self._on_open_project)
```

### 3.4 重构 `_setup_navigation()`
- **菜单栏**：
  - 首页：文件(设置, 退出) | 帮助(关于)
  - 编辑器：文件(保存, 导出, 返回首页, 退出) | 帮助(关于)
  - 实现：创建所有菜单项，按页面 setVisible
- **工具栏**：创建所有按钮（当前 `_setup_editor_toolbar` 的逻辑），默认隐藏
- **QStackedWidget**：`_home_page` (index 0) + `_editor_interface` (index 1)

### 3.5 页面切换方法
```python
def _switch_to_home(self):
    self._toolbar.setVisible(False)
    self._home_page.refresh_projects()
    self._stacked_widget.setCurrentWidget(self._home_page)
    self._update_menu_for_page()

def _switch_to_editor(self):
    self._toolbar.setVisible(True)
    self._stacked_widget.setCurrentWidget(self._editor_interface)
    self._update_menu_for_page()

def _update_menu_for_page(self):
    is_home = self._stacked_widget.currentWidget() == self._home_page
    self._menu_save.setVisible(not is_home)
    self._menu_export.setVisible(not is_home)
    self._menu_back_home.setVisible(not is_home)
    self._menu_settings.setVisible(is_home)
```

### 3.6 录制流程重构
```python
def _on_home_record(self):
    """首页点击'开始录制' → 确认弹窗 → 最小化 → 开始录制"""
    reply = QMessageBox.question(
        self, "开始录制",
        "将开始屏幕录制。录制时窗口会最小化，你可以按系统快捷键停止录制。\n\n确定开始？",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
    )
    if reply == QMessageBox.Yes:
        self.showMinimized()
        QTimer.singleShot(500, self._toggle_record)  # 等最小化完成再开始
```

修改 `_on_recording_stopped`：
```python
def _on_recording_stopped(self):
    # ... 现有停止逻辑不变 ...
    self._auto_create_project()
    
    # ★ 修改 _on_auto_export_finished 末尾添加：
    # 导出完成后自动切换到编辑器
```

修改 `_on_auto_export_finished` 末尾：
```python
# 切换到编辑器并恢复窗口
self._switch_to_editor()
self.showNormal()
self.raise_()
```

### 3.7 返回首页
```python
self._menu_back_home = QAction("返回首页", self)
self._menu_back_home.triggered.connect(self._switch_to_home)
```

### 3.8 首页"打开项目"
```python
def _on_home_open_project(self):
    path, _ = QFileDialog.getOpenFileName(
        self, "选择项目文件", self.config.projects_dir,
        "Recordly 项目 (project.json)"
    )
    if path:
        self._on_open_project(path)
```

## 4. 需要删除的代码
- `_setup_project_interface()` 方法（替代为 `_setup_home_page()`）
- `_nav_toolbar` 相关代码（已被新的 _toolbar 替代）
- `_nav_edit_action` / `_nav_project_action` 及其互斥逻辑
- `_on_nav_page_changed()` 方法（替代为 `_update_menu_for_page()`）

## 5. 测试指引

### 5.1 手动测试流程
1. 启动软件 → 应显示首页，工具栏隐藏
2. 点击"开始录制" → 弹出确认对话框 → 确认 → 窗口最小化
3. 停止录制 → 窗口恢复 → 应显示编辑器，工具栏可见
4. 菜单"文件→返回首页" → 切换回首页，项目列表包含刚录制的项目
5. 点击项目卡片 → 进入编辑器
6. 编辑器所有按钮功能正常

### 5.2 回归测试
- 录制/停止功能正常
- 导出功能正常
- 播放控制功能正常
- 系统托盘功能正常
- 设置对话框正常

## 6. 验收标准
- [ ] 启动后默认显示首页，工具栏不可见
- [ ] 首页点击"开始录制"弹出确认对话框
- [ ] 确认后窗口最小化，开始录制
- [ ] 停止录制后自动创建项目并切换到编辑器，工具栏可见
- [ ] 首页点击项目卡片切换到编辑器
- [ ] 编辑器菜单"返回首页"切换到首页，项目列表已刷新
- [ ] 编辑器菜单"文件→导出"功能正常
- [ ] 工具栏所有按钮功能正常（录制/播放/导出/裁剪/音频）
- [ ] 菜单栏在首页和编辑器页面显示正确的菜单项

## 7. 注意事项
- `_on_auto_export_finished` 在后台线程完成时触发（ExportWorker），需要确保切页操作在主线程执行
- 首页的 `_project_manager` 与现有 `self._project_manager` 必须是同一实例
- 工具栏按钮引用（`_btn_record` 等）名称不变，只改变父容器
- 原有的 `_on_open_project` 方法保留，但不再接收来自 `_nav_project_action` 的调用
