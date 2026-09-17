<script setup>
/**
 * 根组件：主题恢复 + 全局 Toast / Confirm 宿主 + 进入动画
 *
 * 进入动画（BootCalibration）在 v2 上是新增的：
 *   校准台 - 整块向上抽走 - 给 body 加 .ready，页面入场动画随之播放。
 * 只在**首次进入**时播一次（同一会话内路由切换不再播），避免每次跳页都挡一下。
 */
import { onMounted, ref } from 'vue'

import ToastHost from './ui/ToastHost.vue'
import ConfirmHost from './ui/ConfirmHost.vue'
import BootCalibration from './ui/BootCalibration.vue'

/**
 * 进入动画的播放时机（踩过一个坑后的定论）：
 *   . **刷新 / 首次打开** - 要播（用户要的就是"网页进入动画"）
 *   . **站内路由切换**  - 不播（否则每次点导航都挡一下）
 *
 * 模块级变量恰好符合这个语义：页面刷新时 JS 重新执行 - 重置为 false（会播）；
 * 站内路由切换时模块不重新执行 - 保持 true（不播）。
 * 之前用 sessionStorage 记录，导致**刷新也不再播**，是错的。
 */
const booting = ref(true)

onMounted(() => {
  const saved = localStorage.getItem('km-theme')
  if (saved === 'dark') {
    document.documentElement.dataset.theme = 'dark'
  }
})

function onBootDone() {
  booting.value = false
}
</script>

<template>
  <router-view />
  <ToastHost />
  <ConfirmHost />
  <BootCalibration v-if="booting" @done="onBootDone" />
</template>
