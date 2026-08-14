<script setup>
import { formatTime } from '../composables/useBaseData'
import MathText from './MathText.vue'
import MistakeMeta from './MistakeMeta.vue'

defineProps({
  mistake: { type: Object, required: true },
  index: { type: Number, default: 0 },
})

defineEmits(['open'])
</script>

<template>
  <el-card
    shadow="hover"
    class="mistake-card"
    tabindex="0"
    role="button"
    @click="$emit('open', mistake.id)"
    @keydown.enter="$emit('open', mistake.id)"
  >
    <div class="card-top">
      <span class="card-index">{{ String(index).padStart(4, '0') }}</span>
      <MistakeMeta :mistake="mistake" compact />
      <el-rate
        :model-value="mistake.difficulty"
        disabled
        size="small"
        class="card-rate"
      />
    </div>
    <div class="question-text">
      <MathText :text="mistake.question" />
    </div>
    <div class="tag-row">
      <el-tag v-for="t in mistake.knowledge_tags" :key="t" size="small" class="tag-item">
        {{ t }}
      </el-tag>
    </div>
    <div class="card-foot">
      <span v-if="mistake.approach" class="approach-chip">{{ mistake.approach }}</span>
      <el-tag
        v-if="mistake.review_paused"
        size="small"
        type="info"
        effect="plain"
      >
        已暂停
      </el-tag>
      <span v-else-if="mistake.next_review_at" class="source">
        下次 {{ formatTime(mistake.next_review_at).slice(5) }}
      </span>
      <span v-if="mistake.source_name" class="source">{{ mistake.source_name }}</span>
      <span v-if="mistake.source" class="source">{{ mistake.source }}</span>
      <span v-else class="source"></span>
      <span>{{ formatTime(mistake.created_at) }}</span>
    </div>
  </el-card>
</template>

<style scoped>
.card-index {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--ink-700);
}

.approach-chip {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--teal-soft);
  color: var(--teal);
  font-size: 12px;
  font-weight: 700;
}

.mistake-card:focus-visible {
  outline: 2px solid var(--teal);
  outline-offset: 2px;
}
</style>
