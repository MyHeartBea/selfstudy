<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import gsap from 'gsap'

import { loadBaseData } from '../composables/useBaseData'

const route = useRoute()

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/mistakes/')) return '/mistakes'
  return path
})

const pageTitle = computed(() => {
  const map = {
    '/mistakes': '错题列表',
    '/capture': '智能录入',
    '/review': '今日复习',
    '/practice': '自主练习',
    '/knowledge': '知识点库',
    '/formulas': '公式背诵',
    '/subjects': '科目指南',
    '/stats': '学习统计',
  }
  return map[activeMenu.value] || '学习工作台'
})

const today = ref('')

function refreshDate() {
  today.value = new Date().toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  })
}

async function animatePage() {
  await nextTick()
  const page = document.querySelector('.main .page')
  if (page) {
    gsap.fromTo(
      page,
      { opacity: 0, y: 16 },
      { opacity: 1, y: 0, duration: 0.42, ease: 'power2.out' },
    )
  }
  const targets = document.querySelectorAll(
    '.page .stats-cards > *, .page .mistake-grid > *, .page .formula-grid > *, .page [data-reveal]',
  )
  if (targets.length) {
    gsap.fromTo(
      targets,
      { opacity: 0, y: 12 },
      { opacity: 1, y: 0, duration: 0.38, stagger: 0.035, ease: 'power2.out' },
    )
  }
}

watch(
  () => route.fullPath,
  () => {
    refreshDate()
    animatePage()
  },
)

onMounted(() => {
  loadBaseData()
  refreshDate()
  animatePage()
})
</script>

<template>
  <el-container class="layout">
    <el-aside width="264px" class="aside">
      <div class="brand">
        <div class="brand-mark">K</div>
        <div class="brand-copy">
          <div class="brand-title">研错本</div>
          <div class="brand-sub">Kaoyan Mistake Book</div>
        </div>
      </div>

      <div class="menu-section-label">学习工作台</div>
      <el-menu :default-active="activeMenu" router class="side-menu">
        <el-menu-item index="/mistakes">
          <el-icon><DataBoard /></el-icon>
          <span>错题列表</span>
        </el-menu-item>
        <el-menu-item index="/capture">
          <el-icon><DocumentAdd /></el-icon>
          <span>智能录入</span>
        </el-menu-item>
        <el-menu-item index="/review">
          <el-icon><Refresh /></el-icon>
          <span>今日复习</span>
        </el-menu-item>
        <el-menu-item index="/practice">
          <el-icon><EditPen /></el-icon>
          <span>自主练习</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Collection /></el-icon>
          <span>知识点库</span>
        </el-menu-item>
        <el-menu-item index="/formulas">
          <el-icon><Notebook /></el-icon>
          <span>公式背诵</span>
        </el-menu-item>
        <el-menu-item index="/subjects">
          <el-icon><Reading /></el-icon>
          <span>科目指南</span>
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><DataAnalysis /></el-icon>
          <span>学习统计</span>
        </el-menu-item>
      </el-menu>

      <div class="aside-foot">
        <div class="aside-status">
          <span class="status-dot"></span>
          本地数据已同步
        </div>
        <div class="aside-version">v1.0 · Vue 3</div>
      </div>
    </el-aside>

    <el-container class="main-column">
      <header class="topbar">
        <div class="topbar-left">
          <div class="topbar-kicker">Kaoyan OS</div>
          <div class="topbar-title">{{ pageTitle }}</div>
        </div>
        <div class="topbar-actions">
          <div class="topbar-date">{{ today }}</div>
          <div class="user-chip">
            <div class="avatar">研</div>
            <span>我的学习</span>
          </div>
        </div>
      </header>

      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="page-move" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>
