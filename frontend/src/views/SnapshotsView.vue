<script setup>
/**
 * 数据备份与回滚。
 *
 * 这一页把"快照"从一句话变成一件能做的事：以前批量删除/导入前会打快照，
 * 响应里也说"可回滚"，但**全站没有任何一个入口能把快照用回去** ——
 * 那句话实际上是"可回滚，请自己找 sqlite 命令行"。
 *
 * 三条不可省略的事实，页面上每条都要看得见：
 * 1. 快照只含数据库，**不含图片文件**（回滚回不了配图，也删不掉配图）；
 * 2. 回滚是**整库覆盖**，不是撤销单条操作 —— 回到某一份，那份之后的所有改动都没了；
 * 3. 覆盖前服务端会先给当前现场打一份 `before-restore`，打不出来就中止（没有反悔点不动手）。
 *
 * 确认口径：弹窗里要手输 `RESTORE`（服务端另有一份 `confirm === name` 的校验，
 * 那一道是给脚本调用兜底的 —— 让人逐字敲文件名不叫确认，叫折磨）。
 */
import { computed, onMounted, ref } from 'vue'
import request from '../api/request'
import { ageText, formatKb, labelText, snapshotTiles } from '../utils/snapshots.js'
import GlassCard from '../ui/GlassCard.vue'
import Icon from '../ui/Icon.vue'
import MetricTile from '../ui/MetricTile.vue'
import Skeleton from '../ui/Skeleton.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiLoadError from '../ui/UiLoadError.vue'
import { confirmDialog } from '../ui/confirm'
import { toast } from '../ui/toast'

const TABLE_LABEL = {
  mistakes: '错题',
  review_records: '复习记录',
  knowledge_base: '知识点',
  vocab_items: '生词',
  exam_papers: '真题卷',
}

const items = ref([])
const loading = ref(false)
const loadError = ref(false)
const busy = ref(false)
const result = ref(null)
const failed = ref('')

const tiles = computed(() => snapshotTiles(items.value))

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const res = await request.get('/snapshots', { params: { limit: 50 }, silent: true })
    items.value = res.data.data || []
  } catch (err) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

async function makeSnapshot() {
  busy.value = true
  failed.value = ''
  try {
    const res = await request.post('/snapshots', null, { params: { label: 'manual' } })
    toast.success(`已备份：${res.data.data?.name || ''}`)
    await load()
  } catch (err) {
    failed.value = err.response?.data?.message || '备份失败，备份目录可能不可写'
  } finally {
    busy.value = false
  }
}

async function makeImagesSnapshot() {
  busy.value = true
  failed.value = ''
  try {
    const res = await request.post('/snapshots/images', null, { silent: true })
    toast.success(res.data.message || '图片目录已备份')
    await load()
  } catch (err) {
    failed.value = err.response?.data?.message || '图片目录备份失败'
  } finally {
    busy.value = false
  }
}

async function restore(row) {
  const typed = await confirmDialog({
    title: '整库回滚确认',
    // 回滚点之外的每一笔都要在提示里点名，否则"回到哪一天"只能靠用户自己记
    message:
      `确定把整个数据库回到 ${row.created_at} 那一份吗？` +
      `这份之后的所有录入、复习、批改都会被覆盖（来源：${labelText(row.label)}）。` +
      '图片文件不随快照回滚。输入 RESTORE 继续。',
    danger: true,
    // 与列表里每颗按钮的文案**必须不同**：同名会让"点哪颗"在单测里靠运气
    confirmText: '确认整库回滚',
    input: {
      placeholder: '请输入 RESTORE',
      pattern: /^RESTORE$/,
      error: '请大写输入 RESTORE',
    },
  })
  if (typed === null) return
  busy.value = true
  failed.value = ''
  try {
    const res = await request.post('/snapshots/restore', { name: row.name, confirm: row.name })
    result.value = { ...res.data.data, message: res.data.message }
    toast.success('已回滚，请顺手确认一下下面的条数对不对')
    await load()
  } catch (err) {
    // 服务端每一步失败都给了人话（409/404/400），拦下就照原样留在页面上
    failed.value = err.response?.data?.message || '回滚请求失败，当前数据未改动'
  } finally {
    busy.value = false
  }
}

function countRows(data) {
  const before = data.tables_before || {}
  const after = data.tables_after || {}
  const keys = Object.keys(TABLE_LABEL).filter((k) => k in before || k in after)
  return keys.map((key) => ({
    key,
    label: TABLE_LABEL[key],
    before: before[key],
    after: after[key],
    changed: before[key] !== after[key],
  }))
}

onMounted(load)
</script>

<template>
  <div class="snv">
    <header class="snv-head">
      <div>
        <h1 class="snv-title serif">数据备份与回滚</h1>
        <p class="snv-sub">
          每次启动、每次批量导入/删除前都会留一份数据库快照。<b>回滚是整库覆盖</b>，
          不是撤销单条操作，而且<b>图片文件不在快照里</b>。
        </p>
      </div>
      <div class="snv-actions">
        <UiButton variant="outline" :disabled="busy || loading" @click="load">
          <Icon name="refresh" :size="14" />
          {{ loading ? '读取中…' : '刷新' }}
        </UiButton>
        <UiButton variant="primary" :disabled="busy || loading" @click="makeSnapshot">
          <Icon name="download" :size="14" />
          立刻备份一次
        </UiButton>
        <UiButton variant="outline" :disabled="busy || loading" @click="makeImagesSnapshot">
          <Icon name="image" :size="14" />
          备份图片目录
        </UiButton>
      </div>
    </header>

    <UiLoadError
      v-if="loadError"
      text="快照列表加载失败"
      hint="备份目录不可读，或服务未响应"
      @retry="load"
    />

    <template v-else-if="loading && !items.length">
      <Skeleton variant="rect" :height="88" :count="4" />
      <Skeleton variant="rect" :height="220" />
    </template>

    <template v-else>
      <section class="snv-tiles">
        <MetricTile
          v-for="t in tiles"
          :key="t.key"
          :label="t.label"
          :value="t.value"
          :unit="t.unit"
          :tone="t.tone"
          :icon="t.icon"
        />
      </section>

      <p class="snv-note">
        备份目录只保留最近 <b>20</b> 份（按文件名排序，留新去旧），另有
        <b>{{ items.length }}</b> 份列在下面，合计
        {{ formatKb(items.reduce((s, i) => s + (i.size_kb || 0), 0)) }}。 回滚前会先把当前现场另存为
        <code>before-restore</code>，所以选错还有反悔的机会。
      </p>

      <GlassCard v-if="failed" class="snv-block snv-failed">
        <h2 class="snv-h2"><Icon name="alert" :size="16" /> 这次没有做成</h2>
        <p class="snv-hint">{{ failed }}</p>
      </GlassCard>

      <GlassCard v-if="result" class="snv-block">
        <h2 class="snv-h2">
          刚才回到了 <span class="path">{{ result.name }}</span>
        </h2>
        <p class="snv-hint">{{ result.message }}</p>
        <div class="snv-table-wrap">
          <table class="snv-table">
            <thead>
              <tr>
                <th>数据</th>
                <th class="num">回滚前</th>
                <th class="num">回滚后</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in countRows(result)" :key="row.key">
                <td>{{ row.label }}</td>
                <td class="num">{{ row.before ?? '无此表' }}</td>
                <td class="num" :class="{ hit: row.changed }">{{ row.after ?? '无此表' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="snv-hint">
          反悔点：<span class="path">{{ result.safety_snapshot }}</span>
          （就在下面的列表里，可以再回滚回去）
        </p>
      </GlassCard>

      <GlassCard class="snv-block">
        <h2 class="snv-h2">
          快照列表<span class="count-tip">{{ items.length }} 份</span>
        </h2>
        <div v-if="items.length" class="snv-table-wrap">
          <table class="snv-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>来源</th>
                <th class="num">大小</th>
                <th>文件</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in items" :key="row.name">
                <td class="nowrap">
                  {{ row.created_at }}
                  <span class="ago">{{ ageText(row.created_at) }}</span>
                </td>
                <td class="nowrap">{{ labelText(row.label) }}</td>
                <td class="num">{{ formatKb(row.size_kb) }}</td>
                <td class="path">{{ row.name }}</td>
                <td class="act">
                  <UiButton
                    variant="ghost"
                    :disabled="busy"
                    title="把整库覆盖成这一份"
                    @click="restore(row)"
                  >
                    回滚到这一份
                  </UiButton>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <UiEmpty v-else seal="空" text="还没有任何快照" />
      </GlassCard>
    </template>
  </div>
</template>

<style scoped>
.snv {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.snv-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}
.snv-title {
  margin: 0;
  font-size: var(--fs-h1);
  letter-spacing: 0.02em;
}
.snv-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ink-3);
}
.snv-actions {
  display: flex;
  gap: 8px;
  flex: none;
}
.snv-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.snv-note {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-2);
}
.snv-note code {
  padding: 1px 5px;
  border-radius: 6px;
  background: var(--surface-2);
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 11.5px;
}
.snv-block {
  display: block;
}
.snv-failed {
  border-color: var(--red);
}
.snv-h2 {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 6px;
  font-size: var(--fs-h2);
}
.snv-hint {
  margin: 0 0 12px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--ink-3);
}
.snv-table-wrap {
  overflow-x: auto;
}
.snv-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.snv-table th {
  padding: 6px 10px 6px 0;
  text-align: left;
  color: var(--ink-3);
  font-weight: 500;
  white-space: nowrap;
}
.snv-table td {
  padding: 7px 10px 7px 0;
  border-top: 1px solid var(--surface-2);
  vertical-align: middle;
}
.snv-table .num {
  text-align: right;
  white-space: nowrap;
}
.snv-table .num.hit {
  color: var(--accent);
  font-weight: 600;
}
.nowrap {
  white-space: nowrap;
}
.ago {
  margin-left: 6px;
  font-size: 11px;
  color: var(--ink-3);
}
.path {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 11.5px;
  word-break: break-all;
}
.snv-table .act {
  text-align: right;
  white-space: nowrap;
}
</style>
