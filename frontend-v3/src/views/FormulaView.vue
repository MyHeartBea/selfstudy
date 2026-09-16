<!--
  FormulaView —— 公式背诵（公式笺）
  ---------------------------------------------------------------------------
  契约：GET /api/formulas - [{ id, category, title, content, created_at, updated_at }]（无分页）
  公式内容走 KaTeX 渲染 —— 这是全站唯一需要数学渲染的页面，
  所以 KaTeX 只在这一页按需加载（路由级懒加载 + 独立 chunk，见 vite.config.js 的 manualChunks）。

  交互：分类筛选 + 搜索 + 整卡可点看全文；背诵模式（过卡循环）留到后续。
-->
<script setup>
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'

import { usePageMotion } from '../design/usePageMotion'

import { formulasApi } from '../core/api'
import InkCard from '../ui/InkCard.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiField from '../ui/UiField.vue'
import UiModal from '../ui/UiModal.vue'
import UiTag from '../ui/UiTag.vue'

/** 数学渲染按需加载：只有这一页用得到 KaTeX */
const MathText = defineAsyncComponent(() => import('../components/MathText.vue'))

const CATEGORIES = ['高等数学', '线性代数', '概率统计', '英语背诵', '政治背诵', '408背诵', '其他']

const pageRoot = ref(null)
const loading = ref(true)
const errorText = ref('')
const items = ref([])

const cat = ref('')
const search = ref('')

const detailOpen = ref(false)
const detail = ref(null)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return items.value.filter((f) => {
    if (cat.value && f.category !== cat.value) return false
    if (!q) return true
    return (f.title || '').toLowerCase().includes(q) || (f.content || '').toLowerCase().includes(q)
  })
})

/** 每类数量：用于分类条上的计数 */
const counts = computed(() => {
  const m = new Map()
  items.value.forEach((f) => m.set(f.category, (m.get(f.category) || 0) + 1))
  return m
})

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    items.value = (await formulasApi.list()) || []
  } catch (e) {
    errorText.value = e?.message || '无法载入公式'
    items.value = []
  } finally {
    loading.value = false
  }
}

function openDetail(row) {
  detail.value = row
  detailOpen.value = true
}

onMounted(load)

/** 页面级动效：错峰入场 + 视差 + 磁吸 + 路径描绘（见 design/usePageMotion） */
usePageMotion(pageRoot, { stagger: 55 })
</script>

<template>
  <main ref="pageRoot" id="main" class="pad">
    <header class="head">
      <h1 class="mono page-h1">公式背诵</h1>
      <span class="mono">{{ items.length }} 条 · 当前 {{ filtered.length }}</span>
    </header>

    <div class="tools reveal" data-reveal>
      <UiField v-model="search" label="搜索" placeholder="公式名或内容" />
      <div class="cats">
        <button type="button" class="cbtn" :class="{ on: !cat }" @click="cat = ''">
          全部<span class="mono n">{{ items.length }}</span>
        </button>
        <button
          v-for="c in CATEGORIES"
          :key="c"
          type="button"
          class="cbtn"
          :class="{ on: cat === c }"
          :disabled="!counts.get(c)"
          @click="cat = c"
        >
          {{ c }}<span class="mono n">{{ counts.get(c) || 0 }}</span>
        </button>
      </div>
    </div>

    <UiEmpty v-if="loading" variant="skeleton" :rows="3" />
    <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText">
      <template #action><UiButton variant="solid" @click="load">重试</UiButton></template>
    </UiEmpty>
    <UiEmpty
      v-else-if="!filtered.length"
      title="没有匹配的公式"
      hint="换个分类或清空搜索；也可以在录入页把公式存进来"
    />

    <div v-else class="wall reveal" data-reveal>
      <InkCard v-for="row in filtered" :key="row.id" spine="var(--gold)" @select="openDetail(row)">
        <div class="chead">
          <UiTag tone="gold" size="sm">{{ row.category }}</UiTag>
        </div>
        <h2 class="ftitle">{{ row.title }}</h2>
        <!-- 卡片内只渲染公式本体；KaTeX 懒加载 -->
        <div class="fprev"><MathText :text="row.content" /></div>
      </InkCard>
    </div>

    <UiModal v-model="detailOpen" :title="detail ? detail.title : '公式'" size="md">
      <div v-if="detail" class="det">
        <UiTag tone="gold" size="sm">{{ detail.category }}</UiTag>
        <div class="dfull"><MathText :text="detail.content" /></div>
        <details class="raw">
          <summary class="mono">查看原始写法</summary>
          <pre class="mono">{{ detail.content }}</pre>
        </details>
      </div>
      <template #foot>
        <UiButton variant="quiet" @click="detailOpen = false">关闭</UiButton>
      </template>
    </UiModal>
  </main>
</template>

<style scoped>
.page-h1 {
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
  font-weight: 400;
  letter-spacing: 0.12em;
  margin: 0;
}
.pad {
  position: relative;
  z-index: var(--z-content);
  max-width: var(--col);
  margin: 0 auto;
  padding: clamp(84px, 12vh, 132px) var(--pad) 70px;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(16px, 3vh, 30px);
}

.tools {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: clamp(16px, 3vh, 30px);
}
.cats {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.cbtn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  font-size: var(--fs-sm);
  color: var(--ink-1);
  transition:
    border-color 0.22s var(--e-settle),
    color 0.22s var(--e-settle),
    background 0.22s var(--e-settle);
}
.cbtn:hover:not(:disabled) {
  border-color: var(--gold);
  color: var(--ink-0);
}
.cbtn.on {
  border-color: var(--gold);
  color: var(--ink-0);
  background: oklch(0.775 0.12 85 / 0.1);
}
.cbtn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.n {
  color: var(--ink-3);
}

.wall {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr));
  gap: 14px;
}
.chead {
  margin-bottom: 9px;
}
.ftitle {
  font-size: var(--fs-h2);
  font-weight: 500;
  margin-bottom: 10px;
  letter-spacing: -0.01em;
}
/* 公式预览：横向可滚动，避免长公式把卡片撑破 */
.fprev {
  overflow-x: auto;
  color: var(--ink-0);
}

.det {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.dfull {
  padding: 16px;
  background: var(--sky-0);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow-x: auto;
}
.raw summary {
  cursor: pointer;
  color: var(--ink-3);
}
.raw pre {
  margin-top: 8px;
  padding: 12px;
  background: var(--sky-0);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  color: var(--ink-2);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
