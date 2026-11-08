import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import DownloadCards from './components/DownloadCards.vue'
import AppMockup from './components/AppMockup.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('DownloadCards', DownloadCards)
    app.component('AppMockup', AppMockup)
  },
} satisfies Theme
