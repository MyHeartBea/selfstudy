<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import request from '../api/request'
import MistakeForm from '../components/MistakeForm.vue'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => route.name === 'mistake-edit')
const initial = ref(null)
const loadFailed = ref(false)

onMounted(async () => {
  if (isEdit.value) {
    try {
      const res = await request.get(`/mistakes/${route.params.id}`)
      initial.value = res.data.data
    } catch (err) {
      // 加载失败给明确错误态，不再静默白屏
      loadFailed.value = true
    }
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
        <p class="view-desc">修改题干、答案、解析与知识点标签。</p>
      </div>
    </div>
    <el-card shadow="never" class="form-card">
      <el-result
        v-if="loadFailed"
        icon="error"
        title="错题加载失败"
        sub-title="该错题可能已被删除，或网络异常。"
      >
        <template #extra>
          <el-button type="primary" @click="router.push('/mistakes')">
            返回错题列表
          </el-button>
        </template>
      </el-result>
      <MistakeForm
        v-else-if="!isEdit || initial"
        :initial="initial"
        :is-edit="isEdit"
        @submitted="onSubmitted"
      />
    </el-card>
  </div>
</template>
