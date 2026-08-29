<script setup>
/** 分页：页码窗口 + 每页条数选择 + 总数。 */
import { computed } from 'vue'
import UiSelect from './UiSelect.vue'
import Icon from './Icon.vue'

const props = defineProps({
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 10 },
  sizes: { type: Array, default: () => [10, 20, 50] },
})

const emit = defineEmits(['update:page', 'update:pageSize', 'change'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pages = computed(() => {
  const current = props.page
  const last = totalPages.value
  const window = []
  const push = (value) => window.includes(value) || window.push(value)
  push(1)
  for (let p = current - 1; p <= current + 1; p++) {
    if (p > 1 && p < last) push(p)
  }
  if (last > 1) push(last)
  return window
    .sort((a, b) => a - b)
    .flatMap((value, index, arr) => {
      const prev = arr[index - 1]
      return index > 0 && value - prev > 1 ? ['…', value] : [value]
    })
})

function go(value) {
  if (value === '…' || value === props.page || value < 1 || value > totalPages.value) return
  emit('update:page', value)
  emit('change', value)
}

function onSizeChange() {
  emit('update:page', 1)
  emit('change', 1)
}
</script>

<template>
  <div v-if="total" class="pagination">
    <span class="count-tip">共 {{ total }} 条</span>
    <div class="page-btns">
      <button class="page-btn nav" :disabled="page <= 1" aria-label="上一页" @click="go(page - 1)">
        <Icon name="chevron-left" :size="14" />
      </button>
      <template v-for="(p, i) in pages" :key="`${p}-${i}`">
        <span v-if="p === '…'" class="page-ellipsis">…</span>
        <button v-else class="page-btn" :class="{ active: p === page }" @click="go(p)">{{ p }}</button>
      </template>
      <button class="page-btn nav" :disabled="page >= totalPages" aria-label="下一页" @click="go(page + 1)">
        <Icon name="chevron-right" :size="14" />
      </button>
    </div>
    <UiSelect
      compact
      :model-value="pageSize"
      :options="sizes"
      @update:model-value="(v) => emit('update:pageSize', v)"
      @change="onSizeChange"
    />
  </div>
</template>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.page-btns {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-btn {
  min-width: 30px;
  height: 30px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--ink-2);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.12s;
}
.page-btn:hover:not(:disabled) { background: var(--surface-2); color: var(--ink); }
.page-btn.active { background: var(--accent); color: #fff; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.page-ellipsis { color: var(--ink-3); padding: 0 2px; }
</style>
