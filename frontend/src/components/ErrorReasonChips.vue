<script setup>
/**
 * 答错后的错因归因 chips。
 *
 * 为什么是手点而不是 AI 判：机器判得出"答案对不对"，判不出"为什么错"——
 * 知识盲区/审题/计算/粗心必须做题的人自己承认。这四个标记聚合后就是
 * 统计页「错因杠杆榜」的数据源（review_service.get_review_stats.error_reasons）。
 * 再点一次同一格 = 清除归因。
 */
import { ref, watch } from 'vue'

import request from '../api/request'
import Icon from '../ui/Icon.vue'
import { toast } from '../ui/toast'

const props = defineProps({
  mistakeId: { type: Number, default: null },
  visible: { type: Boolean, default: false },
})

const REASONS = [
  { key: 'knowledge', label: '知识盲区' },
  { key: 'read', label: '审题失误' },
  { key: 'calc', label: '计算失误' },
  { key: 'careless', label: '粗心大意' },
]

const marked = ref('')
const saving = ref(false)

// 换题后归因状态归零（上一题的标记不该显示在这一题上）
watch(
  () => props.mistakeId,
  () => {
    marked.value = ''
  },
)

async function mark(key) {
  if (!props.mistakeId || saving.value) return
  const next = marked.value === key ? '' : key
  saving.value = true
  try {
    await request.patch(
      `/mistakes/${props.mistakeId}/error-reason`,
      { reason: next },
      { silent: true },
    )
    marked.value = next
    toast.success(next ? '已标记错因' : '已清除错因')
  } catch (err) {
    // 错误提示由请求拦截器统一处理；本地保持原状态
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="visible" class="er-chips" role="group" aria-label="错因归因">
    <span class="er-label"><Icon name="target" :size="13" /> 这道题为什么错？</span>
    <button
      v-for="r in REASONS"
      :key="r.key"
      type="button"
      class="er-chip"
      :class="{ on: marked === r.key }"
      :aria-pressed="marked === r.key"
      :disabled="saving"
      @click="mark(r.key)"
    >
      {{ r.label }}
    </button>
  </div>
</template>

<style scoped>
.er-chips {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 0 2px;
}
.er-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--ink-3);
}
.er-chip {
  height: 28px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink-2);
  font-size: 12.5px;
  cursor: pointer;
  transition:
    background var(--dur-1) var(--ease),
    color var(--dur-1) var(--ease),
    border-color var(--dur-1) var(--ease);
}
.er-chip:hover {
  border-color: var(--accent-ring);
  color: var(--accent-ink);
}
.er-chip.on {
  background: var(--accent-soft);
  border-color: var(--accent-ring);
  color: var(--accent-ink);
  font-weight: 700;
}
.er-chip:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
