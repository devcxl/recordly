---
layout: home

hero:
  name: "Recordly Docs"
  text: "桌面录屏与演示视频编辑工具"
  tagline: "录制、剪辑、导出，一气呵成 —— 项目产品需求、技术方案与架构决策文档"
  actions:
    - theme: brand
      text: 新用户使用指南
      link: /guide/
    - theme: alt
      text: 项目概览
      link: /00-overview/
    - theme: alt
      text: 产品需求
      link: /01-product/prd/
    - theme: alt
      text: 架构决策
      link: /03-architecture/adr/

features:
  - title: 新用户使用指南
    details: 从安装、第一次录制到剪辑与导出的完整上手流程，含快捷键速查与常见问题。
  - title: 产品需求 (PRD)
    details: 需求背景、用户故事、功能与非功能需求、验收标准 —— 见 01-product/prd/。
  - title: 技术方案 (Tech Spec)
    details: 架构与组件边界、数据流、失败处理与测试决策 —— 见 03-architecture/system-design/。
  - title: 架构决策 (ADR)
    details: 不可变的决策历史：双页面架构、数据持久化、控制器提取等 —— 见 03-architecture/adr/。
---

## 文档结构

```text
00-overview/                     项目概览与导航
01-product/prd/                  产品需求文档（当前状态）
03-architecture/system-design/   技术方案（当前状态）
03-architecture/adr/             架构决策记录（不可变历史）
archive/                         历史工作记录（任务分解、评审、交接）
```

## 维护约定

- 当前状态文档随变更就地更新；决策历史文档不可改写，新决策显式取代旧记录。
- 文档变更遵循 Cabbage 生命周期：变更记录 → 验证 → 同步 → 双轴评审 → 合并。