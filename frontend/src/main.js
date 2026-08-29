import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { reveal } from './directives/reveal'
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
