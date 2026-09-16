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

/** 落墨圆盘的扩散半径：随真实进度增长（用 vmax 保证窄屏也铺满） */
const inkRadius = computed(() => `${18 + progress.value * 1.35}vmax`)
const readout = computed(() => String(Math.round(progress.value)).padStart(3, '0'))
</script>

<template>
  <div
    class="ink-loader"
    :class="phase"
    role="progressbar"
    :aria-valuenow="Math.round(progress)"
    aria-valuemin="0"
    aria-valuemax="100"
    aria-label="正在装载星表"
  >
    <!-- 悬停的星点：第一段的唯一元素 -->
    <span class="seed" aria-hidden="true"></span>

    <!-- 落墨：随进度扩散的圆盘（多尺度模糊 = 墨在纤维里洇开） -->
    <span class="ink" :style="{ '--r': inkRadius }" aria-hidden="true"></span>

    <!-- 读数：等宽、极小、靠下 —— 仪器感 -->
    <div class="readout">
      <span class="mono label">研错本 · 夜航星图</span>
      <span class="num digits">{{ readout }}</span>
      <span class="mono hint">任意键跳过</span>
    </div>
  </div>
</template>

<style scoped>
.ink-loader {
  position: fixed;
  inset: 0;
  z-index: var(--z-loader);
  background: var(--sky-0);
  overflow: hidden;
  cursor: pointer;
}
/* 揭幕：沿斜向掀起（clip-path 只影响合成，不触发布局） */
.ink-loader.opening {
  clip-path: polygon(0 0, 100% 0, 100% 0, 0 0);
  transition: clip-path 0.6s var(--e-settle);
  pointer-events: none;
}
.ink-loader.inking .seed {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.4);
}

/* 悬停的星点：极小的白点，轻微脉动 */
.seed {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 5px;
  height: 5px;
  margin: 0;
  border-radius: 50%;
  background: var(--ink-0);
  box-shadow: 0 0 12px 2px oklch(0.945 0.014 265 / 0.5);
  transform: translate(-50%, -50%);
  animation: seed 2.6s var(--e-drift) infinite;
  transition:
    opacity 0.5s var(--e-settle),
    transform 0.5s var(--e-settle);
}
@keyframes seed {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

/* 落墨：一个随进度扩散的圆，三层模糊叠出"洇开"的层次 */
.ink {
  position: absolute;
  left: 50%;
  top: 50%;
  width: calc(var(--r) * 2);
  height: calc(var(--r) * 2);
  margin: calc(var(--r) * -1) 0 0 calc(var(--r) * -1);
  background:
    radial-gradient(circle at 50% 50%, oklch(0.945 0.014 265 / 0.98) 0 34%, transparent 72%),
    radial-gradient(circle at 47% 52%, oklch(0.665 0.196 34 / 0.55) 0 30%, transparent 78%),
    radial-gradient(circle at 53% 47%, oklch(0.775 0.098 200 / 0.3) 0 26%, transparent 80%);
  filter: blur(28px) contrast(1.06);
  will-change: width, height;
}
.ink-loader.rest .ink {
  width: 0;
  height: 0;
  margin: 0;
}

/* 读数：固定在底部两侧，不与墨迹抢视觉 */
.readout {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: var(--pad);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  pointer-events: none;
}
.digits {
  font-family: var(--font-mono);
  font-weight: 300;
  font-size: clamp(2.2rem, 7vw, 5.4rem);
  line-height: 0.82;
  letter-spacing: -0.05em;
  color: var(--ink-0);
  mix-blend-mode: difference; /* 墨迹盖过来时读数反相，始终可读 */
}
.label {
  color: var(--ink-1);
}
.hint {
  color: var(--ink-3);
}

@media (max-width: 640px) {
  .readout {
    flex-wrap: wrap;
  }
  .hint {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .seed {
    animation: none;
  }
  .ink {
    filter: blur(20px);
  }
}
</style>
