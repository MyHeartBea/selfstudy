<!--
  设计规格页（/design）—— 活体规范
  ---------------------------------------------------------------------------
  它不是文档，是**可交互的规格表**：每个令牌、每条材质、每条动效原语都能当场触发看效果。
  这样做的好处：改令牌时一眼能看出影响面，评审时不需要看截图猜动效。

  页面自身的排版同样遵守全站规则：非对称编辑式网格、等宽读数、2px 圆角、无默认阴影。
-->
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { focusRing, magnetic, revealAll, traceOnScroll } from '../design/motion'
import InkCard from '../ui/InkCard.vue'
import InkDot from '../ui/InkDot.vue'
import StarRow from '../ui/StarRow.vue'
import UiButton from '../ui/UiButton.vue'
import UiCheck from '../ui/UiCheck.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiField from '../ui/UiField.vue'
import UiModal from '../ui/UiModal.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'
import UiTextarea from '../ui/UiTextarea.vue'
import { toast } from '../ui/toast'

/** 组件分区用的受控状态 */
const demoText = ref('泰勒公式的余项')
const demoStar = ref(4)
const demoDot = ref(3)
const demoArea = ref('设函数 f(x) 在 x=0 处连续，则 f′(0) 等于（ ）')
const demoSubject = ref('1')
const demoCheck = ref(false)
const demoMixed = ref(false)
const modalOpen = ref(false)

const SUBJECTS = [
  { value: '1', label: '数学二' },
  { value: '2', label: '英语二' },
  { value: '3', label: '政治' },
  { value: '4', label: '408' },
]

const root = ref(null)
let stops = []

/** 令牌表：与 tokens.css 一一对应（改令牌时这里也要改，否则规范页会撒谎） */
const PALETTE = [
  { name: '星云底', token: '--sky-0', val: '#05060a', note: '页面底' },
  { name: '卡片面', token: '--sky-1', val: '#0b0d15', note: '内容面' },
  { name: '抬升面', token: '--sky-2', val: '#141621', note: '悬停面' },
  { name: '凹陷描边', token: '--sky-4', val: '#2b3040', note: '分隔与描边' },
  { name: '星光 0', token: '--ink-0', val: '#e7e6fb', note: '正文主色' },
  { name: '星光 2', token: '--ink-2', val: '#85849e', note: '辅助信息' },
  { name: '红移', token: '--redshift', val: '#ff5a3c', note: '唯一强调色' },
  { name: '矿脉青', token: '--vein', val: '#57c8d8', note: '数据与进行中' },
  { name: '琥珀', token: '--gold', val: '#e0b25a', note: '警示与过载' },
  { name: '紫', token: '--violet', val: '#8e7bf0', note: '408 科目色' },
]

/** 动效原语：每条都可点击重播 */
const PRIMITIVES = [
  {
    id: 'settle',
    name: '沉降',
    en: 'Settle',
    note: '内容入场：由远及近，模糊到位。用于章节揭示。',
  },
  {
    id: 'flare',
    name: '红移',
    en: 'Flare',
    note: '反馈落定：过冲回弹，一锤定音。用于确认与错误。',
  },
  { id: 'trace', name: '描绘', en: 'Trace', note: '数据呈现：路径从左到右写出。用于曲线与进度。' },
  { id: 'scan', name: '扫描', en: 'Scan', note: '等待上游：说明"在处理"，不编造百分比。' },
  { id: 'focus', name: '聚焦', en: 'Focus', note: '键盘焦点：同心圈收紧，任何背景下可见。' },
  { id: 'drift', name: '漂移', en: 'Drift', note: '环境运动：缓慢、无始无终。用于星云与视差。' },
]

const running = ref('')

function play(id) {
  running.value = ''
  // 强制重排，保证同一张卡可以反复重播
  requestAnimationFrame(() => {
    running.value = id
  })
}

onMounted(() => {
  stops.push(
    revealAll(root.value.querySelectorAll('.reveal'), { stagger: 60 }),
    traceOnScroll(root.value.querySelector('.trace-host')),
    focusRing(root.value),
    magnetic(root.value.querySelector('.magnet')),
  )
})

onBeforeUnmount(() => stops.forEach((fn) => typeof fn === 'function' && fn()))
</script>

<template>
  <main id="main" ref="root" class="spec">
    <header class="head">
      <h1 class="mono page-h1">活体规范</h1>
      <span class="mono">点任意原语卡可重播</span>
    </header>

    <!-- ── 色彩令牌 ── -->
    <section class="block">
      <h2 class="reveal">色彩令牌</h2>
      <p class="lead reveal">
        主定义走 OKLCH（感知均匀，暗色下不会灰掉），十六进制回退给旧浏览器。强调色只有<b>一个</b>。
      </p>
      <div class="swatches reveal">
        <div v-for="c in PALETTE" :key="c.token" class="swatch">
          <span class="chip" :style="{ background: `var(${c.token})` }" aria-hidden="true"></span>
          <span class="meta">
            <b>{{ c.name }}</b>
            <em class="mono">{{ c.token }}</em>
            <span class="hex mono">{{ c.val }}</span>
          </span>
        </div>
      </div>
    </section>

    <!-- ── 动效原语 ── -->
    <section class="block">
      <h2 class="reveal">动效原语</h2>
      <p class="lead reveal">
        全站只有这六条动作，每条都对应一个物理过程，也都有 reduced-motion
        降级（瞬时到位、信息不丢）。
      </p>
      <div class="prims reveal">
        <button
          v-for="p in PRIMITIVES"
          :key="p.id"
          class="prim"
          :class="{ run: running === p.id }"
          type="button"
          @click="play(p.id)"
        >
          <span class="pname"
            >{{ p.name }}<em class="mono">{{ p.en }}</em></span
          >
          <span class="stage" :class="`st-${p.id}`">
            <i class="dot" aria-hidden="true"></i>
            <svg v-if="p.id === 'trace'" viewBox="0 0 120 30" aria-hidden="true">
              <path
                class="p-line"
                d="M4 24 C 22 22, 34 10, 52 13 C 70 16, 82 4, 100 7 C 110 8.5, 114 6, 116 5"
              />
            </svg>
          </span>
          <span class="pnote">{{ p.note }}</span>
        </button>
      </div>
    </section>

    <!-- ── 材质 ── -->
    <section class="block">
      <h2 class="reveal">材质</h2>
      <p class="lead reveal">
        四条材质全部低透明度叠加：扫描线、半调网点、星坐标网格、显示字色差。100% 缩放下不该被察觉。
      </p>
      <div class="mats reveal">
        <div class="mat">
          <span class="mstage"><i class="mat-scanline" aria-hidden="true"></i></span>
          <b>扫描线</b><em class="mono">.mat-scanline</em>
        </div>
        <div class="mat">
          <span class="mstage"><i class="mat-halftone" aria-hidden="true"></i></span>
          <b>半调网点</b><em class="mono">.mat-halftone</em>
        </div>
        <div class="mat">
          <span class="mstage"><i class="mat-grid" aria-hidden="true"></i></span>
          <b>星坐标网格</b><em class="mono">.mat-grid</em>
        </div>
        <div class="mat">
          <span class="mstage dark"><b class="mat-chroma big">星图</b></span>
          <b>显示字色差</b><em class="mono">.mat-chroma</em>
        </div>
      </div>
    </section>

    <!-- ── 描绘原语与磁吸 ── -->
    <section class="block two">
      <div class="reveal">
        <h2>描绘 · 光变曲线</h2>
        <p class="lead">滚动进入视口时按路径真实长度写出，不是裁剪遮罩。</p>
        <div class="panel trace-host">
          <span class="mat-grid" aria-hidden="true"></span>
          <svg
            viewBox="0 0 560 140"
            preserveAspectRatio="none"
            role="img"
            aria-label="光变曲线示意"
          >
            <path
              class="trace-area"
              d="M0 108 C 60 98, 90 62, 140 68 C 190 74, 220 40, 280 46 C 340 52, 380 22, 440 30 C 500 38, 530 22, 560 18 L 560 140 L 0 140 Z"
            />
            <path
              class="trace-path"
              d="M0 108 C 60 98, 90 62, 140 68 C 190 74, 220 40, 280 46 C 340 52, 380 22, 440 30 C 500 38, 530 22, 560 18"
            />
            <circle class="trace-dot" cx="280" cy="46" r="3.2" />
            <circle class="trace-dot" cx="440" cy="30" r="3.2" />
          </svg>
        </div>
      </div>

      <div class="reveal">
        <h2>磁吸 · 焦点</h2>
        <p class="lead">按钮被指针吸过去（位移上限 22px，不做无限跟随）；Tab 键可逐一到访。</p>
        <div class="panel centre">
          <button class="magnet" type="button">磁吸按钮</button>
          <a class="focus-ring" href="#main">键盘焦点示例</a>
        </div>
      </div>
    </section>

    <!-- ── 组件：原子 ── -->
    <section class="block">
      <h2 class="reveal">组件 · 原子</h2>
      <p class="lead reveal">
        每个组件都含键盘可达、focus-visible、aria 与 reduced-motion 降级。
        <b>InkCard 整块可点靠事件绑在卡片本身</b>（不是覆盖层——覆盖层会被 z-index
        更高的子元素盖住）。
      </p>
      <div class="atoms reveal">
        <div class="atom">
          <span class="alab mono">ui-button</span>
          <div class="arow">
            <UiButton variant="solid">主操作</UiButton>
            <UiButton>次操作</UiButton>
            <UiButton variant="quiet">低干扰</UiButton>
            <UiButton variant="danger">删除</UiButton>
            <UiButton loading>进行中</UiButton>
          </div>
        </div>

        <div class="atom">
          <span class="alab mono">ui-field</span>
          <UiField v-model="demoText" label="题干" hint="支持公式与中文混排" counter="7 / 80" />
        </div>

        <div class="atom">
          <span class="alab mono">ui-field（错误态）</span>
          <UiField :model-value="''" label="答案" error="填空答案不能为空" />
        </div>

        <div class="atom">
          <span class="alab mono">ui-tag</span>
          <div class="arow">
            <UiTag tone="red-shift" dot>反复错</UiTag>
            <UiTag tone="vein">数据</UiTag>
            <UiTag tone="gold">过载</UiTag>
            <UiTag tone="violet">408</UiTag>
            <UiTag>中性</UiTag>
          </div>
        </div>
      </div>
    </section>

    <!-- ── 组件：复合 ── -->
    <section class="block">
      <h2 class="reveal">组件 · 复合</h2>
      <p class="lead reveal">
        InkCard 整块可点；InkDot 回答「记住多少」（有模糊地带，所以是五档而非百分比）； StarRow
        回答「看过几遍」（客观可数）。两者语义不同，不要互相替代。
      </p>

      <div class="compound reveal">
        <InkCard spine="var(--redshift)" flagged @select="() => {}">
          <div class="chead">
            <UiTag tone="red-shift" size="sm">数学二</UiTag>
            <UiTag tone="vein" size="sm">高等数学</UiTag>
            <span class="mono cmeta">2019 · 第 7 题</span>
          </div>
          <h3 class="ctitle">设函数 f(x) 在 x=0 处连续，求 f′(0)</h3>
          <div class="cfoot">
            <InkDot :value="demoDot" label="掌握度" />
            <StarRow :value="demoStar" :max="7" label="复习遍数" />
            <button class="cbtn mono" type="button" @click.stop>内部控件不冒泡</button>
          </div>
        </InkCard>

        <div class="compound-note">
          <p class="cexplain">
            点卡片空白处 = 打开详情；点右下角按钮不会顺带打开（<b>@click.stop</b>）。 这条是 v2
            真实事故的正面设计，已由单测钉死。
          </p>
          <div class="adjust">
            <label class="mono" for="adj-mastery">掌握度 {{ demoDot }}</label>
            <input
              id="adj-mastery"
              v-model.number="demoDot"
              type="range"
              min="0"
              max="5"
              step="1"
            />
            <label class="mono" for="adj-star">复习遍数 {{ demoStar }}</label>
            <input id="adj-star" v-model.number="demoStar" type="range" min="0" max="7" step="1" />
          </div>
        </div>
      </div>
    </section>

    <!-- ── 组件：表单与反馈层 ── -->
    <section class="block">
      <h2 class="reveal">组件 · 表单与反馈</h2>
      <p class="lead reveal">
        下拉刻意用<b>原生 select</b>（键盘导航、移动端选择器、屏幕阅读器语义浏览器已经做对了）；
        反馈层不阻塞操作，弹层带<b>焦点陷阱与焦点归还</b>。
      </p>

      <div class="atoms reveal">
        <div class="atom wide">
          <span class="alab mono">ui-textarea（自动增高 + 字数）</span>
          <UiTextarea
            v-model="demoArea"
            label="题干"
            hint="输入越长框越高，超过上限才出现滚动条"
            show-count
            :max-length="200"
          />
        </div>

        <div class="atom">
          <span class="alab mono">ui-select / ui-check</span>
          <UiSelect
            v-model="demoSubject"
            :options="SUBJECTS"
            label="科目"
            hint="原生控件 + 视觉接管"
          />
          <div class="arow">
            <UiCheck v-model="demoCheck" label="已核对题干" />
            <UiCheck v-model="demoMixed" :indeterminate="!demoMixed" label="半选（批量表头）" />
          </div>
        </div>

        <div class="atom">
          <span class="alab mono">toast（不阻塞 · aria-live）</span>
          <div class="arow">
            <UiButton size="sm" @click="toast.success('已点亮入库')">成功</UiButton>
            <UiButton size="sm" @click="toast.info('今晚还有 38 题')">信息</UiButton>
            <UiButton size="sm" variant="danger" @click="toast.error('入库失败：题干为空')">
              错误
            </UiButton>
          </div>
          <span class="alab mono">ui-modal（焦点陷阱 + 归还）</span>
          <div class="arow">
            <UiButton size="sm" @click="modalOpen = true">打开弹层</UiButton>
          </div>
        </div>

        <div class="atom">
          <span class="alab mono">ui-empty / ui-skeleton</span>
          <UiEmpty title="今晚没有待复习" hint="可以先去录入一道题，或提前看明天的星表" />
        </div>

        <div class="atom wide">
          <span class="alab mono">ui-skeleton（形状贴合真实卡片，减少跳版）</span>
          <UiEmpty variant="skeleton" thumb :rows="3" />
        </div>
      </div>
    </section>

    <footer class="foot">
      <span class="mono">SPEC · 令牌改动必须同步这一页</span>
      <span class="mono">NOCTURNAL ATLAS / v3</span>
    </footer>

    <UiModal v-model="modalOpen" title="观测详情" size="md">
      <p class="lead" style="margin-bottom: 10px">
        打开时焦点会移入弹层，Tab 在弹层内循环，Esc 或点遮罩关闭，
        关闭后焦点<b>归还到刚才那个按钮</b>。打开期间页面滚动被锁住，卸载时也会解锁。
      </p>
      <UiEmpty title="这里放详情内容" hint="阶段 3 会换成真实的错题详情" />
      <template #foot>
        <UiButton variant="quiet" @click="modalOpen = false">取消</UiButton>
        <UiButton variant="solid" @click="modalOpen = false">确认</UiButton>
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
.spec {
  position: relative;
  z-index: var(--z-content);
  max-width: var(--col);
  margin: 0 auto;
  padding: clamp(88px, 12vh, 140px) var(--pad) 80px;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
}

.block {
  padding: clamp(38px, 7vh, 88px) 0 0;
}
.block.two {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: clamp(18px, 3vw, 44px);
}
h2 {
  font-size: var(--fs-h1);
  font-weight: 500;
  letter-spacing: -0.03em;
  margin-bottom: 10px;
}
.lead {
  max-width: 58ch;
  color: var(--ink-2);
  margin-bottom: clamp(18px, 3vh, 30px);
}
.lead b {
  color: var(--ink-0);
  font-weight: 500;
}

/* 色板：一行一个令牌，chip 与元信息并排（不是大色块墙） */
.swatches {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.swatch {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--sky-1);
}
.chip {
  width: 34px;
  height: 34px;
  flex: none;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
}
.meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.meta b {
  font-size: var(--fs-sm);
  font-weight: 500;
}
.meta em {
  font-style: normal;
  color: var(--ink-3);
}
.hex {
  color: var(--ink-2);
}

/* 动效原语卡 */
.prims {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.prim {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 15px 16px 17px;
  background: var(--sky-1);
  text-align: left;
  transition: background 0.3s var(--e-settle);
}
.prim:hover {
  background: var(--sky-2);
}
.pname {
  font-size: var(--fs-sm);
  font-weight: 500;
}
.pname em {
  font-style: normal;
  margin-left: 7px;
  color: var(--ink-3);
}
.stage {
  position: relative;
  height: 62px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--sky-2);
  overflow: hidden;
  display: grid;
  place-items: center;
}
.stage .dot {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--ink-0);
}
.pnote {
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink-2);
}

/* 各原语在 .run 下的表现 */
.prim.run .st-settle .dot {
  animation: demo-settle 1s var(--e-settle);
}
@keyframes demo-settle {
  from {
    opacity: 0;
    transform: translateY(16px) scale(0.86);
    filter: blur(9px);
  }
  to {
    opacity: 1;
    transform: none;
    filter: none;
  }
}
.prim.run .st-flare .dot {
  background: var(--redshift);
  animation: flare-pulse 0.62s var(--e-flare);
}
.prim.run .st-scan .dot {
  width: 26%;
  height: 200%;
  border-radius: 0;
  background: linear-gradient(90deg, transparent, var(--redshift), transparent);
  animation: demo-scan 1.1s var(--e-settle);
}
@keyframes demo-scan {
  from {
    transform: translateX(-170%);
  }
  to {
    transform: translateX(440%);
  }
}
.prim.run .st-focus .dot {
  width: 14px;
  height: 14px;
  background: none;
  box-shadow:
    0 0 0 2px var(--ink-0),
    0 0 0 6px var(--sky-2),
    0 0 0 8px var(--redshift);
  animation: demo-focus 1s var(--e-flare);
}
@keyframes demo-focus {
  from {
    transform: scale(2.4);
    opacity: 0;
  }
  to {
    transform: none;
    opacity: 1;
  }
}
.prim.run .st-drift .dot {
  width: 12px;
  height: 12px;
  animation: demo-drift 2.4s var(--e-drift);
}
@keyframes demo-drift {
  0% {
    transform: translate3d(-34px, 8px, 0) scale(0.8);
    opacity: 0.4;
  }
  50% {
    transform: translate3d(10px, -8px, 0) scale(1.1);
    opacity: 1;
  }
  100% {
    transform: translate3d(34px, 6px, 0) scale(0.9);
    opacity: 0.7;
  }
}
.prim .dot,
.prim svg {
  display: none;
}
.prim .st-settle .dot,
.prim .st-flare .dot,
.prim .st-scan .dot,
.prim .st-focus .dot,
.prim .st-drift .dot {
  display: block;
}
.prim .st-trace svg {
  display: block;
  width: 80%;
}
.p-line {
  fill: none;
  stroke: var(--vein);
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-dasharray: var(--len, 200);
  stroke-dashoffset: var(--len, 200);
}
.prim.run .st-trace .p-line {
  --len: 200;
  animation: demo-trace 1.2s var(--e-settle) forwards;
}
@keyframes demo-trace {
  from {
    stroke-dashoffset: 200;
  }
  to {
    stroke-dashoffset: 0;
  }
}

/* 材质展示 */
.mats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.mat {
  background: var(--sky-1);
  padding: 14px 15px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.mstage {
  position: relative;
  display: block;
  height: 76px;
  margin-bottom: 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--sky-0);
  overflow: hidden;
}
.mstage.dark {
  display: grid;
  place-items: center;
  background: var(--sky-2);
}
.big {
  font-size: 26px;
  font-weight: 500;
  letter-spacing: 0.04em;
}
.mat b {
  font-size: var(--fs-sm);
  font-weight: 500;
}
.mat em {
  font-style: normal;
  color: var(--ink-3);
}

/* 面板 */
.panel {
  position: relative;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--sky-1);
  padding: 18px;
  overflow: hidden;
}
.panel svg {
  width: 100%;
  height: 140px;
  display: block;
}
.panel.centre {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
  min-height: 140px;
}
.magnet {
  padding: 11px 20px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  font-size: var(--fs-sm);
  transition:
    transform 0.35s var(--e-flare),
    border-color 0.3s var(--e-settle);
  will-change: transform;
}
.magnet:hover {
  border-color: var(--redshift);
}
.panel a {
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
  letter-spacing: 0.1em;
  color: var(--ink-2);
  border-bottom: 1px solid var(--line-strong);
  padding-bottom: 2px;
}

.foot {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: clamp(40px, 8vh, 90px);
  padding-top: 18px;
  border-top: 1px solid var(--line);
}

/* ── 组件分区 ── */
.atoms {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.atom {
  display: flex;
  flex-direction: column;
  gap: 13px;
  padding: 16px;
  background: var(--sky-1);
}
.atom.wide {
  grid-column: span 2;
}
@media (max-width: 700px) {
  .atom.wide {
    grid-column: span 1;
  }
}
.alab {
  color: var(--ink-3);
}
.arow {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  align-items: center;
}
.compound {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: clamp(16px, 2.6vw, 40px);
  align-items: start;
}
.chead {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 11px;
}
.cmeta {
  color: var(--ink-3);
}
.ctitle {
  font-size: var(--fs-h2);
  font-weight: 500;
  letter-spacing: -0.02em;
  line-height: 1.45;
  margin-bottom: 14px;
}
.cfoot {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.cbtn {
  margin-left: auto;
  padding: 5px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  color: var(--ink-2);
}
.cbtn:hover {
  border-color: var(--redshift);
  color: var(--ink-0);
}
.cexplain {
  color: var(--ink-2);
  font-size: var(--fs-sm);
  line-height: 1.8;
}
.cexplain b {
  color: var(--ink-0);
  font-weight: 500;
}
.adjust {
  margin-top: 18px;
  display: grid;
  gap: 10px;
}
.adjust label {
  color: var(--ink-2);
}
.adjust input[type='range'] {
  width: 100%;
  accent-color: var(--redshift);
}
@media (max-width: 900px) {
  .compound {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .prim.run .st-settle .dot,
  .prim.run .st-flare .dot,
  .prim.run .st-scan .dot,
  .prim.run .st-focus .dot,
  .prim.run .st-drift .dot,
  .prim.run .st-trace .p-line {
    animation: none;
  }
}
</style>
