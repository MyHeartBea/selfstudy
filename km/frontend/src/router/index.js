import { createRouter, createWebHistory } from 'vue-router'

import Layout from '../views/Layout.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    children: [
      { path: '', redirect: '/mistakes' },
      {
        path: 'mistakes',
        name: 'mistake-list',
        component: () => import('../views/MistakeList.vue'),
      },
      {
        path: 'mistakes/new',
        redirect: '/capture',
      },
      {
        path: 'capture',
        name: 'capture',
        component: () => import('../views/CaptureView.vue'),
      },
      {
        path: 'review',
        name: 'review',
        component: () => import('../views/ReviewView.vue'),
      },
      {
        path: 'practice',
        name: 'practice',
        component: () => import('../views/PracticeView.vue'),
      },
      {
        path: 'mistakes/:id/edit',
        name: 'mistake-edit',
        component: () => import('../views/MistakeCreate.vue'),
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('../views/KnowledgeBase.vue'),
      },
      {
        path: 'formulas',
        name: 'formulas',
        component: () => import('../views/FormulaView.vue'),
      },
      {
        path: 'subjects',
        name: 'subject-guide',
        component: () => import('../views/SubjectGuide.vue'),
      },
      {
        path: 'stats',
        name: 'stats',
        component: () => import('../views/Stats.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由级标题：多标签页可辨识（与 Layout 的 pageTitle 文案保持一致）
const TITLE_MAP = {
  'mistake-list': '错题列表',
  capture: '智能录入',
  review: '今日复习',
  practice: '自主练习',
  'mistake-edit': '编辑错题',
  knowledge: '知识点库',
  formulas: '公式背诵',
  'subject-guide': '科目指南',
  stats: '学习统计',
}
router.afterEach((to) => {
  const title = TITLE_MAP[to.name]
  document.title = title ? `${title} · 考研错题本` : '考研错题本'
})

export default router
