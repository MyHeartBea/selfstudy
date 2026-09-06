<script setup>
/** /design 组件画廊：设计令牌与基件的一站式打磨场（不进导航，仅开发评审用） */
import { ref } from 'vue'

import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'
import UiModal from '../ui/UiModal.vue'
import UiTabs from '../ui/UiTabs.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiDropdown from '../ui/UiDropdown.vue'
import UiCheckbox from '../ui/UiCheckbox.vue'
import UiPagination from '../ui/UiPagination.vue'
import UiProgress from '../ui/UiProgress.vue'
import UiStars from '../ui/UiStars.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import GlassCard from '../ui/GlassCard.vue'
import MetricTile from '../ui/MetricTile.vue'
import RingProgress from '../ui/RingProgress.vue'
import AreaChart from '../ui/AreaChart.vue'
import BarRow from '../ui/BarRow.vue'
import Heatmap from '../ui/Heatmap.vue'
import Skeleton from '../ui/Skeleton.vue'
import StageBadge from '../ui/StageBadge.vue'
import Icon from '../ui/Icon.vue'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'

const modalOpen = ref(false)
const tab = ref('week')
 const subject = ref('math')
const checked = ref(true)
const stars = ref(3)
const page = ref(2)
const pageSize = ref(10)

const palette = [
  ['--bg', '纸面'], ['--surface', '卡面'], ['--surface-2', '卡面次级'],
  ['--ink', '浓墨'], ['--ink-2', '淡墨'], ['--ink-3', '灰墨'],
  ['--accent', '朱砂'], ['--accent-soft', '朱砂晕'], ['--teal', '黛青'],
  ['--gold', '洒金'], ['--green', '石绿'], ['--red', '赭红'],
]
const fontSpec = [
  ['--fs-display', '42px', '900', '今日待复习'],
  ['--fs-h1', '32px', '900', '学习统计'],
  ['--fs-h2', '20px', '700', '英语整篇精读'],
  ['--fs-h3', '16.5px', '700', '复习趋势'],
  ['--fs-body', '15px', '400', '设 A 为 3 阶实对称矩阵，秩 r(A)=2，且 $A^2+2A=O$。'],
]

const trendLabels = ['8/31', '9/1', '9/2', '9/3', '9/4', '9/5', '9/6']
const trendSeries = [
  { name: '完成次数', color: 'var(--accent)', values: [6, 9, 4, 11, 7, 10, 8] },
  { name: '答对次数', color: 'var(--teal)', values: [5, 8, 3, 9, 6, 8, 7] },
]

// 热力图演示数据：近 126 天随机
const heatData = (() => {
  let s = 42
  const rnd = () => (s = (s * 9301 + 49297) % 233280) / 233280
  const out = []
  const d = new Date('2026-09-06T00:00:00')
  d.setDate(d.getDate() - 125)
  for (let i = 0; i < 126; i++) {
    const r = rnd()
    const v = r < 0.18 ? 0 : r < 0.42 ? 1 : r < 0.68 ? 3 : r < 0.88 ? 6 : 12
    out.push({ date: d.toISOString().slice(0, 10), count: v })
    d.setDate(d.getDate() + 1)
  }
  return out
})()

async function askConfirm() {
  const ok = await confirmDialog({ title: '删除确认', message: '将删除这条错题及其全部图片，无法恢复。', danger: true, confirmText: '删除' })
  if (ok) toast.success('已删除（演示）')
}
</script>

<template>
  <div class="design-page">
    <header class="page-head">
      <div class="kicker">Design System</div>
      <h1>墨韵 2.0 · 设计画廊</h1>
      <p class="sub">宣纸 · 松烟墨 · 朱砂印 · 洒金 —— 令牌与基件的一站式打磨场（双主题切换见右上角）</p>
    </header>

    <!-- 色板 -->
    <section class="sec">
      <h2>色板</h2>
      <div class="swatches">
        <div v-for="[v, name] in palette" :key="v" class="swatch">
          <div class="chip" :style="{ background: `var(${v})` }"></div>
          <b>{{ name }}</b><code>{{ v }}</code>
        </div>
      </div>
    </section>

    <!-- 字阶 -->
    <section class="sec">
      <h2>字阶 · 显示字体为本地子集思源宋体</h2>
      <div class="type-spec">
        <div v-for="[token, size, weight, text] in fontSpec" :key="token" class="type-row">
          <code>{{ token }} {{ size }}/{{ weight }}</code>
          <p :style="{ fontSize: `var(${token})`, fontWeight: weight }" class="spec-display">{{ text }}</p>
        </div>
        <p class="body-spec">正文 15px/1.7：间隔重复 1/3/7/15/30 天；选择题填 A/B/C/D，数字答案带容差判分。数字使用等宽排版 <span class="num">0123456789</span>。</p>
      </div>
    </section>

    <!-- 玻璃卡与骑缝 -->
    <section class="sec">
      <h2>玻璃卡 GlassCard · 渐变描边 + 流光 + 骑缝徽章</h2>
      <div class="gcard-row">
        <GlassCard class="demo-card">
          <h3>悬停看流光</h3>
          <p class="cap">渐变描边 + 玻璃拟态，背后透出氛围层光晕</p>
        </GlassCard>
        <GlassCard class="demo-card">
          <template #badge><StageBadge text="骑缝徽章" /></template>
          <h3>骑缝防裁切</h3>
          <p class="cap">徽章挂在 #badge 插槽（外层 overflow:visible），不会被卡片圆角裁掉</p>
        </GlassCard>
      </div>
    </section>

    <!-- 按钮 -->
    <section class="sec">
      <h2>按钮 UiButton</h2>
      <div class="row">
        <UiButton variant="primary" @click="toast.success('印章主按钮 · 涟漪')">主按钮</UiButton>
        <UiButton variant="outline">描边</UiButton>
        <UiButton variant="ghost">幽灵</UiButton>
        <UiButton variant="subtle">次要</UiButton>
        <UiButton variant="danger" @click="askConfirm">危险 · 确认弹窗</UiButton>
        <UiButton variant="success">成功</UiButton>
        <UiButton variant="primary" loading>加载中</UiButton>
        <UiButton variant="outline" disabled>禁用</UiButton>
        <UiButton variant="primary" size="sm">小号</UiButton>
        <UiButton variant="primary" size="lg">大号</UiButton>
      </div>
    </section>

    <!-- 表单控件 -->
    <section class="sec">
      <h2>表单控件</h2>
      <div class="row">
        <UiTabs v-model="tab" :tabs="[{ name: 'week', label: '周' }, { name: 'month', label: '月' }, { name: 'all', label: '全部' }]" />
        <UiSelect v-model="subject" :options="[{ label: '高等数学', value: 'math' }, { label: '英语阅读', value: 'en' }, { label: '计算机网络', value: 'net' }]" />
        <UiDropdown label="批量操作" :items="[{ label: '标记已掌握', command: 'mark', icon: 'check' }, { label: '导出 JSON', command: 'export', icon: 'download' }]" @command="(c) => toast.info('命令：' + c)" />
        <UiCheckbox v-model="checked" label="仅看未掌握" />
        <UiStars v-model="stars" />
        <span class="ro-stars"><UiStars :model-value="4.5" readonly /> 只读半星</span>
      </div>
    </section>

    <!-- 反馈 -->
    <section class="sec">
      <h2>反馈 · Toast / 弹窗 / 骨架 / 空态</h2>
      <div class="row">
        <UiButton variant="outline" size="sm" @click="toast.success('保存成功')">成功 Toast</UiButton>
        <UiButton variant="outline" size="sm" @click="toast.error('网络开小差了')">错误 Toast</UiButton>
        <UiButton variant="outline" size="sm" @click="modalOpen = true">玻璃弹窗</UiButton>
      </div>
      <div class="skeleton-row">
        <Skeleton variant="text" :count="2" />
        <Skeleton variant="rect" :width="220" :height="88" :radius="14" />
        <Skeleton variant="circle" :height="48" />
      </div>
      <div class="empty-box">
        <UiEmpty text="还没有错题，去智能录入晒一道吧">
          <UiButton variant="primary" size="sm">去录入</UiButton>
        </UiEmpty>
      </div>
    </section>

    <!-- 数据展示 -->
    <section class="sec">
      <h2>数据展示 · 瓷砖 / 进度环 / 面积图 / 条形 / 热力图</h2>
      <div class="data-grid">
        <GlassCard class="span2">
          <div class="chart-head">
            <div><h3>复习趋势</h3><p class="cap">近 7 天完成与正确（SVG 描边生长）</p></div>
          </div>
          <AreaChart :labels="trendLabels" :series="trendSeries" :height="200" />
        </GlassCard>
        <GlassCard>
          <h3>今日进度</h3>
          <div class="ring-center-demo">
            <RingProgress :percentage="62">
              <div><b class="num">5/8</b><span>今日已完成</span></div>
            </RingProgress>
          </div>
        </GlassCard>
        <GlassCard class="span2">
          <h3>瓷砖指标 MetricTile</h3>
          <div class="tiles">
            <MetricTile icon="layers" :value="83" label="累计错题 · 本周 +6" tone="accent" />
            <MetricTile icon="check" value="75.2" unit="%" label="总正确率 · 105 次复习" tone="green" />
            <MetricTile icon="flame" :value="5" unit="天" label="连续复习 · 最长 11 天" tone="gold">
              <template #spark>
                <svg width="70" height="30" viewBox="0 0 70 30"><polyline points="2,24 13,18 24,21 35,10 46,14 57,7 68,4" fill="none" stroke="var(--gold)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
              </template>
            </MetricTile>
            <MetricTile icon="trending" :value="12" label="今日待复习" tone="teal" />
          </div>
        </GlassCard>
        <GlassCard>
          <h3>掌握度 BarRow</h3>
          <div class="bars">
            <BarRow label="0 级" :percentage="52" :value="24" />
            <BarRow label="1 级" :percentage="100" :value="46" />
            <BarRow label="2 级" :percentage="28" :value="13" color="var(--teal)" />
          </div>
          <div class="progress-demo">
            <UiProgress :percentage="66" />
            <span class="cap">UiProgress 66%</span>
          </div>
        </GlassCard>
        <GlassCard class="span2">
          <h3>复习热力图 Heatmap</h3>
          <p class="cap">近 126 天 · 墨色深浅 = 复习量 · 级联入场</p>
          <Heatmap :data="heatData" :max-weeks="18" />
        </GlassCard>
        <GlassCard>
          <h3>分页与标签</h3>
          <div class="stack">
            <div class="row wrap">
              <UiTag>标签</UiTag>
              <UiTag color="var(--accent)" soft>朱砂</UiTag>
              <UiTag color="var(--teal)" soft>黛青</UiTag>
              <UiTag color="var(--gold)" soft>洒金</UiTag>
              <UiTag size="sm">小号</UiTag>
            </div>
            <UiPagination v-model:page="page" v-model:page-size="pageSize" :total="83" @change="() => {}" />
            <span class="cap">当前第 {{ page }} 页 · 每页 {{ pageSize }} 条</span>
          </div>
        </GlassCard>
      </div>
    </section>

    <!-- 动效 -->
    <section class="sec">
      <h2>动效曲线</h2>
      <div class="motion-row">
        <div class="m-demo"><div class="m-ball spring"></div><code>--spring</code></div>
        <div class="m-demo"><div class="m-ball ease"></div><code>--ease</code></div>
        <span class="cap">图标速览：<Icon name="sparkles" :size="15" /> <Icon name="flame" :size="15" /> <Icon name="trending" :size="15" /> <Icon name="zap" :size="15" /></span>
      </div>
    </section>

    <UiModal v-model="modalOpen" title="弹窗 · 玻璃质感" size="sm">
      <p style="line-height:1.8">宽弹窗、玻璃拟态、弹性入场、Esc 关闭。</p>
      <template #footer><UiButton variant="ghost" size="sm" @click="modalOpen = false">关闭</UiButton></template>
    </UiModal>
  </div>
</template>

<style scoped>
.design-page { max-width: 960px; margin: 0 auto; display: flex; flex-direction: column; gap: 26px; }
.page-head .kicker { font-size: 11px; font-weight: 700; letter-spacing: 0.24em; color: var(--accent); text-transform: uppercase; margin-bottom: 8px; display: flex; align-items: center; gap: 10px; }
.page-head .kicker::before { content: ''; width: 22px; height: 2px; background: var(--accent); border-radius: 2px; opacity: 0.6; }
h1 { font-family: var(--font-display); font-weight: 900; font-size: var(--fs-h1); }
.sub { color: var(--ink-2); margin-top: 6px; font-size: 14px; }
.sec h2 { font-family: var(--font-display); font-size: var(--fs-h3); margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--line); }
.sec h3 { font-family: var(--font-display); font-size: 15px; font-weight: 700; margin-bottom: 4px; }
.cap { font-size: 12.5px; color: var(--ink-3); }

.swatches { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; }
.swatch { background: var(--surface); border-radius: var(--r-md); padding: 10px; box-shadow: var(--shadow-1); }
.swatch .chip { height: 44px; border-radius: 9px; margin-bottom: 8px; box-shadow: inset 0 0 0 1px var(--line); }
.swatch b { font-size: 12.5px; display: block; }
.swatch code { font-size: 11px; color: var(--ink-3); }

.type-spec { display: flex; flex-direction: column; gap: 14px; }
.type-row code { font-size: 11.5px; color: var(--ink-3); }
.spec-display { font-family: var(--font-display); line-height: 1.4; margin-top: 2px; }
.body-spec { color: var(--ink-2); line-height: 1.8; }
.num { font-variant-numeric: tabular-nums; }

.gcard-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.demo-card h3 { font-family: var(--font-display); font-size: 16px; margin-bottom: 4px; }

.row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.row.wrap { flex-wrap: wrap; }
.ro-stars { display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--ink-3); }

.skeleton-row { display: flex; align-items: center; gap: 32px; margin-top: 18px; flex-wrap: wrap; }
.empty-box { margin-top: 12px; border: 1px dashed var(--line-strong); border-radius: var(--r-lg); }

.data-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.span2 { grid-column: span 2; }
.chart-head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px; }
.ring-center-demo { display: grid; place-items: center; padding: 8px 0; }
.ring-center-demo b { font-family: var(--font-display); font-size: 26px; font-weight: 900; display: block; line-height: 1.1; }
.ring-center-demo span { font-size: 11.5px; color: var(--ink-3); }
.tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 24px; margin-top: 10px; }
.bars { display: flex; flex-direction: column; gap: 13px; margin-top: 8px; }
.progress-demo { margin-top: 16px; display: flex; flex-direction: column; gap: 6px; }
.stack { display: flex; flex-direction: column; gap: 12px; }

.motion-row { display: flex; align-items: center; gap: 26px; flex-wrap: wrap; }
.m-demo { display: flex; align-items: center; gap: 10px; }
.m-ball { width: 26px; height: 26px; border-radius: 9px; background: var(--accent-grad); cursor: pointer; transition: transform 0.55s var(--spring); }
.m-ball.ease { transition-timing-function: var(--ease); background: var(--teal); }
.m-ball:hover { transform: translateX(90px) rotate(140deg); }
.m-demo code { font-size: 11.5px; color: var(--ink-3); }

@media (max-width: 860px) {
  .gcard-row, .data-grid { grid-template-columns: 1fr; }
  .span2 { grid-column: span 1; }
}
</style>
