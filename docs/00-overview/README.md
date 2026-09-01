# Recordly 项目文档

> 开源桌面录屏与演示视频编辑工具 —— 录制、剪辑、导出，一气呵成。

Recordly 是基于 PyQt5 + FFmpeg 的桌面录屏与视频编辑工具，支持屏幕录制、鼠标光标特效、音频混合、时间线剪辑与 MP4/GIF 导出，并提供 Arch Linux / Debian / Windows / macOS 分发产物。

本文档库面向项目当前状态与决策历史，遵循 Cabbage 文档生命周期规范组织（详见 `.agents/skills/project-docs-management/`）。

## 文档导航

| 目录 | 内容 | 类型 |
|---|---|---|
| [`01-product/prd/`](../01-product/prd/README.md) | 产品 PRD：需求、用户故事、验收标准 | 当前状态 |
| [`03-architecture/system-design/`](../03-architecture/system-design/README.md) | 技术方案（Tech Spec）：设计决策、组件边界、测试决策 | 当前状态 |
| [`03-architecture/adr/`](../03-architecture/adr/README.md) | 架构决策记录（ADR），不可变历史 | 决策历史 |
| [`archive/`](../archive/README.md) | 历史工作记录：任务分解、评审报告、交接文档、开发笔记 | 归档历史 |

## 当前状态文档清单

### 产品需求（PRD）

- [Recordly 核心稳定性与架构治理](../01-product/prd/recordly-core-stability.md)
- [录制数据持久化与编辑器工具栏精简](../01-product/prd/recordly-data-persistence.md)
- [Recordly 交互与页面架构重构](../01-product/prd/recordly-ux-refactor.md)
- [项目管理功能](../01-product/prd/project-management.md)
- [时间线裁剪功能完善](../01-product/prd/recordly-timeline-trim.md)
- [播放头点击行为修正](../01-product/prd/recordly-playhead-click-behavior.md)
- [时间线编辑器交互增强](../01-product/prd/recordly-timeline-interaction-enhancements.md)
- [撤销/重做快捷键与入口](../01-product/prd/recordly-undo-redo-shortcuts.md)
- [编辑器可用性修复与快捷键配置](../01-product/prd/recordly-editor-usability-fixes.md)
- [双音频轨道编辑与麦克风补录](../01-product/prd/recordly-dual-audio-tracks-and-re-record.md)

### 技术方案（Tech Spec）

- [Recordly 核心稳定性与架构治理](../03-architecture/system-design/recordly-core-stability.md)
- [录制数据持久化与编辑器工具栏精简](../03-architecture/system-design/recordly-data-persistence.md)
- [Recordly 交互与页面架构重构](../03-architecture/system-design/recordly-ux-refactor.md)
- [导出坐标一致性](../03-architecture/system-design/export-coordinate-consistency.md)
- [导出速度优化](../03-architecture/system-design/export-speed-optimization.md)
- [时间线裁剪功能完善](../03-architecture/system-design/recordly-timeline-trim.md)
- [播放头点击行为修正](../03-architecture/system-design/recordly-playhead-click-behavior.md)
- [时间线编辑器交互增强](../03-architecture/system-design/recordly-timeline-interaction-enhancements.md)
- [撤销/重做快捷键与入口](../03-architecture/system-design/recordly-undo-redo-shortcuts.md)
- [编辑器可用性修复与快捷键配置](../03-architecture/system-design/recordly-editor-usability-fixes.md)
- [双音频轨道编辑与麦克风补录](../03-architecture/system-design/recordly-dual-audio-tracks-and-re-record.md)
- [项目管理功能](../03-architecture/system-design/project-management.md)

### 架构决策记录（ADR）

见 [`03-architecture/adr/`](../03-architecture/adr/README.md) 索引。

## 维护规范

- **当前状态文档**（`01-product/`、`03-architecture/system-design/`）描述系统现状，随变更就地更新。
- **决策历史文档**（`03-architecture/adr/`）不可变；新决策通过新增记录并显式取代旧记录。
- **归档区**（`archive/`）保存已完成变更的工作记录，只读不改写。
- 文档变更遵循 Cabbage 生命周期：变更记录 → 验证 → 同步 → 双轴评审 → 合并（见 skill 文档）。