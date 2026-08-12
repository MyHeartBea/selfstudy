<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import request from '../api/request'
import MistakeForm from '../components/MistakeForm.vue'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => route.name === 'mistake-edit')
const initial = ref(null)

onMounted(async () => {
  if (isEdit.value) {
    try {
      const res = await request.get(`/mistakes/${route.params.id}`)
      initial.value = res.data.data
    } catch (err) {
      // 错误提示由请求拦截器统一处理
    }
  }
})

function onSubmitted() {
  router.push('/mistakes')
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>编辑错题</h2>
    </div>
    <el-card shadow="never" class="form-card">
      <MistakeForm
        v-if="!isEdit || initial"
        :initial="initial"
        :is-edit="isEdit"
        @submitted="onSubmitted"
      />
    </el-card>
  </div>
</template>
