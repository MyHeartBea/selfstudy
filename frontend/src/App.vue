<script setup>
/** 根组件：主题恢复 + 全局 Toast / Confirm 宿主 */
import { onMounted } from 'vue'
import ToastHost from './ui/ToastHost.vue'
import ConfirmHost from './ui/ConfirmHost.vue'

onMounted(() => {
  const saved = localStorage.getItem('km-theme')
  if (saved === 'dark') {
    document.documentElement.dataset.theme = 'dark'
  }
})
</script>

<template>
  <router-view />
  <ToastHost />
  <ConfirmHost />
</template>
