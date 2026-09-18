import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { reveal } from './directives/reveal'
// 本地子集思源宋体：动态引入，让 404 条 @font-face（486KB）脱离 render-blocking 链，
// 启动屏不再等它。字体本身有 font-display:swap。
// 把这个 promise 挂到 window：开场编排要等"字体样式表真的注入完"再读
// document.fonts.ready，否则 ready 会在字体还没开始下载时就提前兑现（表现为 FOUT）。
window.__kmFontsReady = import('./styles/fonts.js')
import './styles/tokens.css'
import './styles/base.css'
// 交互与排版增强层（列表悬停 / 逐行揭示 / 等宽数位）—— 学自参考稿，保持 v2 语言
import './styles/km-motion.css'
import './styles/km-live.css'
import './styles/km-editorial.css'
import './styles/km-flip.css'

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
