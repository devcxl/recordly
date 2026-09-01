## 审查报告 — PR #18

### 变更概述
- **PR:** #18 — T1: 创建 HomePage 首页组件
- **修改文件数:** 1（新增 `ui/home_page.py`，120 行）
- **新增组件:** `HomePage(QWidget)`
- **关联 Issue:** #16
- **风险等级:** 中

### 发现问题

#### [HIGH] `_record_btn` 样式不完整，违反暗色主题一致性要求
- **文件:** `ui/home_page.py:73-81`
- **问题:** "开始录制"按钮的样式表仅设置了 `font-size`、`padding`、`font-weight`，缺少 `background-color`、`color`、`border`、`border-radius` 及 hover/pressed 状态。在 #121212 暗色背景下，Qt 会回退到系统默认样式（通常为浅灰色），导致按钮与暗色主题不一致，也无法与 `_open_btn` 的完整样式形成视觉呼应。
- **对照验收标准:** "暗色主题样式与现有界面风格一致" — 不满足。
- **修复建议:**
  ```python
  self._record_btn.setStyleSheet(
      """
      QPushButton {
          background-color: #4A90D9;
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 15px;
          padding: 8px 24px;
          font-weight: bold;
      }
      QPushButton:hover {
          background-color: #5AA0E9;
      }
      QPushButton:pressed {
          background-color: #3A80C9;
      }
      """
  )
  ```
  使用 `#4A90D9`（与 `ProjectCard` hover 状态一致）作为主操作按钮的强调色，或其他适合暗色主题的深色调。

#### [MEDIUM] 按钮缺少 tooltip
- **文件:** `ui/home_page.py:70,83`
- **问题:** 设计文档 `recordly-ux-refactor.md` 第 122 行明确要求 "所有按钮有 tooltip + emoji 图标"，但 `_record_btn` 和 `_open_btn` 均未调用 `setToolTip()`。
- **修复建议:**
  ```python
  self._record_btn.setToolTip("开始新的屏幕录制")
  self._open_btn.setToolTip("打开已有的录制项目")
  ```

#### [MEDIUM] `_build_header` 方法过长（68 行）
- **文件:** `ui/home_page.py:44-111`
- **问题:** 方法从 `_build_header` 定义到 `return widget` 共 68 行，远超 50 行指导标准。按钮创建逻辑可抽取为独立方法。
- **修复建议:** 将两个按钮的创建抽取为 `_create_action_button(text, style, parent)` 工厂方法，或将每个按钮抽为独立方法（`_create_record_button` / `_create_open_button`）。

#### [LOW] 缺少模块级公开 API 声明
- **文件:** `ui/home_page.py`（模块尾）
- **问题:** 模块仅导出 `HomePage`，无 `__all__` 声明不影响功能，但不利于显式声明 API 边界。
- **修复建议:**
  ```python
  __all__ = ["HomePage"]
  ```

### 验收标准对照

| 验收标准 | 状态 | 备注 |
|---------|------|------|
| HomePage 可独立实例化，显示操作按钮和项目画廊 | ✅ | 构造函数接收 `ProjectManager`，内嵌 `ProjectGallery` |
| 三个信号正确发射 | ✅ | `record_requested` / `open_project_requested` / `project_opened` 均已定义并连接 |
| `refresh_projects()` 调用 `ProjectGallery.refresh()` | ✅ | 直接委托调用 |
| 暗色主题样式与现有界面风格一致 | ⚠️ | `_record_btn` 样式不完整，见 HIGH 问题 |
| 空项目状态引导文案 | ✅ | 委托给 `ProjectGallery`（已有 `_empty_label`） |

### 正面评价

- 信号定义和连接逻辑清晰，`_connect_signals` 独立方法职责单一
- 与 `ProjectGallery` 的集成方式正确（信号透传 + 委托刷新）
- 代码结构符合现有项目风格（`_setup_ui` / `_build_xxx` 模式）
- 语法检查通过

### 审查结论

- [ ] 通过 — 存在 1 个 HIGH 问题
- [x] 有条件通过 — 修复 HIGH 问题后可合并
- [ ] 不通过

**建议:** 修复 `_record_btn` 样式（HIGH）后 Approve。MEDIUM/LOW 问题可在后续迭代中处理。
