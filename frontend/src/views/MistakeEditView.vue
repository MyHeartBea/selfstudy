<script setup>
/** 错题编辑页：加载详情 → MistakeForm 全量覆盖更新 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import request from '../api/request'
import MistakeForm from '../components/MistakeForm.vue'
import UiButton from '../ui/UiButton.vue'
import Icon from '../ui/Icon.vue'

const route = useRoute()
const router = useRouter()
const mistake = ref(null)
const loading = ref(true)
const loadFailed = ref(false)

onMounted(async () => {
  try {
    const res = await request.get(`/mistakes/${route.params.id}`)
    mistake.value = res.data.data
  } catch (err) {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
})

function onSubmitted() {
  router.push('/mistakes')
}
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Edit Mistake</div>
        <h2>编辑错题</h2>
        <p class="view-desc">修改后保存即全量覆盖该题内容。</p>
      </div>
      <div class="header-actions">
        <UiButton variant="ghost" @click="router.back()">
          <Icon name="arrowLeft" :size="15" />
          返回
        </UiButton>
      </div>
    </div>

    <div v-if="loading" class="card card-pad">
      <div class="skeleton" style="height: 20px; width: 30%; margin-bottom: 14px"></div>
      <div class="skeleton" style="height: 120px; margin-bottom: 14px"></div>
      <div class="skeleton" style="height: 80px"></div>
    </div>
    <div v-else-if="loadFailed" class="card card-pad muted">错题不存在或已被删除。</div>
    <div v-else class="card card-pad">
      <MistakeForm v-if="mistake" :initial="mistake" is-edit @submitted="onSubmitted" />
    </div>
  </div>
</template>
