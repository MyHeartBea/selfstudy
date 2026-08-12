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

export default router
