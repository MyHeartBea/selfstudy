<!--
  EnglishPanel —— 英语精读面板（中英对照 + 逐句拆解 + 短语/生词与词性）
  ---------------------------------------------------------------------------
  用户明确要求："我之前的 v2 是中英文左右边对照的 还有什么语句词性之类的东西，看准了一并加上"
  所以这一版按 **v2 的数据字段**（看准了再实现）逐项呈现：

    english_sentences[] - { text, translation, structure, pattern }
        · 左右对照：左侧英文原句，右侧中文译文
        · 句下注释：句型 pattern + 结构 structure（两者不同时都显示）
    english_phrases[]   - { phrase, meaning, pos, ... }
        · 短语 + 释义 + **词性标注（pos）**
    english_words[]     - { word, phonetic, meaning, pos, ... }
        · 单词 + 音标 + 释义 + **词性**
    passage_text / passage_translation - 整篇兜底

  视觉主张（不是传统列表）：
    · 对照采用**悬挂在左侧的句序号**（等宽、细），英文与中文两栏以一条细轴线分隔；
      滚动时整句作为一个可聚焦单元，而不是把中英堆成一坨
    · 词性用**极细描边小签**（等宽大字距），不用彩色实心胶囊
    · 生词/短语用**两列密排**（不是一行一条的表格），像词典的密度
-->
<script setup>
import { computed } from 'vue'

import MathText from './MathText.vue'

const props = defineProps({
  data: { type: Object, default: null },
})

/** 逐句对照：优先用 AI 切好的句子；缺失时按标点兜底切分整篇 */
const sentences = computed(() => {
  const list = props.data?.english_sentences || []
  const items = list
    .filter((s) => s && s.text)
    .map((s) => ({
      text: s.text,
      translation: s.translation || '',
      structure: s.structure || '',
      pattern: s.pattern || '',
    }))
  if (items.length) return items

  const raw = String(props.data?.passage_text || '')
  if (!raw) return []
  return raw
    .split(/\n+/)
    .map((t) => t.trim())
    .filter(Boolean)
    .flatMap((para) => para.split(/(?<=[.!?])\s+/))
    .map((t) => ({ text: t.trim(), translation: '', structure: '', pattern: '' }))
    .filter((s) => s.text)
})

const phrases = computed(() =>
  (props.data?.english_phrases || []).filter((p) => p && (p.phrase || p.text)),
)
const words = computed(() => (props.data?.english_words || []).filter((w) => w && w.word))

/** 整篇是否用了 AI 切句（决定要不要显示"整篇"区块） */
const hasSentenceTranslation = computed(() => sentences.value.some((s) => s.translation))

/** 词性：不同来源字段名不同，统一取 */
function posOf(item) {
  return item?.pos || item?.part_of_speech || ''
}
function termOf(item) {
  return item?.phrase || item?.text || item?.word || ''
}
</script>

<template>
  <section v-if="sentences.length" class="eng" aria-label="英语精读">
    <!-- ① 逐句对照 -->
    <div class="block">
      <h3 class="bhead mono">
        <span>逐句对照</span>
        <span class="dim">{{ sentences.length }} 句</span>
      </h3>

      <ol class="pairs">
        <li v-for="(s, i) in sentences" :key="i" class="pair">
          <span class="no mono" aria-hidden="true">{{ String(i + 1).padStart(2, '0') }}</span>

          <div class="cols">
            <p class="en" lang="en"><MathText :text="s.text" /></p>
            <p v-if="s.translation" class="zh"><MathText :text="s.translation" /></p>
            <p v-else class="zh none mono">（此句暂无译文）</p>
          </div>

          <!-- 句型 / 结构：两者相同只显示一次（v2 的处理方式） -->
          <p v-if="s.pattern || s.structure" class="note">
            <span v-if="s.pattern" class="pat">{{ s.pattern }}</span>
            <span v-if="s.structure && s.structure !== s.pattern" class="str">
              结构：{{ s.structure }}
            </span>
          </p>
        </li>
      </ol>
    </div>

    <!-- ② 短语与词性 -->
    <div v-if="phrases.length" class="block">
      <h3 class="bhead mono">
        <span>短语</span>
        <span class="dim">{{ phrases.length }} 条</span>
      </h3>
      <ul class="lex">
        <li v-for="(p, i) in phrases" :key="i">
          <span class="term">{{ termOf(p) }}</span>
          <span v-if="posOf(p)" class="pos mono">{{ posOf(p) }}</span>
          <span class="mean">{{ p.meaning || p.translation || '' }}</span>
        </li>
      </ul>
    </div>

    <!-- ③ 生词 -->
    <div v-if="words.length" class="block">
      <h3 class="bhead mono">
        <span>生词</span>
        <span class="dim">{{ words.length }} 个</span>
      </h3>
      <ul class="lex">
        <li v-for="(w, i) in words" :key="i">
          <span class="term">{{ w.word }}</span>
          <span v-if="w.phonetic" class="pho mono">{{ w.phonetic }}</span>
          <span v-if="posOf(w)" class="pos mono">{{ posOf(w) }}</span>
          <span class="mean">{{ w.meaning || w.translation || '' }}</span>
        </li>
      </ul>
    </div>

    <!-- ④ 整篇：AI 未逐句给译文时，用整篇对照兜底 -->
    <div v-if="!hasSentenceTranslation && data?.passage_translation" class="block">
      <h3 class="bhead mono"><span>整篇译文</span></h3>
      <p class="zh whole"><MathText :text="data.passage_translation" /></p>
    </div>
  </section>
</template>

<style scoped>
.eng {
  display: flex;
  flex-direction: column;
  gap: clamp(20px, 3.4vh, 34px);
}
.block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.bhead {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 7px;
  border-bottom: 1px solid var(--line);
  color: var(--ink-1);
}
.bhead .dim {
  color: var(--ink-3);
}

/* ── 逐句对照 ─────────────────────────────────────────────── */
.pairs {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.pair {
  position: relative;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 12px;
  padding: 13px 12px 13px 0;
  border-bottom: 1px solid var(--line);
  transition: background 0.3s var(--e-settle);
}
.pair:hover {
  background: var(--sky-2);
}
/* 句序号悬挂在左，等宽细字 —— 像批注的页边编号 */
.no {
  color: var(--ink-3);
  padding-top: 3px;
  text-align: right;
}
.cols {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: clamp(12px, 2vw, 30px);
  align-items: start;
}
/* 两栏之间的细轴线：中英对照的分界 */
.en {
  position: relative;
  padding-right: clamp(8px, 1.4vw, 18px);
  border-right: 1px solid var(--line-strong);
  color: var(--ink-0);
  line-height: 1.85;
  overflow-wrap: anywhere;
}
.zh {
  color: var(--ink-1);
  line-height: 1.9;
  overflow-wrap: anywhere;
}
.zh.none {
  color: var(--ink-3);
}
.zh.whole {
  white-space: pre-wrap;
}
.note {
  grid-column: 2 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 9px;
  font-size: var(--fs-sm);
  line-height: 1.75;
}
/* 句型：红移色（重点信号）；结构：次级灰 */
.pat {
  color: var(--redshift);
}
.str {
  color: var(--ink-2);
}

/* ── 短语 / 生词：两列密排，像词典而不是表格 ─────────────── */
.lex {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.lex li {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 11px 14px;
  background: var(--sky-1);
}
.lex li:hover {
  background: var(--sky-2);
}
.term {
  color: var(--ink-0);
  font-weight: 500;
  letter-spacing: 0.01em;
}
.pho {
  color: var(--vein);
}
.lex .mean {
  color: var(--ink-2);
  font-size: var(--fs-sm);
  line-height: 1.65;
}
/* 词性：极细描边小签，不用彩色实心胶囊 */
.pos {
  align-self: flex-start;
  padding: 0 5px;
  border: 1px solid var(--line-strong);
  border-radius: 2px;
  color: var(--ink-2);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  line-height: 1.7;
}

@media (max-width: 820px) {
  .cols {
    grid-template-columns: 1fr;
  }
  .en {
    border-right: 0;
    border-bottom: 1px solid var(--line);
    padding: 0 0 8px;
  }
  .note {
    grid-column: 1 / -1;
  }
}
</style>
