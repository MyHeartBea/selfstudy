<script setup>
/**
 * 错题卡片（v2.1 重排版）：
 * - 行内勾选框（不再悬浮遮挡标签）
 * - 知识点标签行内联解题思路（净化 LaTeX 后截断）
 * - 底部信息最多三项，逐项省略
 * - 保留 3D 倾斜 + 光泽 hover
 */
import { formatTime } from '../composables/useBaseData'
import MistakeMeta from './MistakeMeta.vue'
import MathText from './MathText.vue'
import QuestionImages from './QuestionImages.vue'
import UiStars from '../ui/UiStars.vue'
import UiTag from '../ui/UiTag.vue'
import UiCheckbox from '../ui/UiCheckbox.vue'

const props = defineProps({
  mistake: { type: Object, required: true },
  index: { type: Number, default: 0 },
  selected: { type: Boolean, default: false },
})

const emit = defineEmits(['open', 'toggle-select'])

const TILT_MAX = 3 // 最大倾斜角度，克制不炫技

// 思路文本净化：去掉 $..$ 数学记号与反斜杠命令，截断展示
function approachSummary(text, max = 22) {
  const value = String(text || '')
    .replace(/\$\$?([^$]*)\$\$?/g, '$1')
    .replace(/\\(frac|sqrt|text|mathrm|varphi|vartheta)\{([^}]*)\}\{([^}]*)\}/g, '$2/$3')
    .replace(/\\[a-zA-Z]+/g, '')
    .replace(/[{}]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return value.length > max ? `${value.slice(0, max)}…` : value
}

function onCardMove(event) {
  if (!window.matchMedia('(pointer: fine)').matches) return
  const el = event.currentTarget
  const rect = el.getBoundingClientRect()
  const px = (event.clientX - rect.left) / rect.width
  const py = (event.clientY - rect.top) / rect.height
  el.style.transform = `perspective(900px) rotateX(${(0.5 - py) * TILT_MAX}deg) rotateY(${(px - 0.5) * TILT_MAX}deg) translateY(-3px)`
  el.style.setProperty('--sheen-x', `${px * 100}%`)
  el.style.setProperty('--sheen-y', `${py * 100}%`)
}

function onCardLeave(event) {
  event.currentTarget.style.transform = ''
}

function onCheckboxChange(checked) {
  emit('toggle-select', props.mistake.id, checked)
}
</script>

<template>
  <article
    class="mistake-card card tilt"
    :class="{ picked: selected }"
    tabindex="0"
    role="button"
    @click="$emit('open', mistake.id)"
    @keydown.enter="$emit('open', mistake.id)"
    @keydown.space.prevent="$emit('open', mistake.id)"
    @mousemove="onCardMove"
    @mouseleave="onCardLeave"
  >
    <span class="card-sheen" aria-hidden="true"></span>

    <div class="card-top">
      <span class="card-index">No.{{ String(index).padStart(4, '0') }}</span>
      <MistakeMeta :mistake="mistake" compact />
      <span class="top-end" @click.stop>
        <UiStars :model-value="mistake.difficulty || 0" readonly :size="13" />
        <UiCheckbox
          :model-value="selected"
          @click.stop
          @update:model-value="onCheckboxChange"
        />
      </span>
    </div>

    <QuestionImages :images="mistake.images" :max-width="260" />

    <div class="question-text">
      <MathText :text="mistake.question" />
    </div>

    <div
      v-if="(mistake.knowledge_tags && mistake.knowledge_tags.length) || mistake.approach"
      class="tag-row"
    >
      <UiTag v-for="t in mistake.knowledge_tags || []" :key="t" size="sm">{{ t }}</UiTag>
      <span v-if="mistake.approach" class="approach-chip" :title="mistake.approach">
        {{ approachSummary(mistake.approach) }}
      </span>
    </div>

    <div class="card-foot">
      <UiTag v-if="mistake.review_paused" size="sm">已暂停</UiTag>
      <span v-else-if="mistake.next_review_at" class="foot-item" :title="'下次复习 ' + formatTime(mistake.next_review_at)">
        <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg>
        {{ formatTime(mistake.next_review_at).slice(5) }}
      </span>
      <span v-if="mistake.source_name" class="foot-item grow" :title="mistake.source_name">{{ mistake.source_name }}</span>
      <span class="foot-item">{{ formatTime(mistake.created_at).slice(0, 10) }}</span>
    </div>
  </article>
</template>

<style scoped>
.mistake-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  cursor: pointer;
  height: 100%;
}
.mistake-card:hover {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--line));
  box-shadow: var(--shadow-2);
}
.mistake-card.picked {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent), var(--shadow-1);
}
.mistake-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.card-index {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 800;
  font-style: italic;
  color: var(--accent-ink);
  border-bottom: 2px solid var(--accent);
  padding: 0 2px 1px;
  margin-right: 2px;
  letter-spacing: 0.04em;
}
/* 星级 + 勾选框作为整体靠右，永远不与标签重叠 */
.top-end {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  flex: none;
}

.question-text {
  font-size: 13.8px;
  line-height: 26px;
  color: var(--ink);
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  /* 笔记本横线纸面 */
  background: repeating-linear-gradient(
    0deg,
    transparent 0 25px,
    color-mix(in srgb, var(--ink) 4.5%, transparent) 25px 26px
  );
  border-radius: 2px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  align-items: center;
}
.approach-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 2px 9px;
  border-radius: 999px;
  background: var(--teal-soft);
  color: var(--teal);
  font-size: 11.5px;
  font-weight: 700;
}

.card-foot {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11.5px;
  color: var(--ink-3);
}
.foot-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  white-space: nowrap;
  flex: none;
}
.foot-item.grow {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  justify-content: flex-start;
}
</style>
