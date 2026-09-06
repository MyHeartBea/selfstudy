<script setup>
/** /design 组件画廊：设计令牌与基件的一站式打磨场（不进导航，仅开发评审用） */
import { ref } from 'vue'

import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'
import UiModal from '../ui/UiModal.vue'
import Icon from '../ui/Icon.vue'
import { toast } from '../ui/toast'

const modalOpen = ref(false)

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

    <!-- 海拔与卡片 -->
    <section class="sec">
      <h2>海拔（替代 1px 边框）</h2>
      <div class="elev-row">
        <div class="e-card" style="box-shadow: var(--shadow-1)">e1 · 静置</div>
        <div class="e-card" style="box-shadow: var(--shadow-2)">e2 · 悬浮</div>
        <div class="e-card" style="box-shadow: var(--shadow-3)">e3 · 弹层</div>
        <div class="e-card glass-card">
          <b>渐变描边 + 玻璃</b>
          <span>背后是氛围层，透出光晕</span>
        </div>
      </div>
    </section>

    <!-- 动效 -->
    <section class="sec">
      <h2>动效曲线</h2>
      <div class="motion-row">
        <div class="m-demo">
          <div class="m-ball spring"></div><code>--spring</code>
        </div>
        <div class="m-demo">
          <div class="m-ball ease"></div><code>--ease</code>
        </div>
        <UiButton variant="primary" @click="toast.success('涟漪 + 印章主按钮')">点我试动效</UiButton>
        <UiButton variant="outline" @click="modalOpen = true">打开弹窗</UiButton>
      </div>
    </section>

    <!-- 组件速览 -->
    <section class="sec">
      <h2>组件速览（Phase 2 逐个重做）</h2>
      <div class="comp-row">
        <UiTag>标签</UiTag>
        <UiTag variant="accent">朱砂标签</UiTag>
        <span class="chip-demo">芯片 28px</span>
        <span class="stars-demo">★★★☆☆</span>
        <span class="badge-demo">骑缝徽章</span>
      </div>
    </section>

    <UiModal v-model="modalOpen" title="弹窗 · 毛玻璃" size="sm">
      <p style="line-height:1.8">宽弹窗、玻璃质感、弹性入场。</p>
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

.elev-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.e-card { background: var(--surface); border-radius: var(--r-lg); padding: 22px 18px; font-size: 13.5px; display: flex; flex-direction: column; gap: 4px; transition: transform 0.3s var(--ease); }
.e-card:hover { transform: translateY(-3px); }
.glass-card {
  background: linear-gradient(var(--surface-glass), var(--surface-glass)) padding-box,
    linear-gradient(135deg, color-mix(in srgb, var(--accent) 30%, transparent), transparent 40%, color-mix(in srgb, var(--gold) 24%, transparent)) border-box;
  border: 1px solid transparent;
  backdrop-filter: blur(10px);
}

.motion-row { display: flex; align-items: center; gap: 26px; flex-wrap: wrap; }
.m-demo { display: flex; align-items: center; gap: 10px; }
.m-ball { width: 26px; height: 26px; border-radius: 9px; background: var(--accent-grad); cursor: pointer; transition: transform 0.55s var(--spring); }
.m-ball.ease { transition-timing-function: var(--ease); background: var(--teal); }
.m-ball:hover { transform: translateX(90px) rotate(140deg); }
.m-demo code { font-size: 11.5px; color: var(--ink-3); }

.comp-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.chip-demo { font-size: 12px; font-weight: 600; color: var(--ink-2); background: var(--surface-2); padding: 4px 12px; border-radius: 999px; }
.stars-demo { color: var(--gold); letter-spacing: 2px; font-size: 13px; }
.badge-demo {
  padding: 5px 14px; border-radius: 999px; color: #fff; font-size: 12px; font-weight: 700;
  background: var(--accent-grad); box-shadow: 0 4px 12px rgba(168, 51, 32, 0.35);
}

@media (max-width: 860px) {
  .elev-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
