import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { reveal } from './directives/reveal'
import { installErrorBoundary, installWindowGuards, showFatal } from './utils/errorBoundary'

// API_TOKEN 模式（局域网访问）：<img> 标签发不了自定义头，boot 时把 token 同步写进
// cookie（km_token），让 /images 静态图与缩略图自动携带；axios 侧走 request.js 的请求拦截器。
// token 来源是用户手动在 localStorage 写入 km-api-token（单用户场景，不做登录页）。
const kmToken = localStorage.getItem('km-api-token')
if (kmToken) document.cookie = `km_token=${encodeURIComponent(kmToken)}; path=/; SameSite=Lax`

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

installWindowGuards()

const app = createApp(App)
app.directive('reveal', reveal)
app.use(router)
installErrorBoundary(app)
try {
  app.mount('#app')
} catch (err) {
  // 挂载本身抛错时 #app 是空的，下面的收起启动屏逻辑仍要跑，
  // 否则用户看到的是一层永远不散的遮罩压在白屏上。
  showFatal(err)
}

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
