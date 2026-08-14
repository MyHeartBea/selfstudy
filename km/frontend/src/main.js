import { createApp } from 'vue'
import 'element-plus/dist/index.css'
import {
  Calendar,
  CircleCheck,
  Collection,
  DataAnalysis,
  DataBoard,
  DocumentAdd,
  Download,
  EditPen,
  Medal,
  Notebook,
  Reading,
  Refresh,
  RefreshLeft,
  Star,
  TrendCharts,
  Upload,
} from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { setupElementPlus } from './plugins/element'
import './assets/theme.css'

const app = createApp(App)
// 只注册实际用到的图标，避免全量图标进入打包产物
for (const [key, component] of Object.entries({
  Calendar,
  CircleCheck,
  Collection,
  DataAnalysis,
  DataBoard,
  DocumentAdd,
  Download,
  EditPen,
  Medal,
  Notebook,
  Reading,
  Refresh,
  RefreshLeft,
  Star,
  TrendCharts,
  Upload,
})) {
  app.component(key, component)
}
setupElementPlus(app)
app.use(router)
app.mount('#app')
