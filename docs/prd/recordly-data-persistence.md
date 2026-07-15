# PRD: 录制数据持久化与编辑器工具栏精简

**日期:** 2026-07-15
**状态:** Draft

## 1. 概述

### 1.1 问题陈述
当前存在两个严重问题：
1. **录制数据丢失**：录制完成后自动创建的项目只保存了 name、duration、source 三个字段。cursor_events（光标轨迹）、click_events（点击事件）、camera（自动缩放参数）、timeline（编辑后的轨道）、audio_regions、crop_region 等所有编辑状态全部丢失。`_on_save_project` 是空函数，用户手动保存也无效。
2. **编辑器工具栏冗余**：编辑器页显示了录制/停止按钮，但录制应从首页发起，编辑器应专注于编辑功能。

### 1.2 目标用户
使用 Recordly 录制屏幕后需要编辑和保存项目的用户。

### 1.3 成功指标
- 录制完成后自动创建的项目包含所有录制原始数据（cursor_events、click_events、camera）
- 用户在编辑器中手动保存时，所有编辑状态（timeline、crop_region、audio_regions）被持久化
- 打开已有项目时，编辑状态被完整恢复
- 编辑器工具栏不再显示录制/停止按钮

## 2. 功能需求

### 2.1 核心功能（MVP）
- [ ] F1: 从编辑器工具栏移除录制/停止按钮
- [ ] F2: 录制完成后自动保存 compositor 状态到 Project（cursor_events、click_events、monitor_offset、camera 参数）
- [ ] F3: `_on_save_project` 实现真正的持久化（timeline、crop_region、audio_regions、annotations 等）
- [ ] F4: `_on_open_project` 恢复完整编辑状态（timeline、crop_region、audio_regions、cursor/click events）

### 2.2 扩展功能（后续迭代）
- [ ] E1: 从 project.source.video 解码视频帧到 compositor（打开项目后预览区可播放）
- [ ] E2: cursor_events 和 click_events 存储到项目文件而非 compositor 内存中
- [ ] E3: 录制历史管理（多次录制不覆盖之前的 compositor 状态）

### 2.3 非功能需求
- 保存操作 < 500ms（JSON 序列化 + 磁盘写入）
- 向后兼容：旧版 project.json（无新字段）打开时用默认值填充

## 3. 用户故事

### US-1: 录制后数据完整保存
**作为** 用户
**我想要** 录制完成后自动创建的 Project 包含光标轨迹和缩放数据
**以便** 下次打开项目时预览区能重现原有的缩放效果

**验收标准：**
- [ ] `_auto_create_project` 在创建 Project 后调用保存逻辑，将 compositor 状态写入 project.json
- [ ] project.json 包含 cursor_events、click_events、monitor_offset 数据

### US-2: 手动保存编辑状态
**作为** 用户
**我想要** 点击"保存"后编辑状态被持久化
**以便** 下次打开项目继续编辑

**验收标准：**
- [ ] `_on_save_project` 将当前 compositor 状态（timeline、crop、audio_regions）写入 project.json
- [ ] 保存后状态栏显示"项目已保存"

### US-3: 打开项目恢复编辑状态
**作为** 用户
**我想要** 打开已有项目时恢复光标效果和缩放数据
**以便** 预览区显示与录制时一致的视觉效果

**验收标准：**
- [ ] `_on_open_project` 从 project.json 恢复 cursor_events、click_events 到 compositor
- [ ] 重建 camera 对象（如有），光标效果正常工作
- [ ] timeline、crop_region、audio_regions 正确恢复

### US-4: 编辑器工具栏精简
**作为** 用户
**我想要** 编辑器工具栏只显示编辑相关按钮
**以便** 界面更干净，操作更专注

**验收标准：**
- [ ] 编辑器工具栏不包含录制/停止按钮
- [ ] 录制入口仅在首页提供

## 4. 约束与假设

### 4.1 技术约束
- 不创建新的数据库/文件格式，沿用 project.json（JSON 序列化）
- 不修改 Compositor 核心算法
- 保存 cursor_events/click_events 时需考虑数据量（可能数千条），需压缩或采样

### 4.2 业务约束
- 视频帧解码不在本次范围（E1）
- 不改变 ProjectManager.create_project 的目录结构

### 4.3 假设
- Compositor 的 `_cursor_events` 和 `_click_events` 数据结构稳定
- JSON 序列化可处理 numpy 数据（需转为 Python 原生类型）

## 5. 不在范围内
- 从 source.mp4 解码视频帧回 compositor
- 录制历史多版本管理
- 修改 ProjectManager.create_project 的目录结构
- 导入/导出功能

## 6. 附录
- 当前代码：app/main_window.py（约 1160 行）
- 关键方法：_auto_create_project (L489-520)、_on_save_project (L1110)、_on_open_project (L1040-1092)
- Project 模型：core/project.py（约 253 行）
- Compositor 状态：core/compositor.py（约 390 行）
