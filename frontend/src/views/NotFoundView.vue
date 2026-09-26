<script setup>
/** 404 兜底页：后端 SPA 回退会把任何未知路径交给前端路由，此前没有 catch-all 时会渲染成空白外壳。 */
import { useRouter } from 'vue-router'

import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <UiEmpty seal="误" text="此路不通：页面不存在或已被移动">
      <div class="nf-actions">
        <UiButton variant="primary" @click="router.push('/stats')">回到统计</UiButton>
        <UiButton variant="ghost" @click="router.back()">返回上一页</UiButton>
      </div>
    </UiEmpty>
  </div>
</template>

<style scoped>
.not-found {
  display: grid;
  place-items: center;
  min-height: 60vh;
}
.nf-actions {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}
</style>
