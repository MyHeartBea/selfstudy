<script setup>
/**
 * 错题卡片 v4（墨韵 2.0 收敛版）：
 * - 首图 = 卡片顶部通栏「图版」：等高裁齐、白底衬板、干净统一
 * - 左缘科目色脊 + 朱砂印章序号
 * - 3D 倾斜 + 光泽 hover + 级联入场
 * - 行内勾选框 / 知识点标签 / 思路 chip / 底部信息
 */
import { computed } from 'vue'
import { formatTime, subjectColor } from '../composables/useBaseData'
import MistakeMeta from './MistakeMeta.vue'
import RichText from './RichText.vue'
import QuestionImages from './QuestionImages.vue'
import UiStars from '../ui/UiStars.vue'
import UiTag from '../ui/UiTag.vue'
import UiCheckbox from '../ui/UiCheckbox.vue'

const props = defineProps({
  mistake: { type: Object, required: true },
  index: { type: Number, default: 0 }, // 展示序号（倒序编号）
  pos: { type: Number, default: 0 }, // 页内位置（级联入场）
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

const spineColor = computed(() => subjectColor(props.mistake.subject_id))

// 英语整篇：卡片预览用原文前 1-2 句，并显示该篇题目数量
const englishQuestionCount = computed(() => {
  const m = props.mistake
  if (!m || m.passage_text === undefined) return 0
  return 1 + ((m.english_questions || []).length)
})
const cardText = computed(() => {
  const m = props.mistake
  if (m.passage_text) {
    const sents = String(m.passage_text).split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter(Boolean)
    return sents.slice(0, 2).join(' ') || m.passage_text
  }
  return m.question || ''
})
const hasImage = computed(() => Array.isArray(props.mistake.images) && props.mistake.images.length > 0)
</script>

<template>
  <article
    class="mistake-card card tilt"
    :class="{ picked: selected }"
    :style="{ '--enter-delay': `${Math.min(pos, 11) * 55}ms`, '--spine': spineColor }"
    tabindex="0"
    role="button"
    @click="$emit('open', mistake.id)"
    @keydown.enter="$emit('open', mistake.id)"
    @keydown.space.prevent="$emit('open', mistake.id)"
    @mousemove="onCardMove"
    @mouseleave="onCardLeave"
  >
    <i class="spine" aria-hidden="true"></i>
    <span class="card-sheen" aria-hidden="true"></span>

    <!-- 通栏图版：首图等高裁齐，白底衬板（走缩略图通道） -->
    <div v-if="hasImage" class="shot-banner">
      <QuestionImages :images="mistake.images" :max-width="480" :count="1" thumb />
    </div>

    <div class="card-body">
      <div class="card-top">
        <span class="seal-no">{{ String(index).padStart(4, '0') }}</span>
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

      <div class="question-text">
        <template v-if="mistake.passage_text">
          <p class="passage-preview">{{ cardText }}</p>
          <span v-if="englishQuestionCount > 1" class="passage-count">英语整篇 · 共 {{ englishQuestionCount }} 题</span>
        </template>
        <RichText v-else :text="mistake.question" />
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
    </div>
  </article>
</template>

<style scoped>
.mistake-card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 0;
  cursor: pointer;
  height: 100%;
  overflow: hidden;
  animation: card-in 0.55s var(--ease) both;
  animation-delay: var(--enter-delay, 0ms);
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(18px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.mistake-card:hover {
  border-color: color-mix(in srgb, var(--spine) 45%, var(--line));
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

/* 科目色脊：左缘垂直墨条（通高） */
.spine {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  border-radius: 4px 0 0 4px;
  background: linear-gradient(180deg, var(--spine), color-mix(in srgb, var(--spine) 35%, transparent));
  opacity: 0.9;
  transition: width 0.25s var(--spring);
  z-index: 2;
}
.mistake-card:hover .spine { width: 6px; }

/* 通栏图版 */
.shot-banner {
  height: 148px;
  flex: none;
  background: #fffdf9;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 6px;
}
.shot-banner :deep(.question-images) { margin: 0; }
.shot-banner :deep(.question-image) { border: none; background: transparent; padding: 0; }
.shot-banner :deep(.question-image img) {
  max-width: 100% !important;
  max-height: 130px !important;
  object-fit: contain;
}

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 13px 16px 13px 21px;
  min-width: 0;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
/* 序号印章 */
.seal-no {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 8px;
  background: var(--accent-grad);
  color: #fff;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 800;
  font-style: italic;
  letter-spacing: 0.06em;
  transform: rotate(-2deg);
  box-shadow: 0 2px 6px color-mix(in srgb, var(--accent-hover) 40%, transparent), inset 0 1px 0 rgba(255, 255, 255, 0.25);
  transition: transform 0.25s var(--spring);
}
.mistake-card:hover .seal-no { transform: rotate(0deg) scale(1.05); }

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
.passage-preview { margin: 0; line-height: 1.8; }
.passage-count {
  display: inline-block;
  margin-top: 6px;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--accent-ink);
  background: var(--accent-soft);
  padding: 2px 8px;
  border-radius: 999px;
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
