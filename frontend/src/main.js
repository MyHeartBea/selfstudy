import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { reveal } from './directives/reveal'
// 本地子集思源宋体（unicode-range 分片，只加载用到的字形；离线可用）
import '@fontsource/noto-serif-sc/500.css'
import '@fontsource/noto-serif-sc/600.css'
import '@fontsource/noto-serif-sc/700.css'
import '@fontsource/noto-serif-sc/900.css'
import './styles/tokens.css'
import './styles/base.css'

const app = createApp(App)
app.directive('reveal', reveal)
app.use(router)
app.mount('#app')

// 应用挂载后收起启动屏：保证最短播放时长，让品牌动画完整呈现
const splash = document.getElementById('splash')
if (splash) {
  const elapsed = performance.now()
  const wait = Math.max(0, 950 - elapsed)
  setTimeout(() => {
    splash.classList.add('done')
    setTimeout(() => splash.remove(), 500)
  }, wait)
}
