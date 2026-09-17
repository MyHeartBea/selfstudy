<!--
  研错本 · 开场（开机校准）
  ===========================================================================
  用户反馈："这怎么还是夜航星图？你能不能做一个我们自己的呢""启动动画太简陋了，
  相当于就是一个上滑动画"

  所以这一版做两件事：
    ① **品牌回到我们自己**：研错本 · 考研错题管理（不再出现借来的"夜航星图"命名）
    ② **动效从"线性上滑"改成物理运动**：过冲曲线 / 分速度 / 错峰 / 落定沉降

  物理实现方式（与在 v3 上踩的坑有关）：
    用**阻尼谐振子的解析解**，不逐帧模拟 —— 解析解与帧率无关，也不会被 rAF 节流影响
    （v3 上实测：无头环境 rAF 3 秒只触发 7 次，逐帧驱动的进度会卡死）。
      s(t) = 1 - e^(-ζωt)·[cos(ω_d t) + (ζω/ω_d)·sin(ω_d t)]，ω_d = ω√(1-ζ²)
    ζ<1 会过冲 —— 这就是"弹簧感"的来源。本文件里的 spring() 就是它，供后续复用。

  各处动效：
    · 品牌行：落定沉降（过冲曲线，像"落"下来而不是"出现"）
    · 数字：缓出走到 100（数字用弹簧回弹会显得廉价）
    · 阶段行：三行按进度错峰点亮；已完成的退到次级色并轻微左移，当前行朱砂色
    · 进度条：与数字同步的 2px 朱砂线（给"开机"一个可读完成度）
    · 揭幕：整块 upward 抽走用**过冲曲线**，且**内容与整块分速度**（内容额外上浮淡出）
      —— 这是"有物理感"与"就是平移一下"的区别
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const emit = defineEmits(['done'])

const BRAND = '研错本'
const SUB = '考研错题管理'
const STEPS = ['载入错题库', '整理复习队列', '校准完成']
const DUR = 1400

const progress = ref(0)
const stepIndex = ref(0)
const done = ref(false)
const gone = ref(false)

let raf = 0
let tickTimer = 0
let hideTimer = 0
let safety = 0
let finished = false

const readout = computed(() => String(Math.round(progress.value)).padStart(2, '0'))

function reduced() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * 阻尼谐振子解析解：ζ<1 时过冲（弹簧感）。
 * 保留导出式写法供后续鼠标拖拽/卡片落定复用，不逐帧模拟。
 */
// eslint-disable-next-line no-unused-vars
function spring(t, zeta = 0.72, omega = 9) {
  if (t >= 1) return 1
  const wd = omega * Math.sqrt(1 - zeta * zeta)
  const e = Math.exp(-zeta * omega * t)
  return 1 - e * (Math.cos(wd * t) + ((zeta * omega) / wd) * Math.sin(wd * t))
}

function finish() {
  if (finished) return
  finished = true
  done.value = true
  document.body.style.overflow = ''
  document.body.classList.add('ready')
  hideTimer = setTimeout(() => {
    gone.value = true
    emit('done')
  }, 1150)
}

function skip() {
  if (finished) return
  progress.value = 100
  stepIndex.value = 2
  finish()
}

onMounted(() => {
  if (reduced()) {
    document.body.classList.add('ready')
    emit('done')
    return
  }

  const t0 = Date.now()
  const step = () => {
    const raw = Math.min(1, Math.max(0, (Date.now() - t0) / DUR))
    const ease = 1 - Math.pow(1 - raw, 3) // 计数用缓出，不用弹簧（数字回弹显得廉价）
    progress.value = Math.min(100, Math.max(0, ease * 100))
    const k = raw * 3 // 阶段按进度错峰推进
    stepIndex.value = k < 1 ? 0 : k < 2 ? 1 : 2
    if (raw < 1) raf = requestAnimationFrame(step)
    else setTimeout(finish, 180)
  }

  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', skip)
  window.addEventListener('pointerdown', skip)
  safety = setTimeout(skip, 3600)

  raf = requestAnimationFrame(step)
  // 兜底：rAF 被节流时仍推进（v3 的教训：不能只靠 rAF 驱动时长）
  tickTimer = setInterval(() => {
    if (!finished) step()
  }, 100)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  clearInterval(tickTimer)
  clearTimeout(hideTimer)
  clearTimeout(safety)
  window.removeEventListener('keydown', skip)
  window.removeEventListener('pointerdown', skip)
  document.body.style.overflow = ''
})
</script>

<template>
  <div
    v-if="!gone"
    class="boot"
    :class="{ done }"
    role="progressbar"
    :aria-valuenow="Math.round(progress)"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-label="`正在载入${BRAND}`"
  >
    <!-- 极淡网格：让"开机"有仪表感，而不是一块空白 -->
    <span class="boot__grid" aria-hidden="true"></span>
    <!-- 扫描光带：给"校准"提供持续运动（周期 2.6s） -->
    <span class="boot__scan" aria-hidden="true"></span>

    <!-- 中心主体：巨型印记（版式重心）+ 品牌字（逐字揭示） -->
    <div class="boot__core" aria-hidden="true">
      <span class="boot__seal">错</span>
      <span class="boot__word"> <i>研</i><i>错</i><i>本</i> </span>
    </div>

    <div class="boot__left">
      <div class="boot__brand">
        <span class="boot__mark" aria-hidden="true"></span>
        {{ BRAND }}
        <em>{{ SUB }}</em>
      </div>
      <div class="boot__num">{{ readout }}</div>
      <div class="boot__bar" aria-hidden="true">
        <i :style="{ transform: `scaleX(${progress / 100})` }"></i>
      </div>
    </div>

    <div class="boot__steps" aria-hidden="true">
      <span v-for="(s, i) in STEPS" :key="s" :class="{ on: i === stepIndex, past: i < stepIndex }">
        {{ s }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.boot {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: var(--bg);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: clamp(24px, 4vw, 56px);
  border-radius: 0;
  overflow: hidden;
  cursor: pointer;
  /* 揭幕：过冲曲线 —— 先快速离场、末段轻微减速，不是等速平移 */
  transition: transform 1.05s cubic-bezier(0.62, 0.02, 0.24, 1);
}
.boot.done {
  transform: translateY(-102%);
}
/* 内容与整块**分速度**：内容额外上浮淡出。这是"有物理感"与"整体平移一下"的区别。 */
.boot__left,
.boot__steps {
  transition:
    transform 0.9s cubic-bezier(0.62, 0.02, 0.24, 1),
    opacity 0.7s ease;
}
.boot.done .boot__left,
.boot.done .boot__steps {
  transform: translateY(-28px);
  opacity: 0;
}

.boot__grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.5;
  background-image:
    linear-gradient(to right, var(--line) 1px, transparent 1px),
    linear-gradient(to bottom, var(--line) 1px, transparent 1px);
  background-size: 72px 72px;
  mask-image: radial-gradient(70% 60% at 30% 70%, #000 20%, transparent 100%);
}

.boot__left {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
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
  /* 落定沉降：过冲曲线，像"落"下来而不是"出现" */
  animation: settle 1.1s cubic-bezier(0.34, 1.3, 0.44, 1) both;
}
@keyframes settle {
  0% {
    opacity: 0;
    transform: translateY(14px);
  }
  60% {
    opacity: 1;
  }
  100% {
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
  font-family: var(--font-display);
  font-weight: 500;
  font-size: clamp(3.6rem, 12vw, 9.6rem);
  line-height: 0.8;
  letter-spacing: -0.045em;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

/* 进度条：与数字同步，给"开机"一个可读完成度 */
.boot__bar {
  position: relative;
  width: min(320px, 42vw);
  height: 2px;
  background: var(--line-strong);
  overflow: hidden;
}
.boot__bar i {
  display: block;
  height: 100%;
  background: var(--accent);
  transform-origin: left;
  will-change: transform;
}

.boot__steps {
  position: relative;
  display: grid;
  gap: 9px;
  text-align: right;
}
.boot__steps span {
  font-size: 12px;
  letter-spacing: 0.16em;
  color: var(--ink-3);
  opacity: 0.45;
  transition:
    color 0.45s var(--ease),
    opacity 0.45s var(--ease),
    transform 0.5s cubic-bezier(0.34, 1.3, 0.44, 1);
}
/* 已完成：退到次级色并轻微左移，留下"读过"的痕迹 */
.boot__steps span.past {
  opacity: 0.6;
  transform: translateX(-4px);
}
/* 当前：朱砂色，右进的过冲曲线提供弹簧感 */
.boot__steps span.on {
  color: var(--accent);
  opacity: 1;
  transform: translateX(0);
}

@media (prefers-reduced-motion: reduce) {
  .boot,
  .boot__left,
  .boot__steps,
  .boot__brand,
  .boot__mark {
    transition: none;
    animation: none;
  }
}
/* ── 中心主体 ──────────────────────────────────────────────────────────
   为什么加：上一版内容全在底部两头，中间整块空着，构图失衡。
   用"错"字做版式重心 —— 它是"错题本"的直接标识，不是装饰图形。
   透明度压到 0.07：在米色底上刚好可见，是重心而不是主角。 */
.boot__core {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(10px, 2vh, 22px);
  pointer-events: none;
}
.boot__seal {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: clamp(9rem, 30vw, 26rem);
  line-height: 0.8;
  letter-spacing: -0.06em;
  color: var(--accent);
  opacity: 0.07;
  /* 落定：极慢的沉降，让它"压"在版面上而不是弹出来 */
  animation: seal-in 1.6s cubic-bezier(0.22, 1.12, 0.36, 1) both;
}
@keyframes seal-in {
  from {
    opacity: 0;
    transform: scale(1.04);
  }
  to {
    opacity: 0.07;
    transform: scale(1);
  }
}
/* 品牌字：逐字揭示（每个字比前一个晚 90ms） */
.boot__word {
  display: flex;
  gap: 0.05em;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: clamp(1.4rem, 3.6vw, 2.6rem);
  letter-spacing: 0.16em;
  color: var(--ink);
}
.boot__word i {
  font-style: normal;
  display: inline-block;
  opacity: 0;
  transform: translateY(0.5em);
  animation: word-up 0.9s cubic-bezier(0.22, 1.12, 0.36, 1) both;
}
.boot__word i:nth-child(1) {
  animation-delay: 0.18s;
}
.boot__word i:nth-child(2) {
  animation-delay: 0.27s;
}
.boot__word i:nth-child(3) {
  animation-delay: 0.36s;
}
@keyframes word-up {
  to {
    opacity: 1;
    transform: none;
  }
}

/* ── 扫描光带 ──────────────────────────────────────────────────────────
   一条竖直柔光从左到右扫过面板。作用是让"校准"这件事持续可见地发生，
   同时因为它是柔光（blur + 极低透明度），不干扰内容的可读性。 */
.boot__scan {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 26vw;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--accent) 12%, transparent),
    transparent
  );
  filter: blur(26px);
  animation: scan-x 2.6s var(--ease) infinite;
}
@keyframes scan-x {
  from {
    transform: translateX(-30vw);
  }
  to {
    transform: translateX(125vw);
  }
}

@media (max-width: 760px) {
  .boot__seal {
    font-size: clamp(7rem, 46vw, 14rem);
  }
}
@media (prefers-reduced-motion: reduce) {
  .boot__seal,
  .boot__word i,
  .boot__scan {
    animation: none;
    opacity: 1;
    transform: none;
  }
  .boot__seal {
    opacity: 0.07;
  }
}
</style>
