<script setup>
/** 作文批改结果展示（纯视觉，无副作用）：分数档 + 四维 + 逐句改错 diff + 范文。 */
import { computed, ref } from 'vue'

import MathText from '../components/MathText.vue'
import RichText from '../components/RichText.vue'
import UiTag from '../ui/UiTag.vue'
import Icon from '../ui/Icon.vue'
import { wordDiff } from '../utils/essayDiff'
import { DIMENSION_LABELS, essayScorePct } from '../composables/essayKinds'

const props = defineProps({
  // 后端 ai_essay.normalize_essay_grade 的输出
  result: { type: Object, required: true },
  transcript: { type: String, default: '' },
})

const pct = computed(() => essayScorePct(props.result.score, props.result.max_score))
const dims = computed(() =>
  Object.entries(DIMENSION_LABELS).map(([key, label]) => ({
    key,
    label,
    score: props.result.dimensions?.[key] ?? 0,
  })),
)

// 逐句改错按 diff 预计算：AI 常给出与原文完全一致的句子，那类不进列表
const corrections = computed(() =>
  (props.result.corrections || []).map((c) => ({ ...c, parts: wordDiff(c.original, c.corrected) })),
)

const showTranscript = ref(false)
const showModel = ref(false)
</script>

<template>
  <div class="er">
    <!-- 分数印 + 档位 -->
    <div class="er-head">
      <div class="er-seal" :style="{ '--pct': pct + '%' }">
        <span class="er-score serif">{{ result.score }}</span>
        <span class="er-max">/ {{ result.max_score }}</span>
      </div>
      <div class="er-headline">
        <div class="er-band">
          {{ result.band || '未定档' }}
          <span class="er-kind">{{ result.kind_name }}</span>
        </div>
        <p class="er-overall"><MathText :text="result.overall || '（无总评）'" /></p>
        <div class="er-meta">
          <span v-if="result.estimated_word_count">约 {{ result.estimated_word_count }} 词</span>
          <UiTag v-for="e in result.top_errors || []" :key="e" size="sm" color="accent" soft>
            {{ e }}
          </UiTag>
        </div>
      </div>
    </div>

    <!-- 四维得分 -->
    <div class="er-dims">
      <div v-for="d in dims" :key="d.key" class="er-dim">
        <span class="er-dim-label">{{ d.label }}</span>
        <span class="er-dim-bar"
          ><i :style="{ width: essayScorePct(d.score, result.max_score) + '%' }"></i
        ></span>
        <span class="er-dim-num">{{ d.score }}</span>
      </div>
    </div>

    <!-- 逐句改错 -->
    <section v-if="corrections.length" class="er-sec">
      <h4 class="er-h">
        <Icon name="pencil" :size="14" /> 逐句改错（{{ corrections.length }} 处）
      </h4>
      <ol class="er-corr">
        <li v-for="(c, i) in corrections" :key="i" class="er-corr-item">
          <div class="er-corr-line">
            <span v-for="(p, j) in c.parts" :key="j" :class="'d-' + p.type">{{ p.text }}</span>
          </div>
          <div class="er-corr-note">
            <span v-if="c.type" class="er-corr-type">{{ c.type }}</span>
            <MathText :text="c.note" />
          </div>
        </li>
      </ol>
    </section>

    <!-- 亮点 -->
    <section v-if="(result.highlights || []).length" class="er-sec">
      <h4 class="er-h"><Icon name="star" :size="14" /> 写得好的地方</h4>
      <ul class="er-list good">
        <li v-for="(h, i) in result.highlights" :key="i"><MathText :text="h" /></li>
      </ul>
    </section>

    <!-- 升级表达 -->
    <section v-if="(result.upgrade_tips || []).length" class="er-sec">
      <h4 class="er-h"><Icon name="trending" :size="14" /> 表达升级</h4>
      <ul class="er-list">
        <li v-for="(t, i) in result.upgrade_tips" :key="i"><MathText :text="t" /></li>
      </ul>
    </section>

    <section v-if="result.weakness_advice" class="er-sec advice">
      <h4 class="er-h"><Icon name="target" :size="14" /> 下一步怎么练</h4>
      <p><MathText :text="result.weakness_advice" /></p>
    </section>

    <!-- 同题范文 -->
    <section v-if="result.model_version" class="er-sec">
      <button type="button" class="er-toggle" @click="showModel = !showModel">
        <Icon :name="showModel ? 'minus' : 'plus'" :size="13" />
        {{ showModel ? '收起同题范文' : '看这篇能拿满分的同题范文' }}
      </button>
      <div v-if="showModel" class="er-model">
        <RichText :text="result.model_version" />
      </div>
    </section>

    <!-- 转录原文（视觉识别结果，可核对） -->
    <section v-if="transcript" class="er-sec">
      <button type="button" class="er-toggle" @click="showTranscript = !showTranscript">
        <Icon :name="showTranscript ? 'minus' : 'plus'" :size="13" />
        {{ showTranscript ? '收起识别转录' : '核对 AI 从图片转录出的文字' }}
      </button>
      <pre v-if="showTranscript" class="er-transcript">{{ transcript }}</pre>
    </section>
  </div>
</template>

<style scoped>
.er {
  display: grid;
  gap: 16px;
}
.er-head {
  display: flex;
  gap: 18px;
  align-items: flex-start;
}
.er-seal {
  position: relative;
  flex: none;
  width: 92px;
  height: 92px;
  border-radius: 20px;
  display: grid;
  place-items: center;
  align-content: center;
  color: var(--accent-ink);
  background: conic-gradient(var(--accent) var(--pct), var(--surface-2) 0);
  box-shadow: var(--shadow-1);
}
/* 内圈留白，外环即得分比例 */
.er-seal::after {
  content: '';
  position: absolute;
  inset: 7px;
  border-radius: 15px;
  background: var(--surface);
}
.er-score {
  position: relative;
  z-index: 1;
  font-size: 34px;
  font-weight: 900;
  line-height: 1;
  color: var(--ink);
}
.er-max {
  position: relative;
  z-index: 1;
  font-size: 11.5px;
  color: var(--ink-3);
}
.er-headline {
  flex: 1;
  min-width: 0;
}
.er-band {
  font-size: var(--fs-h2);
  font-weight: 700;
  color: var(--ink);
  display: flex;
  gap: 10px;
  align-items: baseline;
  flex-wrap: wrap;
}
.er-kind {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-ink);
  background: var(--accent-soft);
  padding: 2px 9px;
  border-radius: 999px;
}
.er-overall {
  margin: 7px 0 0;
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--ink-2);
}
.er-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 9px;
  font-size: 12px;
  color: var(--ink-3);
}
.er-dims {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px 18px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface-2);
}
.er-dim {
  display: grid;
  grid-template-columns: 62px 1fr 20px;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--ink-2);
}
.er-dim-bar {
  height: 5px;
  border-radius: 999px;
  background: var(--surface);
  overflow: hidden;
}
.er-dim-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent-grad);
  transition: width 0.5s var(--ease);
}
.er-dim-num {
  text-align: right;
  font-weight: 700;
  color: var(--ink);
}
.er-sec {
  display: grid;
  gap: 8px;
}
.er-h {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
}
.er-h :deep(svg) {
  color: var(--accent);
}
.er-corr {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
  counter-reset: c;
}
.er-corr-item {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--accent);
  border-radius: var(--r-sm);
  background: var(--surface);
}
.er-corr-line {
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink);
  word-break: break-word;
}
.d-same {
  color: var(--ink-2);
}
.d-del {
  color: var(--red);
  text-decoration: line-through;
  text-decoration-thickness: 1.5px;
}
.d-ins {
  color: var(--green);
  font-weight: 600;
  text-decoration: underline;
  text-decoration-color: color-mix(in srgb, var(--green) 55%, transparent);
  text-underline-offset: 3px;
}
.er-corr-note {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin-top: 5px;
  font-size: 12.5px;
  color: var(--ink-3);
}
.er-corr-type {
  flex: none;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-size: 11px;
  font-weight: 700;
}
.er-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 5px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-2);
}
.er-list.good li::marker {
  color: var(--gold);
}
.advice p {
  margin: 0;
  font-size: 13px;
  line-height: 1.8;
  color: var(--ink-2);
}
.er-toggle {
  justify-self: start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
  color: var(--ink-2);
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.2s var(--ease);
}
.er-toggle:hover {
  border-color: var(--accent-ring);
  color: var(--accent-ink);
}
.er-model {
  padding: 12px 14px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--r-md);
  background: var(--surface-2);
  font-size: 13.5px;
  line-height: 1.85;
  color: var(--ink);
}
.er-transcript {
  margin: 0;
  padding: 12px 14px;
  border-radius: var(--r-md);
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: 12.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--ink-2);
  max-height: 320px;
  overflow: auto;
}
</style>
