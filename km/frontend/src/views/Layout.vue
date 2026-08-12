<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { loadBaseData } from '../composables/useBaseData'

const route = useRoute()

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/mistakes/')) return '/mistakes'
  return path
})

onMounted(loadBaseData)
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">
        <div class="brand-title">考研错题本</div>
        <div class="brand-sub">Kaoyan Mistake Book</div>
      </div>
      <el-menu :default-active="activeMenu" router class="side-menu">
        <el-menu-item index="/mistakes">错题列表</el-menu-item>
        <el-menu-item index="/capture">智能录入</el-menu-item>
        <el-menu-item index="/review">今日复习</el-menu-item>
        <el-menu-item index="/practice">自主练习</el-menu-item>
        <el-menu-item index="/knowledge">知识点库</el-menu-item>
        <el-menu-item index="/formulas">公式背诵库</el-menu-item>
        <el-menu-item index="/subjects">科目指南</el-menu-item>
        <el-menu-item index="/stats">统计</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
