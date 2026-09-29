import { defineConfig } from 'vitepress'

// GitHub Pages 项目站点部署路径：/<repo>/。仓库为 recordly，故 base 为 /recordly/。
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

const overviewItems = [
  { text: '项目概览', link: '/00-overview/' },
  { text: 'PRD 索引', link: '/01-product/prd/' },
  { text: 'Tech Spec 索引', link: '/03-architecture/system-design/' },
  { text: 'ADR 索引', link: '/03-architecture/adr/' },
  { text: '文档迁移报告', link: '/archive/adoption-migration-report' },
]

const archiveItems = [
  { text: '归档说明', link: '/archive/' },
  { text: '归档 · 任务 DAG', link: '/archive/design/' },
  { text: '归档 · 评审记录', link: '/archive/review/' },
  { text: '归档 · 任务清单', link: '/archive/task/' },
]

const researchItems = [
  { text: '官网与文档体系调研', link: '/dev/research/vitepress-github-pages-strategy' },
]

export default defineConfig({
  title: 'Recordly',
  base,
  lastUpdated: true,
  cleanUrls: true,
  srcExclude: ['.agents/**'],
  sitemap: {
    hostname: 'https://devcxl.github.io/recordly/',
  },
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${base}logo.svg` }],
    ['meta', { name: 'theme-color', content: '#e53935' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:site_name', content: 'Recordly' }],
    ['meta', { property: 'og:title', content: 'Recordly - 开源桌面录屏与演示剪辑工具' }],
    [
      'meta',
      {
        property: 'og:description',
        content: '基于 PyQt5 + FFmpeg，录制、光标特效、双轨音频、时间线剪辑、NVENC 加速导出，一气呵成。',
      },
    ],
  ],
  themeConfig: {
    logo: '/logo.svg',
    outline: { level: [2, 3] },
    socialLinks: [{ icon: 'github', link: 'https://github.com/devcxl/recordly' }],
    search: {
      provider: 'local',
      options: {
        locales: {
          root: {
            translations: {
              button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
              modal: {
                displayDetails: '显示详细列表',
                resetButtonTitle: '清除搜索',
                backButtonTitle: '返回',
                noResultsText: '未找到相关结果',
                footer: {
                  selectText: '选择',
                  navigateText: '切换',
                  closeText: '关闭',
                },
              },
            },
          },
          en: {
            translations: {
              button: { buttonText: 'Search', buttonAriaLabel: 'Search documentation' },
              modal: {
                displayDetails: 'Display detailed list',
                resetButtonTitle: 'Reset search',
                backButtonTitle: 'Close search',
                noResultsText: 'No results for',
                footer: {
                  selectText: 'to select',
                  navigateText: 'to navigate',
                  closeText: 'to close',
                },
              },
            },
          },
        },
      },
    },
  },
  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      title: 'Recordly',
      description: '开源桌面录屏与演示视频编辑工具 —— 录制、剪辑、导出，一气呵成',
      themeConfig: {
        nav: [
          { text: '首页', link: '/' },
          { text: '功能特性', link: '/features' },
          { text: '使用指南', link: '/guide/' },
          { text: '下载安装', link: '/#download' },
          {
            text: '开发与架构',
            items: [
              { text: '项目概览', link: '/00-overview/' },
              { text: '产品需求 (PRD)', link: '/01-product/prd/' },
              { text: '技术方案 (Tech Spec)', link: '/03-architecture/system-design/' },
              { text: '架构决策 (ADR)', link: '/03-architecture/adr/' },
              { text: '研发调研', link: '/dev/research/vitepress-github-pages-strategy' },
              { text: '历史归档', link: '/archive/' },
            ],
          },
          { text: 'Releases', link: 'https://github.com/devcxl/recordly/releases' },
        ],
        sidebar: {
          '/guide/': [
            {
              text: '使用指南',
              items: [
                { text: '新用户上手指南', link: '/guide/' },
                { text: '安装与启动', link: '/guide/#安装与启动' },
                { text: '首页导览', link: '/guide/#首页导览' },
                { text: '第一次录制', link: '/guide/#第一次录制' },
                { text: '编辑器界面导览', link: '/guide/#编辑器界面导览' },
                { text: '时间线剪辑', link: '/guide/#时间线剪辑' },
                { text: '速度与音量', link: '/guide/#速度与音量' },
                { text: '音频进阶与补录', link: '/guide/#音频进阶' },
                { text: '智能缩放', link: '/guide/#智能缩放' },
                { text: '光标特效与裁剪', link: '/guide/#光标特效与画面裁剪' },
                { text: '导出视频', link: '/guide/#导出视频' },
                { text: '项目管理与保存', link: '/guide/#项目管理与保存' },
                { text: '常见问题 (FAQ)', link: '/guide/#常见问题-faq' },
              ],
            },
          ],
          '/features': [
            {
              text: '功能特性',
              items: [
                { text: '特性详解', link: '/features' },
                { text: '屏幕与音频采集', link: '/features#屏幕与音频采集' },
                { text: '全局光标追踪与特效', link: '/features#全局光标追踪与特效' },
                { text: '演示级时间线剪辑', link: '/features#演示级时间线剪辑' },
                { text: '智能缩放 (Zoom Track)', link: '/features#智能缩放-zoom-track' },
                { text: 'NVENC 硬件加速与导出', link: '/features#nvenc-硬件加速与导出' },
                { text: '工程持久化与安全性', link: '/features#工程持久化与安全性' },
              ],
            },
          ],
          '/00-overview/': [{ text: '概览', items: overviewItems }],
          '/01-product/': [{ text: '01 产品需求 (PRD)', items: prd }],
          '/03-architecture/': [
            { text: '03 技术方案 (Tech Spec)', items: techSpec },
            { text: '03 架构决策 (ADR)', items: adr },
          ],
          '/dev/': [{ text: '研发调研', items: researchItems }],
          '/archive/': [{ text: '历史归档', items: archiveItems }],
        },
      },
    },
    en: {
      label: 'English',
      lang: 'en-US',
      link: '/en/',
      title: 'Recordly',
      description: 'Open-source desktop screen recording and video demo editing tool.',
      themeConfig: {
        nav: [
          { text: 'Home', link: '/en/' },
          { text: 'Features', link: '/en/features' },
          { text: 'Guide', link: '/en/guide/' },
          { text: 'Download', link: '/en/#download' },
          {
            text: 'Architecture & Dev',
            items: [
              { text: 'Overview', link: '/00-overview/' },
              { text: 'Product Specs (PRD)', link: '/01-product/prd/' },
              { text: 'System Design', link: '/03-architecture/system-design/' },
              { text: 'ADR', link: '/03-architecture/adr/' },
              { text: 'Research', link: '/dev/research/vitepress-github-pages-strategy' },
            ],
          },
          { text: 'Releases', link: 'https://github.com/devcxl/recordly/releases' },
        ],
        sidebar: {
          '/en/guide/': [
            {
              text: 'User Guide',
              items: [
                { text: 'Getting Started', link: '/en/guide/' },
                { text: 'Installation', link: '/en/guide/#installation' },
                { text: 'Home Gallery', link: '/en/guide/#home-gallery' },
                { text: 'First Recording', link: '/en/guide/#first-recording' },
                { text: 'Editor Interface', link: '/en/guide/#editor-interface' },
                { text: 'Timeline Editing', link: '/en/guide/#timeline-editing' },
                { text: 'Advanced Audio', link: '/en/guide/#advanced-audio' },
                { text: 'Smart Zoom Track', link: '/en/guide/#smart-zoom-track' },
                { text: 'Exporting Video', link: '/en/guide/#exporting-video' },
                { text: 'Troubleshooting & FAQ', link: '/en/guide/#troubleshooting-and-faq' },
              ],
            },
          ],
          '/en/features': [
            {
              text: 'Features',
              items: [
                { text: 'Feature Details', link: '/en/features' },
                { text: 'Screen & Audio Capture', link: '/en/features#screen-and-audio-capture' },
                { text: 'Cursor Effects & Tracking', link: '/en/features#cursor-effects-and-tracking' },
                { text: 'Timeline Editing', link: '/en/features#timeline-editing' },
                { text: 'Smart Zoom Track', link: '/en/features#smart-zoom-track' },
                { text: 'Export & Hardware Acceleration', link: '/en/features#export-and-hardware-acceleration' },
                { text: 'Project Safety & Persistence', link: '/en/features#project-safety-persistence' },
              ],
            },
          ],
        },
      },
    },
  },
})
