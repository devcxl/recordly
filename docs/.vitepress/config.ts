import { defineConfig } from 'vitepress'

// GitHub Pages 项目站点部署路径：/<repo>/。仓库为 recordly，故 base 为 /recordly/。
// 若部署到自定义域名或用户主页，请相应调整；也可通过 CI 环境变量 BASE_PATH 覆盖。
const base = process.env.BASE_PATH || '/recordly/'

const prd = [
  { text: '核心稳定性与架构治理', link: '/01-product/prd/recordly-core-stability' },
  { text: '录制数据持久化与工具栏精简', link: '/01-product/prd/recordly-data-persistence' },
  { text: '交互与页面架构重构', link: '/01-product/prd/recordly-ux-refactor' },
  { text: '项目管理功能', link: '/01-product/prd/project-management' },
  { text: '时间线裁剪功能完善', link: '/01-product/prd/recordly-timeline-trim' },
  { text: '播放头点击行为修正', link: '/01-product/prd/recordly-playhead-click-behavior' },
  { text: '时间线编辑器交互增强', link: '/01-product/prd/recordly-timeline-interaction-enhancements' },
  { text: '撤销/重做快捷键与入口', link: '/01-product/prd/recordly-undo-redo-shortcuts' },
  { text: '编辑器可用性修复与快捷键配置', link: '/01-product/prd/recordly-editor-usability-fixes' },
  { text: '双音频轨道编辑与麦克风补录', link: '/01-product/prd/recordly-dual-audio-tracks-and-re-record' },
]

const techSpec = [
  { text: '核心稳定性与架构治理', link: '/03-architecture/system-design/recordly-core-stability' },
  { text: '录制数据持久化与工具栏精简', link: '/03-architecture/system-design/recordly-data-persistence' },
  { text: '交互与页面架构重构', link: '/03-architecture/system-design/recordly-ux-refactor' },
  { text: '导出坐标一致性', link: '/03-architecture/system-design/export-coordinate-consistency' },
  { text: '导出速度优化', link: '/03-architecture/system-design/export-speed-optimization' },
  { text: '时间线裁剪功能完善', link: '/03-architecture/system-design/recordly-timeline-trim' },
  { text: '播放头点击行为修正', link: '/03-architecture/system-design/recordly-playhead-click-behavior' },
  { text: '时间线编辑器交互增强', link: '/03-architecture/system-design/recordly-timeline-interaction-enhancements' },
  { text: '撤销/重做快捷键与入口', link: '/03-architecture/system-design/recordly-undo-redo-shortcuts' },
  { text: '编辑器可用性修复与快捷键配置', link: '/03-architecture/system-design/recordly-editor-usability-fixes' },
  { text: '双音频轨道编辑与麦克风补录', link: '/03-architecture/system-design/recordly-dual-audio-tracks-and-re-record' },
  { text: '项目管理功能', link: '/03-architecture/system-design/project-management' },
]

const adr = [
  { text: 'ADR-005 双页面架构', link: '/03-architecture/adr/005-home-editor-dual-view' },
  { text: 'ADR-006 数据持久化到 Project JSON', link: '/03-architecture/adr/006-data-persistence-json' },
  { text: 'ADR-007 三控制器架构提取', link: '/03-architecture/adr/007-project-session-recording-export-controllers' },
  { text: '项目管理功能架构决策', link: '/03-architecture/adr/2026-07-13-project-management' },
  { text: '时间线边缘拖拽 source 同步', link: '/03-architecture/adr/2026-07-17-timeline-trim-source-sync' },
  { text: '编辑器快捷键注册表', link: '/03-architecture/adr/2026-07-19-editor-shortcut-registry' },
  { text: '播放头点击行为', link: '/03-architecture/adr/2026-07-19-playhead-click-behavior' },
  { text: '时间线交互路由与吸附', link: '/03-architecture/adr/2026-07-19-timeline-interaction-routing-and-snapping' },
  { text: '撤销/重做快捷键', link: '/03-architecture/adr/2026-07-19-undo-redo-shortcuts' },
  { text: '双音频轨道编辑与补录', link: '/03-architecture/adr/2026-08-10-dual-audio-tracks-re-record' },
]

export default defineConfig({
  lang: 'zh-CN',
  title: 'Recordly Docs',
  description: 'Recordly 桌面录屏与视频编辑工具 —— 项目文档',
  base,
  lastUpdated: true,
  cleanUrls: true,
  srcExclude: ['.agents/**'],
  themeConfig: {
    outline: { level: [2, 3] },
    nav: [
      { text: '首页', link: '/' },
      { text: '使用指南', link: '/guide/' },
      { text: '产品需求', link: '/01-product/prd/' },
      { text: '技术方案', link: '/03-architecture/system-design/' },
      { text: 'ADR', link: '/03-architecture/adr/' },
      { text: '归档', link: '/archive/' },
    ],
    sidebar: [
      { text: '使用指南', items: [
        { text: '新用户使用指南', link: '/guide/' },
      ]},
      { text: '概览', items: [
        { text: '项目概览', link: '/00-overview/' },
        { text: 'PRD 索引', link: '/01-product/prd/' },
        { text: 'Tech Spec 索引', link: '/03-architecture/system-design/' },
        { text: 'ADR 索引', link: '/03-architecture/adr/' },
        { text: '文档迁移报告', link: '/archive/adoption-migration-report' },
      ]},
      { text: '01 产品需求 (PRD)', items: prd },
      { text: '03 技术方案 (Tech Spec)', items: techSpec },
      { text: '03 架构决策 (ADR)', items: adr },
      { text: '历史归档', items: [
        { text: '归档说明', link: '/archive/' },
        { text: '归档 · 任务 DAG', link: '/archive/design/' },
        { text: '归档 · 评审记录', link: '/archive/review/' },
        { text: '归档 · 任务清单', link: '/archive/task/' },
      ]},
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/devcxl/recordly' },
    ],
  },
})