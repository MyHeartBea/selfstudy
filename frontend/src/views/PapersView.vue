<script setup>
/**
 * 真题库：扫描历年真题文件夹 → AI 拆题入库 → 整卷模考。
 * 流水线状态轮询；题目浏览器支持查看题干/选项/答案/解析。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import MathText from '../components/MathText.vue'
import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import GlassCard from '../ui/GlassCard.vue'
import StageBadge from '../ui/StageBadge.vue'
import Icon from '../ui/Icon.vue'

const router = useRouter()

const scanning = ref(false)
const candidates = ref([])
const papers = ref([])
const selected = ref(null) // 选中的卷（含 questions）
const importing = ref({})
let pollTimer = 0

const SUBJECT_TONES = {
  英语二: 'var(--teal)',
  数学二: 'var(--green)',
  计算机408: 'var(--blue)',
  政治: 'var(--gold)',
}

const paperCandidates = computed(() =>
  candidates.value.filter((c) => c.kind === 'paper'),
)

const activeImporting = computed(() =>
  papers.value.some((p) => ['pending', 'extracting', 'structuring'].includes(p.status)),
)

const statusLabel = {
  pending: '排队中',
  extracting: '提取文本',
  structuring: 'AI 拆题',
  done: '已入库',
  error: '失败',
}

async function scan() {
  scanning.value = true
  try {
    const res = await request.get('/papers/scan', { silent: true })
    candidates.value = res.data.data || []
    if (!candidates.value.length) toast.info(`真题文件夹里没有找到 docx/pdf（${''}检查 D:\\km-v2\\真题）`)
  } catch (err) {
    toast.error('扫描失败')
  } finally {
    scanning.value = false
  }
}

async function loadPapers() {
  try {
    const res = await request.get('/papers', { silent: true })
    papers.value = res.data.data || []
  } catch (err) {
    // 静默
  }
}

async function importPaper(c) {
  const key = c.rel_path
  importing.value[key] = true
  try {
    await request.post(
      '/papers',
      {
        subject: c.subject,
        year: c.year,
        title: `${c.subject} ${c.year} 年真题`,
        source_path: c.rel_path,
        answer_path: c.answer_path || '',
      },
      { silent: true },
    )
    toast.success(`已加入导入队列：${c.subject} ${c.year}`)
    await loadPapers()
    startPolling()
  } catch (err) {
    toast.error('导入失败')
  } finally {
    importing.value[key] = false
  }
}

async function openPaper(p) {
  try {
    const res = await request.get(`/papers/${p.id}`, { silent: true })
    selected.value = res.data.data
  } catch (err) {
    toast.error('加载卷面失败')
  }
}

async function removePaper(p) {
  const ok = await confirmDialog({
    title: '删除真题',
    message: `删除《${p.title}》及其全部题目？源文件不受影响。`,
    danger: true,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await request.delete(`/papers/${p.id}`)
    if (selected.value?.id === p.id) selected.value = null
    toast.success('已删除')
    loadPapers()
  } catch (err) {
    // 拦截器统一提示
  }
}

function mockPaper(p) {
  if (!p.question_count) {
    toast.warning('这份卷还没有题目')
    return
  }
  router.push({
    path: '/review',
    query: { mode: 'mock', paper_id: p.id, duration: 180 },
  })
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    loadPapers().then(() => {
      if (!activeImporting.value) stopPolling()
    })
  }, 2500)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = 0
  }
}

onMounted(() => {
  loadPapers()
  scan()
})
onUnmounted(stopPolling)
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Paper Bank</div>
        <h2>真题库</h2>
        <p class="view-desc">历年真题原卷入库，AI 拆题配答案；整卷模考，错题自动收进错题本。</p>
      </div>
      <div class="header-actions">
        <UiButton variant="outline" :loading="scanning" @click="scan">
          <Icon name="refresh" :size="15" />
          重新扫描
        </UiButton>
      </div>
    </div>

    <!-- 我的卷库 -->
    <section class="sec">
      <div class="sec-title">
        <span>我的卷库</span>
        <span v-if="activeImporting" class="importing-tip">
          <Icon name="refresh" :size="12" class="spin" />
          导入流水线运行中…
        </span>
      </div>
      <UiEmpty v-if="!papers.length" text="卷库还是空的——从下方扫描结果里挑一份真题导入" icon="notebook" />
      <div v-else class="paper-grid">
        <GlassCard v-for="p in papers" :key="p.id" class="paper-card" :hover="true">
          <template #badge>
            <StageBadge v-if="p.status === 'done'" :text="`${p.question_count} 题`" />
          </template>
          <div class="paper-head" @click="openPaper(p)">
            <span class="p-seal serif" :style="{ '--pcol': SUBJECT_TONES[p.subject] || 'var(--accent)' }">
              {{ (p.subject || '卷').slice(0, 1) }}
            </span>
            <div class="p-title-box">
              <b class="p-title">{{ p.title }}</b>
              <span class="p-sub">{{ p.subject }} · {{ p.year }} · {{ p.question_count }} 题</span>
            </div>
            <UiTag
              size="sm"
              :color="p.status === 'done' ? 'var(--green)' : p.status === 'error' ? 'var(--red)' : 'var(--gold)'"
            >
              {{ statusLabel[p.status] || p.status }}
            </UiTag>
          </div>
          <p v-if="p.status === 'structuring' && p.status_note" class="p-note">{{ p.status_note }}</p>
          <p v-else-if="p.status === 'error'" class="p-note err">{{ p.status_note }}</p>
          <p v-else-if="p.status === 'done'" class="p-note ok">{{ p.status_note }}</p>
          <div class="p-actions">
            <UiButton size="sm" variant="primary" :disabled="p.status !== 'done'" @click="mockPaper(p)">
              <Icon name="play" :size="13" />
              整卷模考
            </UiButton>
            <UiButton size="sm" variant="ghost" @click="openPaper(p)">查看卷面</UiButton>
            <button type="button" class="p-del" aria-label="删除" @click="removePaper(p)">
              <Icon name="trash" :size="14" />
            </button>
          </div>
        </GlassCard>
      </div>
    </section>

    <!-- 卷面浏览 -->
    <section v-if="selected" class="sec">
      <div class="sec-title">
        <span>卷面 · {{ selected.title }}</span>
        <UiButton size="sm" variant="ghost" @click="selected = null">收起</UiButton>
      </div>
      <div class="paper-view">
        <div v-for="(q, i) in selected.questions" :key="q.id" class="pq">
          <p v-if="q.passage" class="pq-passage"><MathText :text="q.passage" /></p>
          <div class="pq-row">
            <span class="pq-no num">{{ q.no }}</span>
            <div class="pq-main">
              <div class="pq-q"><MathText :text="q.question" /></div>
              <div v-if="q.option_a" class="pq-opts">
                <span v-for="k in ['a', 'b', 'c', 'd']" :key="k" class="pq-opt">
                  <b>{{ k.toUpperCase() }}.</b> <MathText :text="q['option_' + k]" />
                </span>
              </div>
              <div v-if="q.correct_answer || q.analysis" class="pq-answer">
                <span v-if="q.correct_answer" class="pq-ans-badge">答案 {{ q.correct_answer }}</span>
                <span v-if="q.analysis" class="pq-analysis"><MathText :text="q.analysis" /></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 扫描导入 -->
    <section class="sec">
      <div class="sec-title">
        <span>扫描结果</span>
        <span class="cap">来自 D:\km-v2\真题 · 只列试卷文件（解析/答案自动配对）</span>
      </div>
      <UiEmpty v-if="!paperCandidates.length && !scanning" text="没有扫到试卷文件" icon="inbox" />
      <div v-else class="cand-grid">
        <div v-for="c in paperCandidates" :key="c.rel_path" class="cand-row" :class="{ imported: c.imported }">
          <span class="c-seal" :style="{ '--pcol': SUBJECT_TONES[c.subject] || 'var(--ink-3)' }">{{ c.year || '—' }}</span>
          <div class="c-main">
            <b :title="c.name">{{ c.name }}</b>
            <span class="c-sub">
              {{ c.subject || '未识别' }} · {{ c.size_kb }} KB
              <UiTag v-if="c.answer_path" size="sm" color="var(--green)" soft>已配答案</UiTag>
              <UiTag v-if="c.imported" size="sm" soft>已导入</UiTag>
            </span>
          </div>
          <UiButton
            size="sm"
            variant="outline"
            :loading="importing[c.rel_path]"
            :disabled="c.imported"
            @click="importPaper(c)"
          >
            {{ c.imported ? '已导入' : '导入' }}
          </UiButton>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.sec { margin-bottom: 26px; }
.sec-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 14px;
}
.sec-title .cap { font-family: var(--font-body); font-size: 12.5px; font-weight: 400; }
.importing-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--gold);
  font-family: var(--font-body);
  font-weight: 400;
}
.spin { animation: spin 0.9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 卷库卡片 */
.paper-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 14px;
}
.paper-head {
  display: flex;
  align-items: center;
  gap: 11px;
  cursor: pointer;
}
.p-seal {
  width: 44px;
  height: 44px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 13px;
  background: color-mix(in srgb, var(--pcol) 13%, transparent);
  border: 1px solid color-mix(in srgb, var(--pcol) 30%, transparent);
  color: var(--pcol);
  font-weight: 900;
  font-size: 20px;
  transform: rotate(-3deg);
  transition: transform 0.3s var(--spring);
}
.paper-head:hover .p-seal { transform: rotate(0deg) scale(1.06); }
.p-title-box { min-width: 0; margin-right: auto; }
.p-title {
  display: block;
  font-size: 14.5px;
  font-weight: 700;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.p-sub { font-size: 12px; color: var(--ink-3); }
.p-note { margin: 8px 0 0; font-size: 12px; color: var(--ink-3); }
.p-note.err { color: var(--red); }
.p-note.ok { color: var(--green); }
.p-actions { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.p-del {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  padding: 5px;
  border-radius: 7px;
  transition: all 0.15s var(--ease);
}
.p-del:hover { color: var(--red); background: var(--red-soft); }

/* 卷面浏览 */
.paper-view { display: flex; flex-direction: column; }
.pq { border-bottom: 1px dashed var(--line); padding: 14px 0; }
.pq:last-child { border-bottom: none; }
.pq-passage {
  margin: 0 0 12px;
  padding: 14px 18px;
  border-radius: var(--r-md);
  background: var(--surface-2);
  font-family: var(--font-display);
  font-size: 14.5px;
  line-height: 1.9;
  color: var(--ink);
  white-space: pre-wrap;
}
.pq-row { display: flex; gap: 12px; }
.pq-no {
  flex: none;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-weight: 800;
  font-size: 13px;
}
.pq-main { flex: 1; min-width: 0; }
.pq-q { font-size: 14px; line-height: 1.85; color: var(--ink); }
.pq-opts { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 18px; margin-top: 8px; font-size: 13.5px; color: var(--ink-2); }
.pq-opt b { color: var(--accent-ink); margin-right: 2px; }
.pq-answer {
  margin-top: 9px;
  padding: 9px 13px;
  border-radius: 9px;
  background: var(--green-soft);
  font-size: 12.8px;
  line-height: 1.8;
  color: var(--ink-2);
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.pq-ans-badge {
  flex: none;
  font-weight: 800;
  color: var(--green);
  background: var(--surface);
  border-radius: 7px;
  padding: 2px 9px;
}

/* 扫描候选 */
.cand-grid { display: flex; flex-direction: column; gap: 8px; }
.cand-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface);
  transition: border-color 0.15s var(--ease);
}
.cand-row:hover { border-color: var(--line-strong); }
.cand-row.imported { opacity: 0.55; }
.c-seal {
  width: 42px;
  height: 42px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: color-mix(in srgb, var(--pcol) 12%, transparent);
  color: var(--pcol);
  font-weight: 900;
  font-size: 13px;
  font-family: var(--font-display);
}
.c-main { flex: 1; min-width: 0; }
.c-main b {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.c-sub { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--ink-3); }
</style>
