<script setup>
import { formatTime } from '../composables/useBaseData'

defineProps({
  records: { type: Array, default: () => [] },
})
</script>

<template>
  <el-collapse-item
    :title="'复习记录（' + records.length + '）'"
    name="history"
  >
    <div v-if="records.length">
      <div v-for="record in records" :key="record.id" class="history-row">
        <el-tag :type="record.result === 'correct' ? 'success' : 'danger'" size="small">
          {{ record.result === 'correct' ? '记得' : '记错' }}
        </el-tag>
        <span>{{ formatTime(record.reviewed_at) }}</span>
        <span class="history-note">{{ record.note || '无备注' }}</span>
      </div>
    </div>
    <p v-else class="muted">还没有复习记录。</p>
  </el-collapse-item>
</template>
