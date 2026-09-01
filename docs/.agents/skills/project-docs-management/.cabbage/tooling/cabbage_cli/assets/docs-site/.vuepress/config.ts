import { defineUserConfig } from 'vuepress'
import { viteBundler } from '@vuepress/bundler-vite'
import { defaultTheme } from '@vuepress/theme-default'
import { markdownChartPlugin } from '@vuepress/plugin-markdown-chart'

export default defineUserConfig({
  lang: 'zh-CN',
  title: 'Project Documentation',
  description: 'Project documentation managed by Cabbage',
  bundler: viteBundler(),
  theme: defaultTheme({
    navbar: [{ text: '首页', link: '/' }],
  }),
  plugins: [markdownChartPlugin({ mermaid: true })],
})
