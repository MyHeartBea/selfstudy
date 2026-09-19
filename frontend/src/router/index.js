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
      {
        path: 'papers',
        name: 'paper-bank',
        component: () => import('../views/PapersView.vue'),
      },
      {
        path: 'essays',
        name: 'essay-bank',
        component: () => import('../views/EssayView.vue'),
      },
      {
        // 维护页：不进 Dock 导航，由命令面板（Ctrl+K）或直链进入
        path: 'integrity',
        name: 'data-integrity',
        component: () => import('../views/IntegrityView.vue'),
      },
      {
        path: 'design',
        name: 'design-gallery',
        component: () => import('../views/DesignView.vue'),
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
  'essay-bank': '作文档案',
  'data-integrity': '数据体检',
}
router.afterEach((to) => {
  const title = TITLE_MAP[to.name]
  document.title = title ? `${title} · 研错本` : '研错本 · 考研错题管理'
})

export default router

/**
 * 导航顺序（用于判断换页方向）。
 * 为什么要它：用户要求"选左边那一页就向左翻、选右边那一页就向右翻"，
 * 而"左右"只能由导航里的先后顺序定义 —— 路由表本身不含这个信息。
 * 数组顺序与导航栏一致。
 */
export const NAV_ORDER = [
  // 必须与**真实路由名**一致。第一版写了 home / mistakes / papers / subjects / design，
  // 而这些名字路由里并不存在 —— navIndexOf() 对未知名字返回数组长度，
  // 于是任意两页都算同一个编号、方向判断恒为 prev（这就是"方向反了"的真因）。
  'stats',
  'review',
  'capture',
  'mistake-list',
  'vocab',
  'knowledge',
  'formulas',
  'paper-bank',
  'essay-bank',
  'practice',
  'subject-guide',
  'data-integrity',
  'design-gallery',
  'mistake-edit',
]

/** 取某个路由在导航顺序里的编号；未知路由排到最后 */
export function navIndexOf(name) {
  const i = NAV_ORDER.indexOf(name)
  return i === -1 ? NAV_ORDER.length : i
}
