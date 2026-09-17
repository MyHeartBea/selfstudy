<!--
  启动页 · 校准台（对齐 atlas 参考稿）
  ---------------------------------------------------------------------------
  用户指出："模版页还有一个进入首页后动画向上拉，然后出现首页的动态效果"
  —— 参考稿的转场是**整块面板向上抽走**；我之前做的是圆形遮罩揭开，不是一回事。

  参考稿的实现（已读其源码逐条对齐）：
    进场：左下角一行 00 - 100，缓出 1-(1-p)^3，历时 1250ms
          右下角三行「观测站上线 / 装载星表 / 校准完成」按进度逐行点亮
          （p<0.34 - 第1行，<0.72 - 第2行，否则第3行）
    转场：transform: translateY(-101%)，**1s 缓动**整块向上抽走
    收尾：抽走后 1.2s 卸载组件；body.ready 触发首页入场
    安全网：3400ms 强制结束；全程锁滚动

  与旧版的差别（本次修改的核心）：
    · 去掉圆形遮罩揭幕，改为**向上抽走**（translateY(-101%)）
    · 读数固定在**左下**、步骤固定在**右下**（参考稿是底部左右分布，不是居中）
    · 读数两位（参考稿 padStart(2, '0')）
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const emit = defineEmits(['done'])

const reduce =
  typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

const progress = ref(0)
const done = ref(false)
const gone = ref(false)
const stepIndex = ref(0)

const STEPS = ['观测站上线', '装载星表', '校准完成']
const DUR = 1250

let raf = 0
let hideTimer = 0
let safety = 0
let tickTimer = 0
let finished = false

const readout = computed(() => String(Math.round(progress.value)).padStart(2, '0'))

/** 结束：加 .done 让整块向上抽走，1.2s 后卸载（把控制权交回父组件） */
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

/** 任意键/点击：直接跳到 100 并抽走（保留转场观感，不是瞬间消失） */
function skip() {
  if (finished) return
  progress.value = 100
  stepIndex.value = 2
  finish()
}

onMounted(() => {
  if (reduce) {
    document.body.classList.add('ready')
    emit('done')
    return
  }

  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', skip)
  window.addEventListener('pointerdown', skip)
  // 安全网：任何异常都不能把用户锁在加载页
  safety = setTimeout(skip, 3400)

  /**
   * 时间来源与重绘时机**分开**（两次踩坑后的结论）：
   *   1. 曾用"每帧固定 +16ms"：帧率越高动画越快（headless 下 1.35s 就跑完，参考稿是 2.6s）
   *   2. 改用 rAF 回调的 timestamp 减 performance.now()：**两者时间原点不同**，读数出现 -33；
   *      而且 rAF 会被浏览器节流（实测无头下 3 秒只触发 7 次），进度直接卡住。
   * 正解：用 Date.now() 决定"过了多久"（单调、不受节流影响），
   * rAF 只负责重绘；并在每次重绘时夹紧 0..100，任何时间源异常都不会显示负数。
   */
  const t0 = Date.now()
  const step = () => {
    const p = Math.min(1, Math.max(0, (Date.now() - t0) / DUR))
    const e = 1 - Math.pow(1 - p, 3) // 缓出，与参考稿一致
    progress.value = Math.min(100, Math.max(0, e * 100))
    stepIndex.value = p < 0.34 ? 0 : p < 0.72 ? 1 : 2
    if (p < 1) raf = requestAnimationFrame(step)
    else setTimeout(finish, 160)
  }
  raf = requestAnimationFrame(step)
  // 兜底：即使 rAF 被完全节流，也用定时器继续推进（与安全网不同：它保证进度仍在走）
  tickTimer = setInterval(() => {
    if (!finished) step()
  }, 100)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  clearTimeout(hideTimer)
  clearTimeout(safety)
  clearInterval(tickTimer)
  window.removeEventListener('keydown', skip)
  window.removeEventListener('pointerdown', skip)
  document.body.style.overflow = ''
})
</script>

<template>
  <div
    v-if="!gone"
    class="loader"
    :class="{ done }"
    role="progressbar"
    :aria-valuenow="Math.round(progress)"
    aria-valuemin="0"
    aria-valuemax="100"
    aria-label="正在校准观测站"
  >
    <div class="left">
      <div class="mono brand">研错本 · 夜航星图</div>
      <div class="num">{{ readout }}</div>
    </div>

    <div class="steps mono" aria-hidden="true">
      <span v-for="(s, i) in STEPS" :key="s" :class="{ on: i === stepIndex }">{{ s }}</span>
    </div>
  </div>
</template>

<style scoped>
/* 整块面板：底部左右分布（左读数、右阶段），与参考稿一致 */
.loader {
  position: fixed;
  inset: 0;
  z-index: var(--z-loader);
  background: var(--sky-0);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  padding: var(--pad);
  /* 转场：整块向上抽走（参考稿的 ease2 用本项目的 settle 曲线） */
  transition: transform 1s var(--e-settle);
  cursor: pointer;
}
.loader.done {
  transform: translateY(-101%);
}

.left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.brand {
  color: var(--ink-2);
}
.num {
  font-family: var(--font-mono);
  font-weight: 300;
  font-size: clamp(2.6rem, 8vw, 7rem);
  line-height: 0.85;
  letter-spacing: -0.05em;
  color: var(--ink-0);
}

.steps {
  display: grid;
  gap: 6px;
  text-align: right;
}
.steps span {
  color: var(--ink-3);
  transition: color 0.35s var(--e-settle);
}
/* 当前阶段点亮：与参考稿的逐行点亮同义 */
.steps span.on {
  color: var(--ink-0);
}

@media (prefers-reduced-motion: reduce) {
  .loader {
    transition: none;
  }
}
</style>
