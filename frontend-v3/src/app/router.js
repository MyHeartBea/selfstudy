/**
 * 路由：夜航星图的章节结构
 *
 * base 跟随 vite 的 BASE_URL —— 这样 v3 既可以挂在后端根路径（切换后），
 * 也可以挂在子路径（并行期间），不需要改一行路由代码。
 *
 * 阶段 0 只放一个占位首页；阶段 3/4 逐步替换成真实页面。
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'atlas',
    component: () => import('../views/AtlasHome.vue'),
  },
  {
    // 活体规范页：令牌 / 材质 / 动效原语的可交互规格表
    path: '/design',
    name: 'design',
    component: () => import('../views/DesignView.vue'),
  },
  {
    // 今日复习 · 砚台（阶段 3 第一页，接真实 API）
    path: '/review',
    name: 'review',
    component: () => import('../views/ReviewView.vue'),
  },
  // 兜底：未实现的路由回首页，避免开发期白屏
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, from, saved) {
    if (saved) return saved
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  },
})

const TITLES = {
  atlas: '夜航星图',
  design: '设计规格',
  review: '今日复习',
}

router.afterEach((to) => {
  const t = TITLES[to.name]
  document.title = t ? `${t} · 研错本` : '研错本 · 夜航星图'
})
