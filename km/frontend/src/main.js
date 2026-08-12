import { createApp } from 'vue'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { setupElementPlus } from './plugins/element'
import './assets/theme.css'

const app = createApp(App)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
setupElementPlus(app)
app.use(router)
app.mount('#app')
