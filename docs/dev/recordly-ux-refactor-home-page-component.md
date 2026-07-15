# 开发文档: T1 - 创建 HomePage 首页组件

**Project:** Recordly 交互与页面架构重构
**Task ID:** T1
**Slug:** home-page-component
**Issue:** #16
**类型:** frontend
**Batch:** 1
**依赖:** 无

## 1. 目标
创建 `ui/home_page.py`，提供首页组件 — 操作按钮 + 项目画廊。

## 2. 前置条件
- 无（独立组件，不依赖其他任务）

## 3. 实现步骤

### 3.1 组件结构
- 文件：`ui/home_page.py`
- 类：`HomePage(QWidget)`
- 布局：VBoxLayout
  - 顶部：标题 label "Recordly" + 按钮 HBoxLayout
  - 下方：`ProjectGallery` 嵌入

### 3.2 信号定义
```python
class HomePage(QWidget):
    record_requested = pyqtSignal()        # 开始录制
    open_project_requested = pyqtSignal()  # 打开已有项目（文件选择器）
    project_opened = pyqtSignal(str)       # 点击项目卡片 → 项目路径
```

### 3.3 按钮连接
- "开始录制"按钮 → `self.record_requested.emit()`
- "打开项目"按钮 → `self.open_project_requested.emit()`
- ProjectGallery.project_opened → `self.project_opened.emit(path)`

### 3.4 样式
暗色主题：背景 #121212，按钮与当前 ToolButton 风格一致，标题白色大字。

## 4. 接口/契约

### 4.1 HomePage 公共方法
| 方法 | 参数 | 说明 |
|------|------|------|
| `__init__` | `project_manager: ProjectManager, parent=None` | 构造函数 |
| `refresh_projects()` | 无 | 调用 `self._gallery.refresh()` |

### 4.2 信号
| 信号 | 参数 | 触发时机 |
|------|------|---------|
| `record_requested` | 无 | 点击"开始录制" |
| `open_project_requested` | 无 | 点击"打开项目" |
| `project_opened` | `str` (project_path) | 点击项目卡片 |

## 5. 测试指引

### 5.1 单元测试
- 实例化 HomePage，验证三个按钮存在
- 模拟点击"开始录制"，验证 record_requested 信号发射
- 模拟点击"打开项目"，验证 open_project_requested 信号发射

## 6. 验收标准
- [ ] `HomePage` 可独立实例化，显示操作按钮和项目画廊
- [ ] 三个信号正确发射：record_requested、open_project_requested、project_opened
- [ ] `refresh_projects()` 调用 `ProjectGallery.refresh()`
- [ ] 暗色主题样式与现有界面风格一致

## 7. 注意事项
- 不要修改 ProjectGallery / ProjectCard 的代码
- 信号命名遵循现有风格（snake_case + pyqtSignal）
- ProjectGallery 内部已处理空状态显示
