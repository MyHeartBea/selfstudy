<script setup>
/** 复习记录时间线 */
import { formatTime } from '../composables/useBaseData'
import Icon from '../ui/Icon.vue'

defineProps({
  records: { type: Array, default: () => [] },
})
</script>

<template>
  <div class="history">
    <div v-if="records.length" class="history-list">
      <div v-for="record in records" :key="record.id" class="history-row">
        <span class="history-dot" :class="record.result === 'correct' ? 'ok' : 'bad'">
          <Icon :name="record.result === 'correct' ? 'check' : 'x'" :size="11" />
        </span>
        <span class="history-time">{{ formatTime(record.reviewed_at) }}</span>
        <span class="history-note">{{ record.note || '无备注' }}</span>
      </div>
    </div>
    <p v-else class="muted">还没有复习记录。</p>
  </div>
</template>

<style scoped>
.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.history-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12.5px;
  color: var(--ink-2);
}
.history-dot {
  flex: none;
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}
.history-dot.ok { background: var(--green-soft); color: var(--green); }
.history-dot.bad { background: var(--red-soft); color: var(--red); }
.history-time { color: var(--ink-3); font-variant-numeric: tabular-nums; }
.history-note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
