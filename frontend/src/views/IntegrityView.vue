<script setup>
/**
 * 数据体检（只读）。
 *
 * 存在的意义：图片文件与库里的引用会悄悄对不上（删错题时文件没删干净，
 * 或者反过来记录指向一张已经不存在的图）。这两类问题平时完全看不见。
 *
 * **这一页不删任何东西**，也没有删除按钮：清理仍然要在服务器上显式跑
 * `python scripts/clean_orphan_images.py --apply`（默认只报告）。
 * 判定的口径与那个脚本共用后端同一个 `integrity_service`，不会出现
 * "页面说干净、脚本说要删 102 张"。
 */
import { onMounted, ref } from 'vue'
import request from '../api/request'
import { formatBytes, KIND_LABEL, locatorLabel, summaryTiles } from '../utils/integrity.js'
import GlassCard from '../ui/GlassCard.vue'
import Icon from '../ui/Icon.vue'
import MetricTile from '../ui/MetricTile.vue'
import Skeleton from '../ui/Skeleton.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiLoadError from '../ui/UiLoadError.vue'

const report = ref(null)
const loading = ref(false)
const loadError = ref(false)

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const res = await request.get('/system/integrity', { silent: true })
    report.value = res.data.data
  } catch (err) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)

const tiles = () => summaryTiles(report.value)
const kb = formatBytes
</script>

<template>
  <div class="ity">
    <header class="ity-head">
      <div>
        <h1 class="ity-title serif">数据体检</h1>
        <p class="ity-sub">
          检查图片文件与库里的引用对不对得上。<b>本页只读，不会删除任何文件。</b>
        </p>
      </div>
      <UiButton variant="outline" :disabled="loading" @click="load">
        <Icon name="refresh" :size="14" />
        {{ loading ? '体检中…' : '重新体检' }}
      </UiButton>
    </header>

    <UiLoadError
      v-if="loadError"
      text="体检数据加载失败"
      hint="服务未响应或数据库被占用"
      @retry="load"
    />

    <template v-else-if="loading && !report">
      <Skeleton variant="rect" :height="88" :count="4" />
      <Skeleton variant="rect" :height="220" />
    </template>

    <template v-else-if="report">
      <!-- 数据健康(冲刺期数字仪表):积压/归因覆盖/考试日外排期。随体检同响应返回 -->
      <GlassCard v-if="report.data_health" class="ity-block ity-health">
        <h2 class="ity-h2">
          数据健康
          <span class="count-tip" v-if="report.data_health.exam_valid"
            >考试日 {{ report.data_health.exam_date }}</span
          >
        </h2>
        <div class="ity-health-grid">
          <div class="ity-health-col">
            <h3>生词</h3>
            <p>
              共 <b class="num">{{ report.data_health.vocab.total }}</b> · 到期
              <b class="num warn">{{ report.data_health.vocab.due }}</b> · 已掌握
              <b class="num ok">{{ report.data_health.vocab.mastered }}</b>
            </p>
            <p class="ity-health-warn" v-if="report.data_health.vocab.scheduled_after_exam">
              <b class="num">{{ report.data_health.vocab.scheduled_after_exam }}</b> 个词的下一次
              复习排在考试日之后——考前总复习时需要强制回流
            </p>
          </div>
          <div class="ity-health-col">
            <h3>错题</h3>
            <p>
              共 <b class="num">{{ report.data_health.mistakes.total }}</b> · 到期
              <b class="num warn">{{ report.data_health.mistakes.due }}</b> · 已归因
              <b class="num ok">{{ report.data_health.mistakes.attributed }}</b>
            </p>
            <p
              class="ity-health-warn"
              v-if="report.data_health.mistakes.total > report.data_health.mistakes.attributed"
            >
              还有
              <b class="num">{{
                report.data_health.mistakes.total - report.data_health.mistakes.attributed
              }}</b>
              题没标过错因——复习时顺手标,杠杆榜和周报才有数据
            </p>
          </div>
          <div class="ity-health-col">
            <h3>知识点</h3>
            <p>
              共 <b class="num">{{ report.data_health.knowledge.total }}</b> · 到期
              <b class="num warn">{{ report.data_health.knowledge.due }}</b>
            </p>
            <p class="ity-health-warn" v-if="report.data_health.knowledge.scheduled_after_exam">
              <b class="num">{{ report.data_health.knowledge.scheduled_after_exam }}</b> 条排在
              考试日之后——考前总复习时需要强制回流
            </p>
          </div>
        </div>
      </GlassCard>

      <section class="ity-tiles">
        <MetricTile
          v-for="t in tiles()"
          :key="t.key"
          :label="t.label"
          :value="t.value"
          :unit="t.unit"
          :tone="t.tone"
          :icon="t.icon"
        />
      </section>

      <p class="ity-note">
        扫描目录里共 {{ report.files }} 个图片文件，其中
        <b>{{ report.referenced }}</b> 张正被错题或真题引用。
        <template v-if="report.protected_recent">
          另有 {{ report.protected_recent }} 个文件在 {{ report.keep_days }}
          天保护期内（后台拆题时图先落盘、记录后写库），本次不计入。
        </template>
        <template v-if="report.unparseable_refs">
          有 {{ report.unparseable_refs }} 条记录的图片字段解析不了，已保守跳过（不当成引用）。
        </template>
      </p>

      <GlassCard class="ity-block">
        <h2 class="ity-h2">
          没人引用的文件
          <span class="count-tip"
            >{{ report.orphan_total }} 个 / {{ kb(report.orphan_bytes) }}</span
          >
        </h2>
        <p class="ity-hint">
          这些图片没有任何一条记录在用它（多为过去删掉的错题留下的截图）。
          它们在列表页和详情页都不会出现，但<em>知道文件名的人仍可以直接访问</em>。
          要清理请在服务器上跑
          <code>python scripts/clean_orphan_images.py</code>（先报告，加
          <code>--apply</code> 才删；自动备份只备份数据库，不备份图片，删了找不回来）。
        </p>
        <div v-if="report.orphans.length" class="ity-table-wrap">
          <table class="ity-table">
            <thead>
              <tr>
                <th>文件</th>
                <th>类型</th>
                <th class="num">大小</th>
                <th>生成日期</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in report.orphans" :key="row.rel">
                <td class="path">{{ row.rel }}</td>
                <td>{{ KIND_LABEL[row.kind] || row.kind }}</td>
                <td class="num">{{ kb(row.size) }}</td>
                <td class="num">{{ row.mtime }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="report.orphan_truncated" class="ity-hint">
            只列出最大的前 {{ report.orphans.length }} 个，其余同类的合计已算进上面的总数。
          </p>
        </div>
        <UiEmpty v-else seal="净" text="没有多余的图片文件" />
      </GlassCard>

      <GlassCard class="ity-block">
        <h2 class="ity-h2">
          记录指向的图不见了
          <span class="count-tip">{{ report.missing_total }} 条</span>
        </h2>
        <p class="ity-hint">
          这一类是"点开详情看到的是破图"：记录里写着有图，磁盘上却没有那个文件。
          通常是磁盘上的文件被手工删过或换过机器。
        </p>
        <ul v-if="report.missing.length" class="ity-list">
          <li v-for="row in report.missing" :key="row.name">
            <span class="path">{{ row.name }}</span>
            <span class="who">{{ locatorLabel(row.refs) }}</span>
          </li>
        </ul>
        <UiEmpty v-else seal="全" text="所有记录的图片都还在" />
      </GlassCard>
    </template>
  </div>
</template>

<style scoped>
.ity {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.ity-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}
.ity-title {
  margin: 0;
  font-size: var(--fs-h1);
  letter-spacing: 0.02em;
}
.ity-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ink-3);
}
.ity-health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}
.ity-health-col h3 {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: var(--ink-3);
}
.ity-health-col p {
  margin: 0 0 6px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--ink-2);
}
.ity-health-col .num.warn {
  color: var(--gold);
}
.ity-health-col .num.ok {
  color: var(--green);
}
.ity-health-warn {
  color: var(--ink-3);
}
.ity-health-warn .num {
  color: var(--red);
}
.ity-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.ity-note {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-2);
}
.ity-block {
  display: block;
}
.ity-h2 {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 6px;
  font-size: var(--fs-h2);
}
.ity-hint {
  margin: 0 0 12px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--ink-3);
}
.ity-hint code {
  padding: 1px 5px;
  border-radius: 6px;
  background: var(--surface-2);
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 11.5px;
}
.ity-table-wrap {
  overflow-x: auto;
}
.ity-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.ity-table th {
  padding: 6px 10px 6px 0;
  text-align: left;
  color: var(--ink-3);
  font-weight: 500;
  white-space: nowrap;
}
.ity-table td {
  padding: 7px 10px 7px 0;
  border-top: 1px solid var(--surface-2);
  vertical-align: top;
}
.ity-table .num {
  text-align: right;
  white-space: nowrap;
}
.path {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 11.5px;
  word-break: break-all;
}
.ity-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ity-list li {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: var(--r-sm);
  background: var(--surface-2);
}
.who {
  font-size: 12px;
  color: var(--ink-3);
  white-space: nowrap;
}
</style>
