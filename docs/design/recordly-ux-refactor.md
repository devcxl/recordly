# 技术方案: Recordly 交互与页面架构重构

**日期:** 2026-07-15
**状态:** Draft

## 1. 技术栈

| 层级 | 技术选型 | 理由 |
|------|---------|------|
| 前端 | PyQt5 | 现有技术栈，不引入新依赖 |
| 组件 | ProjectGallery, ProjectCard | 复用现有组件 |
| 新增组件 | HomePage (QWidget) | 首页容器 |

## 2. 架构设计

### 2.1 页面架构

当前：编辑器 (index 0) ↔ 项目文件 (index 1) 通过 QStackedWidget 切换
改为：**首页 (index 0) → 编辑器 (index 1)**，单向为主，可返回

```
QMainWindow
  ├─ QMenuBar
  │    ├─ 文件 (设置 / 返回首页 / 退出)    ← 按页面动态调整
  │    └─ 帮助 (关于)
  ├─ QToolBar (仅在编辑器页可见)
  │    ├─ 录制按钮
  │    ├─ 播放控制
  │    ├─ 帧/时间
  │    ├─ 导出/裁剪/音频
  │    └─ stretch → 返回首页按钮
  ├─ QStackedWidget (central)
  │    ├─ [0] HomePage          ← 默认页
  │    └─ [1] EditorInterface   ← 录制/编辑页
  └─ QStatusBar
```

### 2.2 模块划分

| 模块 | 职责 | 类型 |
|------|------|------|
| `ui/home_page.py` | 首页容器：操作按钮 + ProjectGallery | 新增 |
| `app/main_window.py` | 主窗口重构：双页切换、录制流程、菜单/工具栏 | 修改 |
| `ui/project_gallery.py` | 项目卡片画廊（不变） | 复用 |
| `ui/project_card.py` | 项目卡片（不变） | 复用 |
| `core/project_manager.py` | 项目持久化（不变） | 复用 |

### 2.3 页面切换数据流

```
[首页] 点击"开始录制"
  → 确认对话框
  → hide() / showMinimized()
  → Recorder.start_recording()
  → 停止录制
  → Recorder.stop_recording()
  → ExportWorker(src→mp4) 后台线程
  → _on_auto_export_finished()
    → ProjectManager.create_project()
    → _refresh_project_gallery()
    → _stacked_widget.setCurrentWidget(_editor_interface)  ★ 自动切换
    → showNormal() / raise()

[首页] 点击项目卡片
  → _on_open_project(path)
    → 加载项目数据
    → _stacked_widget.setCurrentWidget(_editor_interface)  ★ 切换

[编辑器] 菜单"返回首页"
  → _stacked_widget.setCurrentWidget(_home_page)
  → _refresh_project_gallery()
```

## 3. 接口设计

### 3.1 HomePage 组件

```python
class HomePage(QWidget):
    """首页组件"""

    # 信号
    record_requested = pyqtSignal()        # 用户点击"开始录制"
    open_project_requested = pyqtSignal()  # 用户点击"打开项目"（文件选择器）
    project_opened = pyqtSignal(str)       # 用户点击项目卡片 → 传递 project_path

    def __init__(self, project_manager: ProjectManager, parent=None): ...
    def refresh_projects(self): ...        # 刷新项目列表
```

### 3.2 MainWindow 菜单变更

| 页面 | 文件菜单 | 帮助菜单 |
|------|---------|---------|
| 首页 | 设置, 退出 | 关于 |
| 编辑器 | 保存, 导出, 返回首页, 退出 | 关于 |

工具栏仅在编辑器页可见，通过 `self._toolbar.setVisible(page == editor)` 控制。

## 4. 关键决策

| 决策 | 方案 | 理由 |
|------|------|------|
| 首页组件位置 | 新建 `ui/home_page.py` | 职责分离，MainWindow 只做编排 |
| ProjectGallery 复用 | HomePage 内嵌 ProjectGallery | 避免重复造轮子，卡片交互逻辑不变 |
| 工具栏可见性 | `setVisible()` 按页面切换 | 首页不需要工具栏控件 |
| 录制确认 | QMessageBox.question | 标准交互，无需自定义组件 |
| 自动切换编辑器 | 在 `_on_recording_stopped` 末尾 | 录制完成后无缝进入编辑 |
| 窗口最小化 | `self.showMinimized()` | 录制时窗口收起，避免遮挡屏幕 |

## 5. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 录制时窗口最小化后托盘可能无法恢复 | 中 | showNormal() + raise() 确保恢复 |
| ExportWorker 后台线程与 UI 线程竞争 compositor | 高 | 导出期间禁用录制按钮（已有逻辑） |
| 打开项目后视频帧未加载 | 低 | 已在 Out-of-Scope，后续迭代 |

## 6. 非功能需求实现方案

- 性能：页面切换仅操作 QStackedWidget.setCurrentWidget()，无 IO，< 10ms
- 可用性：所有按钮有 tooltip + emoji 图标，空项目状态有引导文案
