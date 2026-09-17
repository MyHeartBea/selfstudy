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

function onCheckboxChange(checked) {
  emit('toggle-select', props.mistake.id, checked)
}

const spineColor = computed(() => subjectColor(props.mistake.subject_id))

// 英语整篇：卡片预览用原文前 1-2 句，并显示该篇题目数量
const englishQuestionCount = computed(() => {
  const m = props.mistake
  if (!m || m.passage_text === undefined) return 0
  return 1 + (m.english_questions || []).length
})
const cardText = computed(() => {
  const m = props.mistake
  if (m.passage_text) {
    const sents = String(m.passage_text)
      .split(/(?<=[.!?])\s+/)
      .map((s) => s.trim())
      .filter(Boolean)
    return sents.slice(0, 2).join(' ') || m.passage_text
  }
  return m.question || ''
})
const hasImage = computed(
  () => Array.isArray(props.mistake.images) && props.mistake.images.length > 0,
)
</script>

<template>
  <!--
    悬停复合特效统一由 .km-live 提供（styles/km-live.css + composables/kmLive.js）。
    原来自带的 tilt（3°、自己写 transform）已移除：两处都动 transform 会互相覆盖，
    且参考稿的幅度是 8-10°，3° 几乎看不出来 —— 用户反馈"鼠标放上去没有明显的动态特效"。
  -->
  <article
    class="mistake-card card km-live"
    :class="{ picked: selected }"
    :style="{ '--enter-delay': `${Math.min(pos, 11) * 55}ms`, '--spine': spineColor }"
    tabindex="0"
    role="button"
    @click="$emit('open', mistake.id)"
    @keydown.enter="$emit('open', mistake.id)"
    @keydown.space.prevent="$emit('open', mistake.id)"
  >
    <!-- ⑤ 幽灵序号：压在背景的巨型编号 -->
    <span class="km-live__ghost" aria-hidden="true">{{ String(index).padStart(2, '0') }}</span>
    <!-- ③ 四角取景框 ④ 扫描线 -->
    <!-- 顶边标尺：悬停时从左向右展开的朱砂线（"被选中"的空间语言） -->
    <span class="km-live__rule" aria-hidden="true"></span>
    <span class="km-live__corner tl" aria-hidden="true"></span>
    <span class="km-live__corner tr" aria-hidden="true"></span>
    <span class="km-live__corner bl" aria-hidden="true"></span>
    <span class="km-live__corner br" aria-hidden="true"></span>
    <span class="km-live__scan" aria-hidden="true"></span>

    <i class="spine" aria-hidden="true"></i>

    <div class="km-live__inner">
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
            <span v-if="englishQuestionCount > 1" class="passage-count"
              >英语整篇 · 共 {{ englishQuestionCount }} 题</span
            >
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
          <span
            v-else-if="mistake.next_review_at"
            class="foot-item"
            :title="'下次复习 ' + formatTime(mistake.next_review_at)"
          >
            <svg
              viewBox="0 0 24 24"
              width="12"
              height="12"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
            >
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v5l3.5 2" />
            </svg>
            {{ formatTime(mistake.next_review_at).slice(5) }}
          </span>
          <span v-if="mistake.source_name" class="foot-item grow" :title="mistake.source_name">{{
            mistake.source_name
          }}</span>
          <span class="foot-item">{{ formatTime(mistake.created_at).slice(0, 10) }}</span>
        </div>
      </div>
    </div>
    <!-- /.km-live__inner -->
  </article>
</template>

<style scoped>
/*
  纸面配色（修一个真实可读性 bug）
  ---------------------------------------------------------------------------
  这张卡刻意做成"米色纸片"以与深色底形成纸感对比。但深色主题下，
  卡内文字会**继承主题的浅色 ink**，造成"浅字 + 浅纸"——静止状态几乎不可读；
  而悬停叠加朱砂染色后反倒更清楚，于是产生了"只有悬停才看得出"的错觉。

  这里给卡片内部显式定义一套纸面配色，不再依赖从 body 继承的主题色。
  只作用于本组件，不影响其它页面。
*/
.mistake-card {
  --paper-bg: #f1e9d9;
  --paper-bg-2: #ece3d0;
  --paper-ink: #2c2822;
  --paper-ink-2: #635c4d;
  --paper-ink-3: #8f8672;
  --paper-line: rgba(44, 40, 34, 0.12);

  /* 暖纸 + 极淡渐变 + 内亮边 —— 避免"死白"。
     纯 #fdfbf5 在深底上像一块灯箱：对比硬、无层次。
     渐变让上方略亮、下方略沉，读起来像"一张有厚度的纸"；
     内亮边模拟纸张边缘受光。 */
  background: linear-gradient(180deg, #fdf9f0 0%, #f8f2e6 46%, #f1ead9 100%);
  color: var(--paper-ink);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    inset 0 0 0 1px rgba(44, 40, 34, 0.06);
}
/* ── 图版 / 文字区的明度差（修"上下都是白的"）───────────────────────────
   原来题图容器是纯白衬板、而卡面也是亮纸色，两者几乎同色，上下连成一片白。
   这里给图版区保留白（图片需要干净底），但把它**明确成一块"图版"**：
   加一条下边线切开，形成"上图下文的版式"；文字区则用更沉的纸色。 */
.mistake-card .shot-banner {
  /* 纯白 #fff 在暖纸旁边会显得刺眼；改为暖白，与纸面同一色系 */
  background: #fbf8f1;
  border-bottom: 1px solid rgba(44, 40, 34, 0.12);
  padding: 10px 10px 12px;
}
/*
  实测发现的错位点：我先前把"纸面"加在了 .mistake-card 自身，
  但视觉主体其实是内层 .card-body —— 而它被写成了 rgb(248,242,230)，
  于是整块可见区域仍是米白，卡片自身的深色底完全看不到。
  用户说"把白色改成米白色压根没啥区别"就是因为改错了层。
  这里把纸面落到内层，并加深到"暖纸"，与纯白拉开明显差距。
*/
.mistake-card .card-body {
  background: #f1e9d9;
}
/* 题干区再沉半档，与图版形成层次 */
.mistake-card .question-text {
  color: var(--paper-ink);
}

/* 内部文字统一走纸面配色（v2 各子组件用不同类名，所以按标签与常见类兜底） */
.mistake-card :is(h1, h2, h3, h4, p, span, b, strong, em, time, dt, dd).not-this {
  color: inherit;
}
.mistake-card .seal-no,
.mistake-card .card-foot,
.mistake-card .passage-count,
.mistake-card .foot-item {
  color: var(--paper-ink-3);
}
.mistake-card .question-text,
.mistake-card .passage-preview {
  color: var(--paper-ink);
}
.mistake-card .tag-row :is(.ui-tag, span) {
  color: var(--paper-ink-2);
}

.mistake-card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 0;
  cursor: pointer;
  height: 100%;
  overflow: hidden;
  /* 入场动画**只动 opacity**，不动 transform。
     原因（实测踩到）：入场动画用 `both` 填充模式，动画结束后仍会持续占用
     transform 属性；而 .km-live 的悬停倾斜也走 transform（通过 --rx/--ry），
     结果被动画的 transform 覆盖 —— 实测悬停时 computed transform 始终是
     matrix(1,0,0,1,0,0)，倾斜完全没生效。
     所以把"位移动画"交给外层容器（.card-grid 的错峰入场），
     这里只负责淡入，避免两处争同一个属性。 */
  animation: card-fade 0.55s var(--ease) both;
  animation-delay: var(--enter-delay, 0ms);
}
@keyframes card-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
.mistake-card:hover {
  border-color: color-mix(in srgb, var(--spine) 45%, var(--line));
  box-shadow: var(--shadow-2);
}
.mistake-card.picked {
  border-color: var(--accent);
  box-shadow:
    0 0 0 1px var(--accent),
    var(--shadow-1);
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
  background: linear-gradient(
    180deg,
    var(--spine),
    color-mix(in srgb, var(--spine) 35%, transparent)
  );
  opacity: 0.9;
  transition: width 0.25s var(--spring);
  z-index: 2;
}
.mistake-card:hover .spine {
  width: 6px;
}

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
.shot-banner :deep(.question-images) {
  margin: 0;
}
.shot-banner :deep(.question-image) {
  border: none;
  background: transparent;
  padding: 0;
}
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
  box-shadow:
    0 2px 6px color-mix(in srgb, var(--accent-hover) 40%, transparent),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
  transition: transform 0.25s var(--spring);
}
.mistake-card:hover .seal-no {
  transform: rotate(0deg) scale(1.05);
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
.passage-preview {
  margin: 0;
  line-height: 1.8;
}
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
