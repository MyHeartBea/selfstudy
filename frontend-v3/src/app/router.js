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
    // 首页 = 夜航星图（连续滚动叙事：首屏 - 宣言 - 今晚星表 - 天文台 - 科目星群 - 收束）。
    // 用户要求形态照 atlas 参考稿 —— 首页不再是一张数据看板。
    path: '/',
    name: 'home',
    component: () => import('../views/AtlasHome.vue'),
  },
  {
    // 成册（学习统计）保留在 /stats：它是"数据断面"，不是首页
    path: '/stats',
    name: 'stats',
    component: () => import('../views/StatsView.vue'),
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
  {
    // 智能录入 · 蘸墨台（多帧暂存 + 一次研墨）
    path: '/capture',
    name: 'capture',
    component: () => import('../views/CaptureView.vue'),
  },
  {
    // 错题星表（列表 + 详情）
    path: '/mistakes',
    name: 'mistakes',
    component: () => import('../views/MistakeListView.vue'),
  },
  {
    // 知识点库（知识笺墙 + 关联错题）
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('../views/KnowledgeView.vue'),
  },
  {
    // 生词本（闪卡快刷 + 词表）
    path: '/vocab',
    name: 'vocab',
    component: () => import('../views/VocabView.vue'),
  },
  {
    // 公式背诵（KaTeX 只在这一页按需加载）
    path: '/formulas',
    name: 'formulas',
    component: () => import('../views/FormulaView.vue'),
  },
  {
    // 真题库（套列表 + 巡天扫描）
    path: '/papers',
    name: 'papers',
    component: () => import('../views/PapersView.vue'),
  },
  {
    // 模考记录（得分走势）
    path: '/mocks',
    name: 'mocks',
    component: () => import('../views/MocksView.vue'),
  },
  {
    // 科目指南（学科志：科目列表 + 画像）
    path: '/subjects',
    name: 'subjects',
    component: () => import('../views/SubjectsView.vue'),
  },
  {
    // 自主练习（不写回复习进度）
    path: '/practice',
    name: 'practice',
    component: () => import('../views/PracticeView.vue'),
  },
  {
    // 设置与数据（版本自查 + 全量导出）
    path: '/settings',
    name: 'settings',
    component: () => import('../views/SettingsView.vue'),
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
  home: '首页 · 学习统计',
  atlas: '夜航星图',
  design: '设计规格',
  review: '今日复习',
  capture: '智能录入',
  mistakes: '错题星表',
  knowledge: '知识点库',
  stats: '学习统计',
  vocab: '生词本',
  formulas: '公式背诵',
  papers: '真题库',
  mocks: '模考记录',
  subjects: '科目指南',
  practice: '自主练习',
  settings: '设置与数据',
}

router.afterEach((to) => {
  const t = TITLES[to.name]
  document.title = t ? `${t} · 研错本` : '研错本 · 夜航星图'
})
