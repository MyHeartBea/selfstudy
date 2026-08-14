<script setup>
import { ref, watch } from 'vue'

import RichText from './RichText.vue'
import { subjectColor, subjectName, truncate } from '../composables/useBaseData'

const props = defineProps({
  knowledgeExtra: { type: Object, default: null },
  relatedKnowledge: { type: Array, default: () => [] },
  relatedMistakes: { type: Array, default: () => [] },
})

const emit = defineEmits(['go-knowledge', 'switch'])

const expandedId = ref(null)

watch(
  () => props.relatedMistakes,
  () => {
    expandedId.value = null
  },
)

function toggleSummary(id, event) {
  event.stopPropagation()
  expandedId.value = expandedId.value === id ? null : id
}

function summaryPreview(text) {
  const value = String(text || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .join(' ')
    .replace(/[#$*`|]/g, '')
    .trim()
  return value.length > 80 ? `${value.slice(0, 80)}…` : value
}
</script>

<template>
  <el-collapse-item title="知识点补充" name="knowledge">
    <RichText
      v-if="knowledgeExtra && knowledgeExtra.summary"
      :text="knowledgeExtra.summary"
    />
    <p v-else class="muted">暂无补充，可前往知识点库添加。</p>
    <template v-if="relatedKnowledge && relatedKnowledge.length">
      <div class="section-label" style="margin-top: 10px">关联知识点</div>
      <div
        v-for="rk in relatedKnowledge"
        :key="rk.id"
        class="related-kn-card"
      >
        <div
          class="related-kn-title"
          role="link"
          tabindex="0"
          @click="emit('go-knowledge', rk.tag_name)"
          @keydown.enter="emit('go-knowledge', rk.tag_name)"
          @keydown.space.prevent="emit('go-knowledge', rk.tag_name)"
        >
          {{ rk.tag_name }}
          <span v-if="rk.subject_name" class="muted">
            · {{ rk.subject_name }}{{ rk.sub_subject_name ? ' / ' + rk.sub_subject_name : '' }}
          </span>
        </div>
        <template v-if="rk.summary">
          <RichText v-if="expandedId === rk.id" :text="rk.summary" />
          <p v-else class="muted" style="margin: 4px 0 0">
            {{ summaryPreview(rk.summary) }}
          </p>
          <el-button size="small" link type="primary" @click="toggleSummary(rk.id, $event)">
            {{ expandedId === rk.id ? '收起' : '展开' }}
          </el-button>
        </template>
        <p v-else class="muted" style="margin: 4px 0 0">
          暂无摘要，可前往知识点库补充。
        </p>
      </div>
    </template>
  </el-collapse-item>
  <el-collapse-item
    :title="'同知识点错题（' + relatedMistakes.length + '）'"
    name="related"
  >
    <div v-if="relatedMistakes.length">
      <div
        v-for="rm in relatedMistakes"
        :key="rm.id"
        class="related-card"
        role="button"
        tabindex="0"
        @click="emit('switch', rm.id)"
        @keydown.enter="emit('switch', rm.id)"
        @keydown.space.prevent="emit('switch', rm.id)"
      >
        <span class="related-question">{{ truncate(rm.question, 40) }}</span>
        <el-tag
          size="small"
          :color="subjectColor(rm.subject_id)"
          effect="dark"
          style="color: #fff; border-color: transparent"
        >
          {{ subjectName(rm.subject_id) }}
        </el-tag>
      </div>
    </div>
    <p v-else class="muted">暂无同知识点错题。</p>
  </el-collapse-item>
</template>

<style scoped>
.related-kn-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
  margin: 8px 0;
  cursor: pointer;
  background: #f9fafb;
  transition: border-color 0.2s;
}

.related-kn-card:hover {
  border-color: #1f5aa8;
}

.related-kn-title {
  font-weight: 600;
  color: #1d3a5f;
  margin-bottom: 6px;
}
</style>
