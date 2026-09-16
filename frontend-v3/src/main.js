/**
 * km-v3 入口
 *
 * 顺序有讲究：先挂样式，再挂应用 —— 避免首帧出现无样式的闪烁（FOUC）。
 * 加载顺序：设计令牌，基础层，应用。
 */
import { createApp } from 'vue'

import './design/tokens.css'
import './design/base.css'
import './design/materials.css'

import App from './app/App.vue'
import { router } from './app/router'

const app = createApp(App)
app.use(router)
app.mount('#app')

// 移除 index.html 里的首帧兜底底色（Vue 已接管）
const boot = document.getElementById('boot')
if (boot) boot.remove()
