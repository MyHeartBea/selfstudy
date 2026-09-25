<script setup>
/**
 * 打印背诵稿（A4）：勾选的错题 / 知识点 / 公式排成一份纸面文稿。
 * 入口：错题列表勾选后「打印背诵稿」、知识点/公式页工具栏「打印当前筛选」。
 * 屏幕上是预览 + 打印按钮；@media print 时只留正文（全局 print 样式已隐藏外壳）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import request from '../api/request'
import { questionTypeName, subjectName } from '../composables/useBaseData'
import MathText from '../components/MathText.vue'
import RichText from '../components/RichText.vue'
import UiButton from '../ui/UiButton.vue'
import UiLoadError from '../ui/UiLoadError.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import Icon from '../ui/Icon.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const loadError = ref(false)
const rows = ref([])

const TYPE_TITLES = {
  mistakes: '错题背诵稿',
  knowledge: '知识点背诵稿',
  formula: '公式背诵稿',
}
const type = computed(() => {
  const value = String(route.query.type || 'mistakes')
  return TYPE_TITLES[value] ? value : 'mistakes'
})
const title = computed(() => TYPE_TITLES[type.value])

async function load() {
  loading.value = true
  loadError.value = false
  rows.value = []
  try {
    const ids = String(route.query.ids || '')
      .split(',')
      .map(Number)
      .filter((n) => Number.isInteger(n) && n > 0)
    if (type.value === 'mistakes') {
      // 数量即勾选数（上限 100，列表每页最多选这么多），逐条取详情最稳
      const details = await Promise.all(
        ids.slice(0, 100).map((id) => request.get(`/mistakes/${id}`)),
      )
      rows.value = details.map((res) => res.data.data)
    } else if (type.value === 'formula') {
      const res = await request.get('/formulas')
      const all = res.data.data || []
      rows.value = ids.length ? all.filter((item) => ids.includes(item.id)) : all
    } else {
      const res = await request.get('/knowledge', { params: { page: 1, page_size: 500 } })
      const all = res.data.data?.items || []
      rows.value = ids.length ? all.filter((item) => ids.includes(item.id)) : all
    }
  } catch (err) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)

const today = new Date().toISOString().slice(0, 10)

function isChoiceLike(item) {
  return ['choice', 'multi'].includes(item.question_type)
}

function doPrint() {
  window.print()
}
</script>

<template>
  <div class="page print-view">
    <div class="print-toolbar">
      <UiButton variant="ghost" @click="router.back()">返回</UiButton>
      <span class="pt-tip"
        >{{ title }} · 共 {{ rows.length }} 条 · 打印前可在浏览器里选「横向/纵向」</span
      >
      <UiButton variant="primary" :disabled="!rows.length" @click="doPrint">
        <Icon name="notebook" :size="15" />
        打印
      </UiButton>
    </div>

    <UiLoadError v-if="loadError" text="背诵稿加载失败" @retry="load" />
    <UiEmpty v-else-if="!loading && !rows.length" seal="印" text="没有可打印的内容" />
    <template v-else>
      <header class="sheet-head">
        <h1 class="sheet-title">{{ title }}</h1>
        <p class="sheet-sub">研错本 · {{ today }} · 共 {{ rows.length }} 条</p>
      </header>

      <!-- 错题：题干在前、答案解析在后，一段一题不跨页 -->
      <template v-if="type === 'mistakes'">
        <article v-for="(item, i) in rows" :key="item.id" class="sheet-item">
          <div class="item-head">
            <span class="item-no">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="item-meta">
              {{ subjectName(item.subject_id) }} · {{ questionTypeName(item.question_type) }}
              <template v-if="item.difficulty"> · 难度 {{ item.difficulty }}</template>
            </span>
          </div>
          <div class="item-question"><MathText :text="item.question || '（无题干）'" /></div>
          <div v-if="isChoiceLike(item)" class="item-options">
            <p
              v-for="key in ['a', 'b', 'c', 'd', 'e', 'f', 'g']"
              :key="key"
              :class="{ empty: !item['option_' + key] }"
            >
              <b>{{ key.toUpperCase() }}.</b>
              <MathText :text="item['option_' + key] || ''" />
            </p>
          </div>
          <div class="item-answer">
            <span class="label">答案</span>
            <MathText :text="item.correct_answer || '暂无'" />
          </div>
          <div v-if="item.analysis" class="item-analysis">
            <span class="label">解析</span>
            <RichText :text="item.analysis" />
          </div>
          <div v-if="item.approach" class="item-approach">
            <span class="label">思路</span>{{ item.approach }}
          </div>
        </article>
      </template>

      <!-- 知识点：一张知识笺一段 -->
      <template v-else-if="type === 'knowledge'">
        <article v-for="(item, i) in rows" :key="item.id" class="sheet-item">
          <div class="item-head">
            <span class="item-no">{{ String(i + 1).padStart(2, '0') }}</span>
            <h2 class="item-name">{{ item.tag_name }}</h2>
            <span class="item-meta">{{ subjectName(item.subject_id) }}</span>
          </div>
          <div v-if="item.summary" class="item-body"><RichText :text="item.summary" /></div>
        </article>
      </template>

      <!-- 公式：按分类归段 -->
      <template v-else>
        <article v-for="(item, i) in rows" :key="item.id" class="sheet-item">
          <div class="item-head">
            <span class="item-no">{{ String(i + 1).padStart(2, '0') }}</span>
            <h2 class="item-name">{{ item.title }}</h2>
            <span class="item-meta">{{ item.category }}</span>
          </div>
          <div class="item-body"><RichText :text="item.content" /></div>
        </article>
      </template>
    </template>
  </div>
</template>

<style scoped>
.print-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
.pt-tip {
  color: var(--ink-3);
  font-size: 12.5px;
  margin-right: auto;
}

.sheet-head {
  margin: 6px 0 18px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--ink);
}
.sheet-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 26px;
  letter-spacing: 0.08em;
}
.sheet-sub {
  margin: 6px 0 0;
  color: var(--ink-3);
  font-size: 12.5px;
}

.sheet-item {
  padding: 14px 2px;
  border-bottom: 1px solid var(--line);
  break-inside: avoid;
}
.item-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}
.item-no {
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 15px;
  color: var(--accent-ink);
}
.item-name {
  margin: 0;
  font-size: 16.5px;
}
.item-meta {
  margin-left: auto;
  color: var(--ink-3);
  font-size: 12px;
  white-space: nowrap;
}
.item-question {
  font-size: 13.5px;
  line-height: 1.9;
}
.item-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px 18px;
  margin: 6px 0 0;
}
.item-options p {
  margin: 0;
  font-size: 12.8px;
  line-height: 1.8;
}
.item-options p.empty {
  visibility: hidden;
}
.item-options b {
  margin-right: 4px;
}
.item-answer,
.item-analysis,
.item-approach {
  margin-top: 8px;
  font-size: 12.8px;
  line-height: 1.85;
}
.item-answer .label,
.item-analysis .label,
.item-approach .label {
  display: inline-block;
  margin-right: 8px;
  padding: 0 6px;
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  color: var(--ink-2);
}
.item-approach {
  color: var(--ink-2);
}

@media print {
  .print-toolbar {
    display: none !important;
  }
  .sheet-title {
    font-size: 20px;
  }
}
</style>
