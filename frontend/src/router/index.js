import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '../views/AppLayout.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', redirect: '/stats' },
      {
        path: 'stats',
        name: 'stats',
        component: () => import('../views/StatsView.vue'),
      },
      {
        path: 'mistakes',
        name: 'mistake-list',
        component: () => import('../views/MistakeListView.vue'),
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
        component: () => import('../views/MistakeEditView.vue'),
      },
      {
        path: 'vocab',
        name: 'vocab',
        component: () => import('../views/VocabView.vue'),
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('../views/KnowledgeView.vue'),
      },
      {
        path: 'formulas',
        name: 'formulas',
        component: () => import('../views/FormulaView.vue'),
      },
      {
        path: 'subjects',
        name: 'subject-guide',
        component: () => import('../views/SubjectView.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由级标题：多标签页可辨识
const TITLE_MAP = {
  stats: '学习统计',
  'mistake-list': '错题列表',
  capture: '智能录入',
  review: '今日复习',
  practice: '自主练习',
  'mistake-edit': '编辑错题',
  vocab: '生词本',
  knowledge: '知识点库',
  formulas: '公式背诵',
  'subject-guide': '科目指南',
}
router.afterEach((to) => {
  const title = TITLE_MAP[to.name]
  document.title = title ? `${title} · 研错本` : '研错本 · 考研错题管理'
})

export default router
