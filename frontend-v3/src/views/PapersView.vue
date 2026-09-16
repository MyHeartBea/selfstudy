<!--
  PapersView —— 真题库
  ---------------------------------------------------------------------------
  语义：真题 = 已归档的星图底片；扫描 = 巡天。

  契约（基线实测）：
    GET /api/papers      - [{ id, title, year, subject, status, status_note,
                              question_count, answered_count, source_path, answer_path }]
    GET /api/papers/scan - [{ name, rel_path, kind, size_kb, subject, year,
                              imported, mixed, sources[], answer_path, answer_kind }]

  设计要点：
   - 扫描是**显式动作**（点按钮），不自动跑：目录可能很大，不能一进页面就卡住
   - `imported` 已导入的条目在扫描结果里标出来，避免重复导入
   - 失败条目的 status_note 必须显示 —— 否则用户只看到"失败"却不知道原因
-->
<script setup>
import { computed, onMounted, ref } from 'vue'

import { papersApi } from '../core/api/extra'
import { toast } from '../ui/toast'
import { usePageMotion } from '../design/usePageMotion'
import InkCard from '../ui/InkCard.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiModal from '../ui/UiModal.vue'
import UiTag from '../ui/UiTag.vue'

const pageRoot = ref(null)
usePageMotion(pageRoot, { stagger: 55 })

const loading = ref(true)
const errorText = ref('')
const items = ref([])

const scanOpen = ref(false)
const scanning = ref(false)
const scanResult = ref(null)
const scanError = ref('')

const imported = computed(() => items.value.filter((p) => p.status === 'imported'))
const pending = computed(() => items.value.filter((p) => p.status !== 'imported'))
const failed = computed(() => items.value.filter((p) => p.status === 'failed'))

const STATUS_TONE = { imported: 'vein', pending: 'gold', failed: 'red-shift' }
const STATUS_TEXT = { imported: '已入库', pending: '待导入', failed: '失败' }

function statusOf(row) {
  return {
    tone: STATUS_TONE[row.status] || 'ink',
    text: STATUS_TEXT[row.status] || row.status || '未知',
  }
}

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    items.value = (await papersApi.list()) || []
  } catch (e) {
    errorText.value = e?.message || '无法载入真题库'
    items.value = []
  } finally {
    loading.value = false
  }
}

/** 扫描：显式触发，避免一进页面就因大目录卡住 */
async function runScan() {
  scanning.value = true
  scanError.value = ''
  scanResult.value = null
  try {
    scanResult.value = (await papersApi.scan()) || []
    if (!scanResult.value.length) toast.info('没有扫描到新的真题文件')
    else toast.success(`扫描到 ${scanResult.value.length} 个文件`)
  } catch (e) {
    scanError.value = e?.message || '扫描失败'
  } finally {
    scanning.value = false
  }
}

onMounted(load)
</script>

<template>
  <main id="main" ref="pageRoot" class="pad">
    <header class="head">
      <span class="mono">[08] ARCHIVE · 真题库</span>
      <span class="mono">{{ items.length }} 套 · 已入库 {{ imported.length }}</span>
    </header>

    <div class="tools reveal" data-reveal>
      <p class="lead">
        真题按套归档；扫描会巡一遍真题目录，把题目与答案配对后列出来。
        <b>扫描是显式动作</b>——不自动跑，避免目录很大时一进页面就卡住。
      </p>
      <UiButton variant="solid" @click="((scanOpen = true), runScan())">巡天扫描</UiButton>
    </div>

    <UiEmpty v-if="loading" variant="skeleton" :rows="3" />
    <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText">
      <template #action><UiButton variant="solid" @click="load">重试</UiButton></template>
    </UiEmpty>
    <UiEmpty
      v-else-if="!items.length"
      title="还没有导入真题"
      hint="点右上角「巡天扫描」找找本机的真题文件"
    />

    <template v-else>
      <!-- 失败条目单独提示：只说"失败"不说原因的界面是没用的 -->
      <div v-if="failed.length" class="warn reveal" data-reveal>
        <span class="mono wlabel">有 {{ failed.length }} 套导入失败</span>
        <ul class="wlist">
          <li v-for="f in failed" :key="f.id">
            <span class="wtitle">{{ f.title }}</span>
            <span class="mono wnote">{{ f.status_note || '未给出原因' }}</span>
          </li>
        </ul>
      </div>

      <div class="wall reveal" data-reveal>
        <InkCard
          v-for="row in items"
          :key="row.id"
          :spine="row.status === 'failed' ? 'var(--redshift)' : 'var(--ink-3)'"
          :interactive="false"
        >
          <div class="chead">
            <UiTag :tone="statusOf(row).tone" size="sm" dot>{{ statusOf(row).text }}</UiTag>
            <span v-if="row.year" class="mono yr">{{ row.year }}</span>
            <span v-if="row.subject" class="mono subj">{{ row.subject }}</span>
          </div>
          <h3 class="ptitle">{{ row.title }}</h3>
          <p class="pmeta mono">
            {{ row.question_count || 0 }} 题 · 已作答 {{ row.answered_count || 0 }}
          </p>
          <p v-if="row.source_path" class="mono path">{{ row.source_path }}</p>
        </InkCard>
      </div>

      <p v-if="pending.length" class="mono note">
        另有 {{ pending.length }} 套待导入 —— 导入流程在后续接上。
      </p>
    </template>

    <UiModal v-model="scanOpen" title="巡天扫描" size="lg">
      <UiEmpty v-if="scanning" variant="skeleton" thumb :rows="3" />
      <UiEmpty v-else-if="scanError" title="扫描失败" :hint="scanError">
        <template #action><UiButton variant="solid" @click="runScan">重试</UiButton></template>
      </UiEmpty>
      <div v-else-if="scanResult && scanResult.length" class="scanlist">
        <div v-for="f in scanResult" :key="f.rel_path" class="srow">
          <div class="smain">
            <span class="sname">{{ f.name }}</span>
            <span class="mono smeta">
              {{ f.kind === 'answer' ? '答案' : '题目' }}
              <template v-if="f.mixed"> · 题答同文件</template>
              · {{ f.size_kb }} KB
              <template v-if="f.subject"> · {{ f.subject }}</template>
              <template v-if="f.year"> · {{ f.year }}</template>
            </span>
            <span v-if="f.sources && f.sources.length" class="mono ssrc">
              来源 {{ f.sources.length }} 个：{{ f.sources.map((s) => s.rel_path).join(' / ') }}
            </span>
          </div>
          <UiTag :tone="f.imported ? 'vein' : 'gold'" size="sm">
            {{ f.imported ? '已导入' : '未导入' }}
          </UiTag>
        </div>
      </div>
      <UiEmpty v-else title="没有扫描到文件" hint="确认真题目录里有 PDF 或图片" />
      <template #foot>
        <UiButton variant="quiet" @click="((scanOpen = false), load())">关闭</UiButton>
      </template>
    </UiModal>
  </main>
</template>

<style scoped>
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
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: clamp(18px, 3vh, 32px);
  flex-wrap: wrap;
}
.lead {
  max-width: 62ch;
  color: var(--ink-2);
  line-height: 1.8;
}
.lead b {
  color: var(--ink-0);
  font-weight: 500;
}

.warn {
  padding: 14px 16px;
  border: 1px solid oklch(0.665 0.196 34 / 0.45);
  border-radius: var(--radius);
  background: oklch(0.665 0.196 34 / 0.06);
  margin-bottom: 18px;
}
.wlabel {
  color: var(--redshift);
}
.wlist {
  list-style: none;
  margin-top: 9px;
  display: grid;
  gap: 6px;
}
.wlist li {
  display: flex;
  gap: 10px;
  align-items: baseline;
  font-size: var(--fs-sm);
  flex-wrap: wrap;
}
.wtitle {
  color: var(--ink-0);
}
.wnote {
  color: var(--ink-2);
}

.wall {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 330px), 1fr));
  gap: 14px;
}
.chead {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 10px;
}
.yr,
.subj {
  color: var(--ink-3);
}
.subj {
  margin-left: auto;
}
.ptitle {
  font-size: var(--fs-h2);
  font-weight: 500;
  line-height: 1.5;
  margin-bottom: 8px;
}
.pmeta {
  color: var(--ink-2);
}
.path {
  margin-top: 7px;
  color: var(--ink-3);
  word-break: break-all;
  line-height: 1.6;
}
.note {
  margin-top: 20px;
  color: var(--ink-3);
}

.scanlist {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  max-height: 54vh;
  overflow-y: auto;
}
.srow {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  background: var(--sky-1);
}
.smain {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}
.sname {
  color: var(--ink-0);
}
.smeta,
.ssrc {
  color: var(--ink-3);
  word-break: break-all;
}
</style>
