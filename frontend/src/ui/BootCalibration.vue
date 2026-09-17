<!--
  BootCalibration —— 进入动画（校准台）
  ---------------------------------------------------------------------------
  在 v2 上新增。形态对齐用户给的参考稿：
    ① 面板铺满、内容**贴底左右分布**：左下角读数 00 - 100，右下角三行阶段
       「观测站上线 / 装载星表 / 校准完成」按进度**逐行点亮**
    ② 走完后 **整块向上抽走**（translateY(-102%)，1s 缓动）
    ③ 抽走后卸载并给 body 加 .ready，触发页面的入场动画
    ④ 全程锁滚动；任意键/点击可提前跳过；3.4s 安全网

  视觉用 v2 自己的语言：暖米底 --bg、朱砂 --accent、衬线 --font-display、
  --surface 面板、--line 分隔、--r-xl 圆角、--ease 缓动。

  - 时间驱动方式（这是我在 v3 上踩过三个坑后确定的写法，不要改回去）：
    . **不要用 rAF 回调的 timestamp 做差值** —— 它与 performance.now() 时间原点不同，
      会算出负数（实测出现过 -33）
    . **不要靠 rAF 驱动进度** —— 后台标签页/省电/无头环境下 rAF 会被节流
      （实测 3 秒只触发 7 次），进度会卡死
    . **不要写成"每帧固定 +16ms"** —— 那样帧率越高动画越快（实测快一倍）
    正解：用 Date.now() 决定"过了多久"，rAF 只负责重绘，另加 100ms 兜底定时器；
    读数夹紧 0..100。动画时长因此与帧率、与节流都无关。
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const emit = defineEmits(['done'])

const DUR = 1250 // 计数时长（ms），与参考稿一致
const STEPS = ['观测站上线', '装载星表', '校准完成']

const progress = ref(0)
const done = ref(false)
const gone = ref(false)
const stepIndex = ref(0)

let raf = 0
let tickTimer = 0
let hideTimer = 0
let safety = 0
let finished = false

const readout = computed(() => String(Math.round(progress.value)).padStart(2, '0'))

function reduced() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** 结束：加 .done 触发向上抽走，抽完（1.2s）再卸载 */
function finish() {
  if (finished) return
  finished = true
  done.value = true
  document.body.style.overflow = ''
  document.body.classList.add('ready')
  hideTimer = setTimeout(() => {
    gone.value = true
    emit('done')
  }, 1200)
}

/** 任意键 / 点击：直接补满并抽走（保留转场观感，不是瞬间消失） */
function skip() {
  if (finished) return
  progress.value = 100
  stepIndex.value = 2
  finish()
}

onMounted(() => {
  if (reduced()) {
    // 减弱动效：不播开场，直接进入
    document.body.classList.add('ready')
    emit('done')
    return
  }

  const t0 = Date.now()
  const step = () => {
    const p = Math.min(1, Math.max(0, (Date.now() - t0) / DUR))
    const e = 1 - Math.pow(1 - p, 3) // 缓出，与参考稿一致
    progress.value = Math.min(100, Math.max(0, e * 100))
    stepIndex.value = p < 0.34 ? 0 : p < 0.72 ? 1 : 2
    if (p < 1) raf = requestAnimationFrame(step)
    else setTimeout(finish, 160)
  }

  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', skip)
  window.addEventListener('pointerdown', skip)
  // 安全网：任何异常都不能把用户锁在加载页
  safety = setTimeout(skip, 3400)

  raf = requestAnimationFrame(step)
  // 兜底：即使 rAF 被完全节流，也用定时器继续推进进度
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
    aria-label="正在校准观测站"
  >
    <div class="boot__left">
      <div class="boot__brand">研错本 . 夜航星图</div>
      <div class="boot__num">{{ readout }}</div>
    </div>

    <div class="boot__steps" aria-hidden="true">
      <span v-for="(s, i) in STEPS" :key="s" :class="{ on: i === stepIndex }">{{ s }}</span>
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
  /* 不留圆角：全屏面板若带圆角，抽走时底边会露一条页面（截图实测） */
  border-radius: 0;
  overflow: hidden;
  /* 转场：整块向上抽走 */
  transition: transform 1s var(--ease);
  cursor: pointer;
}
.boot.done {
  transform: translateY(-105%);
}

.boot__left {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.boot__brand {
  font-family: var(--font-body);
  font-size: 12px;
  letter-spacing: 0.18em;
  color: var(--ink-3);
}
/* 读数用 v2 的衬线标题字：与站内大标题同一气质 */
.boot__num {
  font-family: var(--font-display);
  font-weight: 500;
  font-size: clamp(3.4rem, 11vw, 9rem);
  line-height: 0.82;
  letter-spacing: -0.04em;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.boot__steps {
  display: grid;
  gap: 8px;
  text-align: right;
}
.boot__steps span {
  font-family: var(--font-body);
  font-size: 12.5px;
  letter-spacing: 0.14em;
  color: var(--ink-3);
  opacity: 0.5;
  transition:
    color 0.4s var(--ease),
    opacity 0.4s var(--ease);
}
/* 当前阶段点亮：朱砂色，与站内强调色一致 */
.boot__steps span.on {
  color: var(--accent);
  opacity: 1;
}

@media (prefers-reduced-motion: reduce) {
  .boot {
    transition: none;
  }
}
</style>
