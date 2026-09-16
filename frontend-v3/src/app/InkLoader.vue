/* * 启动页 · 研墨开场（Ink Opening） *
--------------------------------------------------------------------------- * 三段式，共约
2.6s。它不是"进度条动画"，而是一次有始有终的仪式： * * 第一段 静默（0-700ms） 纯黑 +
一颗悬停的星点，什么都不给，先制造注意力。 * 第二段 落墨（700-2000ms）
星点坠下并在纸上洇开（多尺度模糊 + 遮罩扩散）， * 同时浮出等宽读数。读数是真实进度，不是假动画。 *
第三段 揭幕（2000-2600ms） 墨色铺满，沿斜向 clip-path 掀起，露出主界面。 * * 三条硬要求： * 1.
可跳过：任意键 / 点击 / 触摸立即完成 —— 这是每天要开很多次的工具。 * 2.
不阻塞：正常结束或安全网（4.5s）都会解锁滚动；出错也不会把人锁在加载页。 * 3.
reduced-motion：直接不播，立刻进入主界面。 * * 真实进度来源（不是编的）： * - document.fonts.ready *
- 首帧后 requestAnimationFrame 至少两帧（保证 WebGL 首帧已绘制） * - 外部传入的 ready 信号（阶段 3
起接入首屏数据请求） */
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  /** 外部就绪信号：数据/资源准备好时置 true */
  ready: { type: Boolean, default: true },
  /** 最短展示时长（ms）：避免一闪而过反而显得廉价 */
  minDuration: { type: Number, default: 2100 },
})

const emit = defineEmits(['done'])

const reduce =
  typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

const progress = ref(0)
const phase = ref(reduce ? 'opening' : 'rest')
const finished = ref(false)

let raf = 0
let startedAt = 0
let safetyTimer = 0
const elapsed = () => performance.now() - startedAt

/** 真实进度：字体 + 两帧绘制 + ready 信号，三者齐备才算 100 */
async function measure() {
  const checks = []
  if (document.fonts && document.fonts.ready) checks.push(document.fonts.ready)

  // 两帧：确保 WebGL 星点场已经画过第一帧
  checks.push(
    new Promise((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(resolve))
    }),
  )

  // 外部 ready（阶段 3 起由首屏数据驱动；默认 true 时立即通过）
  checks.push(
    new Promise((resolve) => {
      if (props.ready) {
        resolve()
        return
      }
      const stop = setInterval(() => {
        if (props.ready) {
          clearInterval(stop)
          resolve()
        }
      }, 60)
    }),
  )

  await Promise.all(checks)
}

function finish(reason) {
  if (finished.value) return
  finished.value = true
  progress.value = 100
  phase.value = 'opening'
  if (reason === 'manual') document.documentElement.dataset.loaderSkipped = '1'
  // 揭幕动画时长需与 CSS 里 .ink-loader.opening 的 transition 一致
  const wait = reduce ? 0 : 620
  setTimeout(() => {
    document.body.classList.add('ready')
    document.body.style.overflow = ''
    emit('done')
  }, wait)
}

function skip() {
  if (!finished.value) finish('manual')
}

function onKey() {
  skip()
}

onMounted(() => {
  if (reduce) {
    progress.value = 100
    phase.value = 'opening'
    document.body.classList.add('ready')
    emit('done')
    return
  }

  document.body.style.overflow = 'hidden'
  startedAt = performance.now()
  // 第一段：静默 700ms，随后进入落墨
  setTimeout(() => {
    if (!finished.value) phase.value = 'inking'
  }, 700)

  window.addEventListener('keydown', onKey)
  window.addEventListener('pointerdown', onKey)
  // 安全网：任何异常都不能把人锁在加载页
  safetyTimer = setTimeout(() => finish('safety'), 4500)

  measure().then(() => {
    // 进度只升不降，且不早于 minDuration 结束
    const tick = () => {
      const t = elapsed()
      const soft = Math.min(18, (t / 700) * 18)
      const real = 18 + 82 * Math.min(1, (t - 700) / Math.max(1, props.minDuration - 700))
      const target = Math.min(100, Math.max(soft, props.ready ? real : soft))
      progress.value = Math.max(progress.value, target)
      if (progress.value < 100 && t < props.minDuration - 40) {
        raf = requestAnimationFrame(tick)
      } else {
        finish('complete')
      }
    }
    raf = requestAnimationFrame(tick)
  })
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  clearTimeout(safetyTimer)
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('pointerdown', onKey)
  document.body.style.overflow = ''
})

const readout = computed(() => String(Math.round(progress.value)).padStart(3, '0'))

/* ── 目镜几何与读数（第二段"校准"的视觉核心） ───────────────────────────
   旧版只有一颗点 + 一个数字，画面信息密度撑不起"装置"；这一版加入
   望远镜十字丝 + 双向旋转刻度环 + 24 条角刻度，并把真实进度写成环形弧。 */
const RING_R = 92
const RING_C = 2 * Math.PI * RING_R
const ringDash = computed(() => {
  const on = (progress.value / 100) * RING_C
  return `${on.toFixed(1)} ${(RING_C - on).toFixed(1)}`
})
/** 揭幕：以中心为原点的软边圆形遮罩半径（替代旧版硬边斜切） */
const revealR = computed(() => `${8 + progress.value * 1.5}vmax`)
const phaseLabel = computed(() => {
  if (phase.value === 'opening') return '就绪'
  if (phase.value === 'calibrating') return progress.value > 66 ? '装载星表' : '对准赤经'
  return '观测站上线'
})
const TICKS = Array.from({ length: 24 }, (_, i) => i * 15)
</script>

<template>
  <div
    class="ink-loader"
    :class="phase"
    role="progressbar"
    :aria-valuenow="Math.round(progress)"
    aria-valuemin="0"
    aria-valuemax="100"
    aria-label="正在校准观测站"
    :style="{ '--reveal': revealR, '--p': progress / 100 }"
  >
    <!-- 黑场背景：以中心为原点的软边圆形透明区，随进度向外扩散，露出下面的星点场。
         刻意**不用**独立的不透明遮罩层压在目镜之上 —— 那样会把刻度环整个盖住（已踩过）。 -->
    <span class="veil" aria-hidden="true"></span>

    <!-- 目镜：十字丝 + 双向旋转刻度环 + 角刻度 -->
    <div class="optic" aria-hidden="true">
      <svg class="reticle" viewBox="0 0 240 240" width="240" height="240">
        <g class="ticks">
          <line
            v-for="(a, i) in TICKS"
            :key="a"
            :x1="120"
            :y1="i % 2 ? 6 : 2"
            :x2="120"
            :y2="i % 2 ? 14 : 20"
            :transform="`rotate(${a} 120 120)`"
          />
        </g>
        <g class="ring-in">
          <circle cx="120" cy="120" r="62" />
          <line x1="120" y1="52" x2="120" y2="62" />
        </g>
        <g class="ring-out">
          <circle cx="120" cy="120" r="92" class="track" />
          <circle cx="120" cy="120" r="92" class="prog" :stroke-dasharray="ringDash" />
          <line x1="120" y1="24" x2="120" y2="36" />
        </g>
        <g class="cross">
          <line x1="120" y1="86" x2="120" y2="104" />
          <line x1="120" y1="136" x2="120" y2="154" />
          <line x1="86" y1="120" x2="104" y2="120" />
          <line x1="136" y1="120" x2="154" y2="120" />
        </g>
      </svg>
      <span class="seed"></span>
      <span class="halo"></span>
    </div>

    <!-- HUD 四角读数 -->
    <div class="hud">
      <span class="corner tl mono">研错本 · 夜航星图</span>
      <span class="corner tr mono">NOCTURNAL ATLAS</span>
      <span class="corner bl mono"><i class="live"></i>{{ phaseLabel }}</span>
      <span class="corner br mono">任意键跳过</span>
      <span class="digits num">{{ readout }}</span>
    </div>
  </div>
</template>

<style scoped>
/* 启动页样式（重做版）—— 只保留仍然有效的部分。
   被删掉的旧写法（保留说明以防回退）：
     · `.veil` 作为独立整屏不透明层 —— 它排在目镜之后，会把刻度环整个盖住。
       正确做法：遮罩即启动页自身的背景（见下 `.ink-loader::before`），目镜自然浮在其上。
     · 旧版硬边斜切 `clip-path` 揭幕 —— 观感像"切一刀"，改为软边圆形扩散。 */

/* ── 黑场背景：软边圆形透明区，随 --reveal 扩散 ────────────────────── */
.ink-loader::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--sky-0);
  -webkit-mask-image: radial-gradient(
    circle var(--reveal) at 50% 50%,
    transparent 0 62%,
    #000 100%
  );
  mask-image: radial-gradient(circle var(--reveal) at 50% 50%, transparent 0 62%, #000 100%);
  pointer-events: none;
  transition:
    -webkit-mask-image 0.14s linear,
    mask-image 0.14s linear;
}
/* 静默段还没有扩散，整屏保持黑场 */
.ink-loader.rest::before {
  -webkit-mask-image: none;
  mask-image: none;
}

/* ── 目镜：十字丝 + 双向旋转刻度环 + 角刻度 ───────────────────────── */
.optic {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 240px;
  height: 240px;
  margin: -120px 0 0 -120px;
  display: grid;
  place-items: center;
  transition:
    opacity 0.5s var(--e-settle),
    transform 0.7s var(--e-settle);
  z-index: 2;
}
.ink-loader.opening .optic {
  opacity: 0;
  transform: scale(1.35);
}
/* 揭幕期间立刻收起所有前景信息（HUD / 读数 / 星点），
   否则那 0.5s 的淡出里读数会叠在已经露出的首页内容上 —— 截图确认过这个瑕疵 */
.ink-loader.opening .hud,
.ink-loader.opening .optic,
.ink-loader.opening .seed {
  opacity: 0;
  transition: opacity 0.22s linear;
}
.ink-loader.rest .reticle {
  opacity: 0;
}
.reticle {
  position: absolute;
  inset: 0;
  transition: opacity 0.6s var(--e-settle);
}
.ticks line {
  stroke: var(--ink-3);
  stroke-width: 1;
  opacity: 0.75;
}
.ring-in circle,
.ring-out circle {
  fill: none;
  stroke: var(--line-strong);
  stroke-width: 1;
}
.ring-out .track {
  stroke: var(--line);
}
.ring-out .prog {
  stroke: var(--redshift);
  stroke-width: 2;
  stroke-linecap: round;
  filter: drop-shadow(0 0 6px oklch(0.665 0.196 34 / 0.6));
  transform: rotate(-90deg);
  transform-origin: 120px 120px;
}
.ring-in line,
.ring-out line {
  stroke: var(--vein);
  stroke-width: 2;
}
.cross line {
  stroke: var(--ink-1);
  stroke-width: 1;
  opacity: 0.9;
}
/* 双向旋转：内圈顺时针 26s、外圈逆时针 40s —— 仪器在扫天 */
.ring-in {
  transform-origin: 120px 120px;
  animation: spin-cw 26s linear infinite;
}
.ring-out {
  transform-origin: 120px 120px;
  animation: spin-ccw 40s linear infinite;
}
@keyframes spin-cw {
  to {
    transform: rotate(360deg);
  }
}
@keyframes spin-ccw {
  to {
    transform: rotate(-360deg);
  }
}

/* ── 中心星点 + 墨晕 ─────────────────────────────────────────────── */
.seed {
  position: absolute;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ink-0);
  box-shadow: 0 0 14px 3px oklch(0.945 0.014 265 / 0.6);
  animation: seed 2.6s var(--e-drift) infinite;
  z-index: 3;
}
@keyframes seed {
  0%,
  100% {
    opacity: 0.7;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.25);
  }
}
/* 墨晕：随进度增强的柔光，与刻度环进度同步 */
.halo {
  position: absolute;
  width: 46vmax;
  height: 46vmax;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    oklch(0.945 0.014 265 / 0.18) 0 16%,
    oklch(0.665 0.196 34 / 0.12) 32%,
    transparent 60%
  );
  filter: blur(34px);
  opacity: calc(0.22 + var(--p, 0) * 0.78);
  pointer-events: none;
  z-index: 1;
}
.ink-loader.rest .halo {
  opacity: 0;
}

/* ── HUD 四角读数 ───────────────────────────────────────────────── */
.hud {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 4;
}
.corner {
  position: absolute;
  color: var(--ink-2);
}
.tl {
  left: var(--pad);
  top: var(--pad);
}
.tr {
  right: var(--pad);
  top: var(--pad);
}
.bl {
  left: var(--pad);
  bottom: var(--pad);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-0);
}
.br {
  right: var(--pad);
  bottom: var(--pad);
  color: var(--ink-3);
}
.live {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--vein);
  animation: ping 2.2s var(--e-settle) infinite;
}
@keyframes ping {
  0% {
    box-shadow: 0 0 0 0 oklch(0.775 0.098 200 / 0.5);
  }
  70% {
    box-shadow: 0 0 0 9px oklch(0.775 0.098 200 / 0);
  }
  100% {
    box-shadow: 0 0 0 0 oklch(0.775 0.098 200 / 0);
  }
}
/* 巨型读数：底部居中，与刻度环同一数值 */
.digits {
  position: absolute;
  left: 50%;
  bottom: calc(var(--pad) + 6px);
  transform: translateX(-50%);
  font-family: var(--font-mono);
  font-weight: 300;
  font-size: clamp(2rem, 6vw, 4.4rem);
  line-height: 0.85;
  letter-spacing: -0.05em;
  color: var(--ink-0);
  mix-blend-mode: difference;
}

@media (max-width: 640px) {
  .tr,
  .br {
    display: none;
  }
  .optic {
    width: 190px;
    height: 190px;
    margin: -95px 0 0 -95px;
  }
  .reticle {
    width: 190px;
    height: 190px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .seed,
  .ring-in,
  .ring-out,
  .live {
    animation: none;
  }
  .ink-loader::before {
    display: none;
  }
}
</style>
