<!--
  研错本 · 开机（撕裂揭幕版）
  ===========================================================================
  用户要求的时间线：
    1) **明显的进度条 1 -> 100%**
    2) 到 100% 后，中间的圆**转圈**
    3) 然后从中间**开裂**：上半部分向上滑动、下半部分向下滑动
    4) 首页出现

  实现关键：**真的把屏幕撕成两半**，而不是简单上滑。
  做法：两个 .boot__half 都铺满全屏、都放一份**完整内容**，
  再用 clip-path 各裁一半（上面裁下 50%、下面裁上 50%）。
  这样两半各带着"属于自己那一半"的画面一起滑走 —— 看起来就是屏幕被撕开。

  时间驱动一律「按 wall-clock 算进度 + setInterval 兜底」，**不许只靠 rAF**：
  v3 上实测过，无头环境 rAF 3 秒只触发 7 次，逐帧驱动的进度会卡死。
  改回纯 rAF 会让撕裂阶段永远不结束，遮罩卡在 spin 上压住整页（真实浏览器
  后台标签页同样会触发，因为帧被浏览器推迟）。
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const emit = defineEmits(['done'])

const BRAND = '研错本'
const SUB = '考研错题管理'
const STEPS = ['载入错题库', '整理复习队列', '校准完成']

const COUNT_MS = 1400 // 1 -> 100
const SPIN_MS = 660 // 圆环转圈
const SPLIT_MS = 860 // 两半分离

const progress = ref(1)
const stepIndex = ref(0)
const phase = ref('boot') // boot | spin | split | gone

const rootEl = ref(null)
// 每个 runAnim 注册一个自己的收尾函数；结束时自摘，卸载时全摘。
const animStops = new Set()

let raf = 0
let tickTimer = 0
let safety = 0
let finished = false

const readout = computed(() => String(Math.round(progress.value)).padStart(2, '0'))

function reduced() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * 用 JS 驱动一段动画（写内联样式）。
 *
 * 为什么不用 CSS transition/animation（实测排除后的定论）：
 *   CSS 规则在产物里、选择器也匹配（half.matches(...) === true），
 *   但 transition 与 animation 都不推进 —— 位移恒为 0。
 *   而 Date.now + 定时器驱动的进度是正常的。
 *   根因与早先实测的「无头环境 rAF 3 秒只触发 7 次」同源：合成器不产生帧。
 *   改为 JS 写内联 transform 后，任何环境下行为一致。
 */

/**
 * 粒子迸发：从圆心向外炸开约 44 个粒子。
 *
 * 为什么用 JS 而不是 CSS 动画：本环境（无头/合成器不产帧）里 CSS 动画与过渡
 * 都不推进 —— 实测过选择器匹配、类名已渲染，但位移恒为 0。
 * JS 写内联 transform 则稳定生效。
 */
function burstParticles() {
  // 每个半屏的粒子层**各自**创建粒子：
  // 只做一份再复制，动画时分身同步，看起来仍像"一层"；
  // 各自随机后，撕裂时两半的轨迹不同 —— 符合"屏幕被撕开"的直觉。
  const hosts = Array.from(rootEl.value?.querySelectorAll('.boot__burst') || [])
  if (!hosts.length) return

  const cx = window.innerWidth / 2
  const cy = window.innerHeight / 2
  // 三色：朱砂为主，少量琥珀与米白 —— 保持 v2 的配色语言
  const colors = ['var(--accent)', 'var(--gold)', 'var(--ink)']
  const perHost = 26

  const parts = []
  hosts.forEach((host) => {
    for (let i = 0; i < perHost; i++) {
      const el = document.createElement('span')
      el.className = 'boot__particle'
      const size = 2 + Math.random() * 4
      el.style.width = `${size.toFixed(1)}px`
      el.style.height = `${size.toFixed(1)}px`
      el.style.left = `${cx}px`
      el.style.top = `${cy}px`
      el.style.background = colors[Math.floor(Math.random() * colors.length)]
      host.appendChild(el)

      const angle = Math.random() * Math.PI * 2
      const dist = 80 + Math.random() * 320
      parts.push({
        el,
        dx: Math.cos(angle) * dist,
        dy: Math.sin(angle) * dist,
        spin: (Math.random() - 0.5) * 240,
      })
    }
  })

  runAnim(1150, (p) => {
    const e = 1 - Math.pow(1 - p, 2.2) // 缓出：一开始快，逐渐减速
    const fade = p < 0.25 ? p / 0.25 : 1 - (p - 0.25) / 0.75
    const op = Math.max(0, fade).toFixed(3)
    parts.forEach((q) => {
      const x = q.dx * e
      const y = q.dy * e
      const sc = 1 - e * 0.55
      q.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) scale(${sc.toFixed(3)}) rotate(${(q.spin * e).toFixed(1)}deg)`
      q.el.style.opacity = op
    })
  }).then(() => {
    parts.forEach((q) => q.el.remove())
  })
}

function runAnim(duration, onTick) {
  return new Promise((resolve) => {
    // 双驱动：rAF 负责逐帧平滑，setInterval 负责"rAF 根本不产帧"的场合。
    // 只留 rAF 会卡死整条时间线：后台标签页/无头里合成器不排帧（本文件开头
    // 记录的实测是 3 秒只触发 7 次，进度段靠 setInterval 兜底才走完），于是
    // startSpin 的第一个 await 永远不返回，遮罩停在 spin 阶段压住整页。
    const t0 = performance.now()
    let rafId = 0
    let timer = 0
    let done = false
    const stop = () => {
      if (done) return
      done = true
      cancelAnimationFrame(rafId)
      clearInterval(timer)
      animStops.delete(stop)
      resolve()
    }
    const step = (now) => {
      if (done) return
      const p = Math.min(1, (now - t0) / duration)
      try {
        onTick(p)
      } catch {
        // 单帧写样式失败不该让开场停摆；下一次 step 照常推进到收尾
      }
      if (p >= 1) stop()
    }
    const loop = (now) => {
      step(now)
      if (!done) rafId = requestAnimationFrame(loop)
    }
    rafId = requestAnimationFrame(loop)
    timer = setInterval(() => step(performance.now()), 90)
    animStops.add(stop)
  })
}

/** 缓出 */
const easeOut = (p) => 1 - Math.pow(1 - p, 3)

/** 到 100% 之后：先转圈，再撕裂，最后卸载 */
async function startSpin() {
  if (phase.value !== 'boot') return
  phase.value = 'spin'
  // 用 querySelectorAll：两个半屏各有一个 dial，只取第一个会导致
  // 下半屏的圆不转（用户实测反馈过）
  const dials = Array.from(rootEl.value?.querySelectorAll('.boot__dial') || [])
  const halfTop = rootEl.value?.querySelector('.boot__half--top')
  const halfBot = rootEl.value?.querySelector('.boot__half--bottom')

  // 1) 粒子迸发（与转圈同时开始，视觉上就是"能量从圆心炸开"）
  burstParticles()

  // 2) 圆环转两圈 + 轻微放大（模拟"启动"的动作）
  await runAnim(SPIN_MS, (p) => {
    if (!dials.length) return
    const deg = easeOut(p) * 720
    const scale = 1 + Math.sin(p * Math.PI) * 0.045
    const tf = `translate(-50%, -50%) rotate(${deg.toFixed(1)}deg) scale(${scale.toFixed(3)})`
    dials.forEach((d) => {
      d.style.transform = tf
    })
  })

  // 2) 撕裂：上半向上、下半向下
  phase.value = 'split'
  document.body.classList.add('ready')
  await runAnim(SPLIT_MS, (p) => {
    const e = easeOut(p)
    const d = e * 102
    if (halfTop) halfTop.style.transform = `translateY(${(-d).toFixed(2)}%)`
    if (halfBot) halfBot.style.transform = `translateY(${d.toFixed(2)}%)`
  })

  // 3) 卸载，首页入场
  phase.value = 'gone'
  document.body.style.overflow = ''
  emit('done')
}

function finish() {
  if (finished) return
  finished = true
  progress.value = 100
  stepIndex.value = STEPS.length - 1
  startSpin()
}

/** 任意键/点击：直接补满并走完后续（保留观感，不是瞬间消失） */
function skip() {
  if (finished) return
  finish()
}

onMounted(() => {
  if (reduced()) {
    document.body.classList.add('ready')
    phase.value = 'gone'
    emit('done')
    return
  }

  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', skip)
  window.addEventListener('pointerdown', skip)
  safety = setTimeout(skip, 4200)

  const t0 = Date.now()
  const step = () => {
    if (finished) return
    const p = Math.min(1, Math.max(0, (Date.now() - t0) / COUNT_MS))
    const eased = 1 - Math.pow(1 - p, 3) // 缓出
    // 从 1 开始（用户要求 1 -> 100）
    progress.value = Math.max(1, Math.min(99, 1 + eased * 98))
    stepIndex.value = p < 0.34 ? 0 : p < 0.72 ? 1 : 2
    if (p < 1) raf = requestAnimationFrame(step)
    else setTimeout(finish, 90)
  }
  raf = requestAnimationFrame(step)

  // 兜底：rAF 被节流时仍推进（否则会停在半路）
  tickTimer = setInterval(() => {
    if (!finished && phase.value === 'boot') step()
  }, 100)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  clearInterval(tickTimer)
  animStops.forEach((stop) => stop())
  animStops.clear()
  clearTimeout(safety)
  window.removeEventListener('keydown', skip)
  window.removeEventListener('pointerdown', skip)
  document.body.style.overflow = ''
})
</script>

<template>
  <div
    v-if="phase !== 'gone'"
    ref="rootEl"
    class="boot"
    :class="[`is-${phase}`]"
    :style="{ '--p': progress / 100 }"
    role="progressbar"
    :aria-valuenow="Math.round(progress)"
    aria-valuemin="1"
    aria-valuemax="100"
    :aria-label="`正在载入${BRAND}`"
  >
    <!--
      两个半屏：各放一份**完整内容**，再用 clip-path 各裁一半。
      这样两半各带着"属于自己那一半"的画面滑走 —— 视觉上就是屏幕被撕开，
      而不是"一层覆盖物滑走"（后者就是用户抱怨过的"也只是上滑一下"）。
    -->
    <div class="boot__half boot__half--top" aria-hidden="true">
      <div class="boot__content">
        <span class="boot__frame"></span>
        <span class="boot__tear" aria-hidden="true"></span>
        <div class="boot__burst" aria-hidden="true"></div>
        <!-- 撕裂线：各半屏各带一条，贴在自己那一侧的分界边上 -->
        <span class="boot__tear" aria-hidden="true"></span>
        <div class="boot__burst" aria-hidden="true"></div>
        <svg class="boot__dial" viewBox="0 0 300 300" :style="{ '--p': progress / 100 }">
          <g class="boot__ticks">
            <line
              v-for="n in 36"
              :key="n"
              x1="150"
              :y1="n % 3 === 0 ? 5 : 10"
              x2="150"
              y2="19"
              :transform="`rotate(${(n - 1) * 10} 150 150)`"
            />
          </g>
          <circle class="boot__track" cx="150" cy="150" r="132" />
          <circle
            class="boot__arc"
            cx="150"
            cy="150"
            r="132"
            :stroke-dasharray="829.4"
            :stroke-dashoffset="829.4 * (1 - progress / 100)"
          />
        </svg>
        <div class="boot__core">
          <span class="boot__seal">错</span>
          <span class="boot__word">{{ BRAND }}</span>
        </div>
        <div class="boot__bottom">
          <div class="boot__left">
            <div class="boot__brand">
              <span class="boot__mark"></span>
              {{ BRAND }}
              <em>{{ SUB }}</em>
            </div>
            <div class="boot__num">{{ readout }}<i>%</i></div>
          </div>
          <div class="boot__steps">
            <span
              v-for="(s, i) in STEPS"
              :key="s"
              :class="{ on: i === stepIndex, past: i < stepIndex }"
            >
              {{ s }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="boot__half boot__half--bottom" aria-hidden="true">
      <div class="boot__content">
        <span class="boot__frame"></span>
        <svg class="boot__dial" viewBox="0 0 300 300" :style="{ '--p': progress / 100 }">
          <g class="boot__ticks">
            <line
              v-for="n in 36"
              :key="`b${n}`"
              x1="150"
              :y1="n % 3 === 0 ? 5 : 10"
              x2="150"
              y2="19"
              :transform="`rotate(${(n - 1) * 10} 150 150)`"
            />
          </g>
          <circle class="boot__track" cx="150" cy="150" r="132" />
          <circle
            class="boot__arc"
            cx="150"
            cy="150"
            r="132"
            :stroke-dasharray="829.4"
            :stroke-dashoffset="829.4 * (1 - progress / 100)"
          />
        </svg>
        <div class="boot__core">
          <span class="boot__seal">错</span>
          <span class="boot__word">{{ BRAND }}</span>
        </div>
        <div class="boot__bottom">
          <div class="boot__left">
            <div class="boot__brand">
              <span class="boot__mark"></span>
              {{ BRAND }}
              <em>{{ SUB }}</em>
            </div>
            <div class="boot__num">{{ readout }}<i>%</i></div>
          </div>
          <div class="boot__steps">
            <span
              v-for="(s, i) in STEPS"
              :key="`b${s}`"
              :class="{ on: i === stepIndex, past: i < stepIndex }"
            >
              {{ s }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 明显的进度条：横贯底部整宽，4px 高，朱砂填充 + 游标 -->
    <div class="boot__progress" aria-hidden="true">
      <span class="boot__progress-fill" :style="{ transform: `scaleX(${progress / 100})` }"></span>
      <span class="boot__progress-knob" :style="{ left: `${progress}%` }"></span>
    </div>
  </div>
</template>

<style scoped>
.boot {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: transparent;
  cursor: pointer;
  overflow: hidden;
}

/* 两个半屏：铺满全屏 + 各裁一半 + 各带一份完整内容 */
.boot__half {
  position: absolute;
  inset: 0;
  background: var(--bg);
  will-change: transform;
}
.boot__half--top {
  clip-path: inset(0 0 50% 0);
}
.boot__half--bottom {
  clip-path: inset(50% 0 0 0);
}
/*
  撕裂：上半向上、下半向下。
  用 animation 而不是 transition：实测 transition 在这个场景（Vue 响应式切类 +
  clip-path 元素）里不可靠 —— 选择器明明匹配（matchesSplit=true），
  但位移始终为 0。animation 由类名触发、自身控时，不依赖属性变化检测。
*/
/* 撕裂由 JS 写内联 transform 驱动（见脚本注释：CSS 动画在无头环境不推进） */

.boot__content {
  position: absolute;
  inset: 0;
  display: block;
}

/* 四角取景框 */
.boot__frame {
  position: absolute;
  inset: clamp(16px, 2.6vw, 40px);
  pointer-events: none;
  opacity: 0.5;
}
.boot__frame::before,
.boot__frame::after {
  content: '';
  position: absolute;
  width: clamp(18px, 2.4vw, 34px);
  height: clamp(18px, 2.4vw, 34px);
  border: 1px solid var(--line-strong);
}
.boot__frame::before {
  top: 0;
  left: 0;
  border-right: 0;
  border-bottom: 0;
}
.boot__frame::after {
  right: 0;
  bottom: 0;
  border-left: 0;
  border-top: 0;
}

/* 刻度环 + 弧线进度 */
.boot__dial {
  position: absolute;
  left: 50%;
  top: 50%;
  width: min(72vmin, 620px);
  height: min(72vmin, 620px);
  transform: translate(-50%, -50%);
  pointer-events: none;
  opacity: 0.9;
  will-change: transform;
}
.boot__ticks {
  transform-origin: 150px 150px;
  transform: rotate(calc(var(--p, 0) * 360deg));
  transition: transform 0.2s linear;
}
.boot__ticks line {
  stroke: var(--line-strong);
  stroke-width: 1;
}
.boot__track {
  fill: none;
  stroke: var(--line);
  stroke-width: 1;
}
.boot__arc {
  fill: none;
  stroke: var(--accent);
  stroke-width: 2.5;
  stroke-linecap: round;
  transform: rotate(-90deg);
  transform-origin: 150px 150px;
}

/* 到 100% 后：圆环**加速转圈**（两圈）并轻微放大，形成"启动"的动作 */
/* 转圈同样由 JS 驱动 */

.boot.is-spin .boot__arc {
  stroke-width: 4;
  filter: drop-shadow(0 0 10px color-mix(in srgb, var(--accent) 60%, transparent));
}

/* 中心印记 + 品牌字 */
.boot__core {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(10px, 2vh, 20px);
  pointer-events: none;
}
.boot__seal {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: clamp(8rem, 26vw, 22rem);
  line-height: 0.8;
  letter-spacing: -0.06em;
  color: var(--accent);
  opacity: 0.06;
}
.boot__word {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: clamp(1.4rem, 3.4vw, 2.4rem);
  letter-spacing: 0.22em;
  color: var(--ink);
}

/* 底部左右：品牌与读数（左）／阶段（右） */
.boot__bottom {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: clamp(24px, 4vw, 56px);
  padding-bottom: clamp(48px, 6vw, 78px);
}
.boot__left {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.boot__brand {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--ink);
  animation: settle 1s cubic-bezier(0.34, 1.3, 0.44, 1) both;
}
@keyframes settle {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
.boot__mark {
  width: 9px;
  height: 9px;
  background: var(--accent);
  border-radius: 2px;
  animation: mark-spin 5s var(--ease) infinite;
}
@keyframes mark-spin {
  0%,
  72% {
    transform: rotate(0) scale(1);
  }
  88% {
    transform: rotate(200deg) scale(0.7);
  }
  100% {
    transform: rotate(360deg) scale(1);
  }
}
.boot__brand em {
  font-style: normal;
  font-weight: 400;
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--ink-3);
}
.boot__num {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-weight: 300;
  font-size: clamp(3.4rem, 11vw, 8.6rem);
  line-height: 0.82;
  letter-spacing: -0.03em;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.boot__num i {
  font-style: normal;
  font-size: 0.32em;
  color: var(--ink-3);
  margin-left: 4px;
}
.boot__steps {
  display: grid;
  gap: 9px;
  text-align: right;
}
.boot__steps span {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 12px;
  letter-spacing: 0.16em;
  color: var(--ink-3);
  opacity: 0.45;
  transition:
    color 0.4s var(--ease),
    opacity 0.4s var(--ease),
    transform 0.5s cubic-bezier(0.34, 1.3, 0.44, 1);
}
.boot__steps span.past {
  opacity: 0.6;
  transform: translateX(-4px);
}
.boot__steps span.on {
  color: var(--accent);
  opacity: 1;
  transform: none;
}

/* ── 明显的进度条（用户要求 1 -> 100%）───────────────────────────────
   横贯屏幕底部**整宽**，4px 高，朱砂填充 + 一个游标点。
   原来是一条 320px 的短细条，不够"明显"。 */
.boot__progress {
  position: absolute;
  left: clamp(24px, 4vw, 56px);
  right: clamp(24px, 4vw, 56px);
  bottom: clamp(26px, 3.4vw, 42px);
  height: 4px;
  background: var(--line-strong);
}
.boot__progress-fill {
  display: block;
  height: 100%;
  background: var(--accent);
  transform-origin: left center;
  will-change: transform;
}
.boot__progress-knob {
  position: absolute;
  top: 50%;
  width: 11px;
  height: 11px;
  margin-left: -6px;
  margin-top: -6px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 20%, transparent);
}
/* 撕裂瞬间：进度条淡出（它属于下半部分） */
.boot.is-split .boot__progress {
  animation: fade-out 0.22s ease forwards;
}
@keyframes fade-out {
  to {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .boot__half,
  .boot__progress {
    transition: none;
  }
  .boot.is-spin .boot__dial {
    animation: none;
  }
}
/* ── 撕裂线（用户："中间整体的分裂感不强，加一条明显的动态感线"）──────────
   两条线，各自贴在自己那一侧的分界边：
     上半屏 bottom:0、下半屏 top:0。
   撕裂时两条发光边线一起被拉开 —— 分裂感来自"两条线被拉开"，
   而不只是"画面平移"。强度随进度增长（--p），到 100% 时最亮。 */
.boot__tear {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  /*
    只在到 100% 时出现（用户明确要求）。
    原来写成随进度从 0.25 亮到 1.00 —— 也就是全程可见，不符合预期。
    现在默认 opacity:0，只有 .is-spin / .is-split 阶段才亮起。
  */
  opacity: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    color-mix(in srgb, var(--accent) 55%, transparent) 12%,
    var(--accent) 50%,
    color-mix(in srgb, var(--accent) 55%, transparent) 88%,
    transparent 100%
  );
  box-shadow:
    0 0 12px 1px color-mix(in srgb, var(--accent) 45%, transparent),
    0 0 30px 4px color-mix(in srgb, var(--accent) 18%, transparent);
}
/*
  线要定位在**裁剪边界**上，而不是 content 的上下边：
  .boot__content 铺满全屏，它的 bottom:0 落在视口底（实测 y=1048），
  而那一带已被 clip 裁掉 —— 线根本看不见。
  top:50% 才是真正的撕开处。
*/
.boot__half--top .boot__tear {
  top: calc(50% - 2px);
}
.boot__half--bottom .boot__tear {
  top: 50%;
}
/* 撕裂阶段保持可见（它随两半一起被拉开） */
.boot.is-split .boot__tear {
  opacity: 1;
}
/* 到 100%（转圈阶段）才出现，并更粗更亮，强调"要裂了" */
.boot.is-spin .boot__tear {
  opacity: 1;
  height: 3px;
  transition: opacity 0.28s ease-out;
  box-shadow:
    0 0 18px 2px color-mix(in srgb, var(--accent) 62%, transparent),
    0 0 46px 8px color-mix(in srgb, var(--accent) 26%, transparent);
}

/* ── 粒子迸发层 ─────────────────────────────────────────────────────────
   绝对定位的小圆点，初始都在圆心，由 JS 写 transform 向外炸开。
   用 JS 而不是 CSS 动画的原因见脚本注释（本环境 CSS 动画不推进）。 */
.boot__burst {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 3;
  overflow: hidden;
}
.boot__particle {
  position: absolute;
  border-radius: 50%;
  transform: translate3d(0, 0, 0);
  will-change: transform, opacity;
  filter: blur(0.3px);
}

@media (prefers-reduced-motion: reduce) {
  .boot__burst {
    display: none;
  }
}
</style>
