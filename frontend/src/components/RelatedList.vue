<script setup>
/** 知识点补充 + 同知识点错题联动 */
import { ref, watch } from 'vue'

import RichText from './RichText.vue'
import { subjectColor, subjectName, truncate } from '../composables/useBaseData'
import UiTag from '../ui/UiTag.vue'
import Icon from '../ui/Icon.vue'

const props = defineProps({
  knowledgeExtra: { type: Object, default: null },
  relatedKnowledge: { type: Array, default: () => [] },
  relatedMistakes: { type: Array, default: () => [] },
})

const emit = defineEmits(['go-knowledge', 'switch'])

const expandedId = ref(null)
const openPanel = ref('knowledge')

watch(
  () => props.relatedMistakes,
  () => {
    expandedId.value = null
  },
)

function togglePanel(name) {
  openPanel.value = openPanel.value === name ? '' : name
}

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
  <div class="collapse">
    <section class="collapse-item">
      <button type="button" class="collapse-head" @click="togglePanel('knowledge')">
        <span>知识点补充</span>
        <Icon name="chevron-down" :size="15" class="collapse-arrow" :class="{ open: openPanel === 'knowledge' }" />
      </button>
      <div v-if="openPanel === 'knowledge'" class="collapse-body">
        <RichText
          v-if="knowledgeExtra && knowledgeExtra.summary"
          :text="knowledgeExtra.summary"
        />
        <p v-else class="muted">暂无补充，可前往知识点库添加。</p>

        <template v-if="relatedKnowledge && relatedKnowledge.length">
          <div class="section-label" style="margin-top: 12px">关联知识点</div>
          <div v-for="rk in relatedKnowledge" :key="rk.id" class="related-kn-card">
            <div
              class="related-kn-title"
              role="link"
              tabindex="0"
              @click="emit('go-knowledge', rk.tag_name)"
              @keydown.enter="emit('go-knowledge', rk.tag_name)"
            >
              {{ rk.tag_name }}
              <span v-if="rk.subject_name" class="muted">
                · {{ rk.subject_name }}{{ rk.sub_subject_name ? ' / ' + rk.sub_subject_name : '' }}
              </span>
            </div>
            <template v-if="rk.summary">
              <RichText v-if="expandedId === rk.id" :text="rk.summary" />
              <p v-else class="muted" style="margin: 4px 0 4px">{{ summaryPreview(rk.summary) }}</p>
              <button type="button" class="link-btn" @click="toggleSummary(rk.id, $event)">
                {{ expandedId === rk.id ? '收起' : '展开' }}
              </button>
            </template>
            <p v-else class="muted" style="margin: 4px 0 0">暂无摘要，可前往知识点库补充。</p>
          </div>
        </template>
      </div>
    </section>

    <section class="collapse-item">
      <button type="button" class="collapse-head" @click="togglePanel('related')">
        <span>同知识点错题（{{ relatedMistakes.length }}）</span>
        <Icon name="chevron-down" :size="15" class="collapse-arrow" :class="{ open: openPanel === 'related' }" />
      </button>
      <div v-if="openPanel === 'related'" class="collapse-body">
        <div v-if="relatedMistakes.length" class="related-grid">
          <div
            v-for="rm in relatedMistakes"
            :key="rm.id"
            class="related-card"
            role="button"
            tabindex="0"
            @click="emit('switch', rm.id)"
            @keydown.enter="emit('switch', rm.id)"
          >
            <span class="related-question">{{ truncate(rm.question, 40) }}</span>
            <UiTag :color="subjectColor(rm.subject_id)" size="sm">
              {{ subjectName(rm.subject_id) }}
            </UiTag>
          </div>
        </div>
        <p v-else class="muted">暂无同知识点错题。</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.collapse {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  overflow: hidden;
  margin-top: 14px;
}
.collapse-item + .collapse-item { border-top: 1px solid var(--line); }

.collapse-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 11px 14px;
  border: none;
  background: var(--surface-2);
  color: var(--ink);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
.collapse-arrow { transition: transform 0.18s; color: var(--ink-3); }
.collapse-arrow.open { transform: rotate(180deg); }

.collapse-body { padding: 12px 14px; }

.link-btn {
  border: none;
  background: transparent;
  color: var(--accent-ink);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.related-kn-card {
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  padding: 10px 12px;
  margin: 8px 0;
  background: var(--surface-2);
  transition: border-color 0.15s;
}
.related-kn-card:hover { border-color: var(--accent); }
.related-kn-title {
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 6px;
  cursor: pointer;
}
.related-kn-title:hover { color: var(--accent-ink); }

.related-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.related-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  padding: 9px 12px;
  background: var(--surface-2);
  cursor: pointer;
  transition: border-color 0.15s;
}
.related-card:hover { border-color: var(--accent); }
.related-question { font-size: 13px; color: var(--ink); }
</style>
