<script setup>
/**
 * 根组件：主题恢复 + 全局宿主 + 进入动画 + 页面内容转场 + 动效层
 *
 * 转场策略（换过一次做法，记录原因）：
 *   第一版：换页时插一层"幕布"扫过 —— 用户两次反馈"丑"。
 *   问题不在幕布的实现，而在**做法本身**：
 *     · 用户点导航后先被一层实色盖住，主观上像"卡了一下"
 *     · 幕布上还放了"载入"文案与转圈标记，等于把内部加载状态暴露给用户
 *     · 站内换页本来就是瞬时的，加遮盖是**给自己制造等待**
 *
 *   改为**内容自身入场**（不遮盖）：
 *     旧页面快速淡出上移 -> 新页面淡入并上移到位。
 *     用户看到的是"新内容推上来"，而不是"一张纸盖住再掀开"。
 *
 * 动效层（用户要求"除移动端外尽可能加入"）：
 *   · Lenis 平滑滚动 + GSAP 滚动叙事（composables/motion.js）
 *   · 自定义光标（ui/AppCursor.vue）—— 挂载成功才隐藏原生指针（安全网）
 *   · 全局磁吸：带 data-magnetic 的元素自动获得
 *   · 噪点层（composables/grain.js）
 *   · 悬停复合特效：km-live.css + kmLive.js（事件委托，全站一次）
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import ToastHost from './ui/ToastHost.vue'
import ConfirmHost from './ui/ConfirmHost.vue'
import BootCalibration from './ui/BootCalibration.vue'
import AppCursor from './ui/AppCursor.vue'
import { useRouter } from 'vue-router'
import { navIndexOf } from './router'
import {
  bindScrollMotion,
  magnetic,
  startSmoothScroll,
  stopSmoothScroll,
} from './composables/motion'
import { useGrain } from './composables/grain'
import { startLiveHover } from './composables/kmLive'

// 噪点层：纯色底加材料感（学自参考稿的 feTurbulence + steps 位移）
useGrain()

const booting = ref(true)
const router = useRouter()

/**
 * 换页方向：'right' 表示新页在当前页右边（当前页向左滑出）。
 * 由导航顺序（NAV_ORDER）决定 —— 见 router/index.js 的注释。
 */
const pageDir = ref('next')
router.beforeEach((to, from) => {
  if (!from.name) return true
  // 注意方向语义：next 表示"新页在当前页右边"。
  // 实测发现第一版方向反了 —— 所以这里用 `>` 取 next，`<=` 取 prev。
  pageDir.value = navIndexOf(to.name) > navIndexOf(from.name) ? 'next' : 'prev'
  return true
})

let magnets = []
let unbindScroll = null
let stopLive = null

onMounted(async () => {
  const saved = localStorage.getItem('km-theme')
  if (saved === 'dark') {
    document.documentElement.dataset.theme = 'dark'
  }
  // 平滑滚动与 GSAP 都是动态 import：首屏不为动效付出体积
  await startSmoothScroll()
  document.querySelectorAll('[data-magnetic]').forEach((el) => {
    magnets.push(magnetic(el))
  })
  await bindMotion()
  // 悬停复合特效的指针追踪（事件委托，全站一次）
  stopLive = startLiveHover()
})

/**
 * 绑定滚动叙事/视差。
 * 必须在**视图挂载之后**执行：ScrollTrigger 依赖真实 DOM，
 * 早于视图渲染会找不到标记（实测出过 wordSpans = 0）。
 */
async function bindMotion() {
  if (unbindScroll) {
    unbindScroll()
    unbindScroll = null
  }
  await nextTick()
  unbindScroll = await bindScrollMotion(document.body)
}

onBeforeUnmount(() => {
  magnets.forEach((fn) => fn())
  magnets = []
  if (unbindScroll) unbindScroll()
  if (stopLive) stopLive()
  stopSmoothScroll()
})

router.afterEach(async () => {
  document.querySelectorAll('[data-magnetic]').forEach((el) => {
    magnets.push(magnetic(el))
  })
  await bindMotion()
})

function onBootDone() {
  booting.value = false
}
</script>

<template>
  <!--
    页面内容转场：3D 翻书（方向由 NAV_ORDER 决定）。
      · **刻意不用 mode="out-in"**：翻书需要两页同时存在 ——
        一页绕书脊转走、另一页在下面显露。
        用 out-in 时旧页先淡到全黑、新页才进，中间那一帧就是"黑屏"
        （这是用户实测反馈过的问题）。
      · 只动 transform / opacity / filter
  -->
  <RouterView v-slot="{ Component, route }">
    <!-- 不用 mode="out-in"：翻书需要两页同时存在（一页转走、另一页露出） -->
    <Transition :name="`km-flip-${pageDir}`">
      <component :is="Component" :key="route.path" />
    </Transition>
  </RouterView>
  <ToastHost />
  <ConfirmHost />
  <AppCursor />
  <BootCalibration v-if="booting" @done="onBootDone" />
</template>

<style>
/* 全局（不能用 scoped：Transition 的类名要作用在根元素上） */
/*
  换页动画：**3D 翻书**
  ---------------------------------------------------------------------------
  上一版的两个问题（用户实测反馈）：
    1) 方向反了 —— 已在 beforeEach 里反过来（见脚本注释）
    2) "单纯的黑屏，没有翻书感" —— 根因是用了 mode="out-in"：
       旧页先淡出到 opacity:0、新页才进，中间那段屏幕上什么都没有 = 黑屏；
       而且逐一进出根本不可能产生翻书观感，因为翻书的关键是**两页同时存在**：
       一页转走，另一页在下面露出来。

  这一版的要点：
    · 两页**同时**存在（去掉 out-in）
    · 离开的那页绕**书脊**（左/右边缘）做 rotateY 转走，并轻微暗化 —— 像纸被翻过去
    · 进入的那页在下方**轻微反向**起手，转走的那页掀开后它正好显露
    · 容器加 perspective，否则 rotateY 只会把页面压扁，没有立体感
    · backface-visibility: hidden 避免旋转过 90° 后出现镜像内容
*/
/* 每一页都带自己的透视（无需外层容器，避免破坏既有布局） */
.km-flip-next-leave-active,
.km-flip-next-enter-active,
.km-flip-prev-leave-active,
.km-flip-prev-enter-active {
  will-change: transform, opacity;
  backface-visibility: hidden;
}

/* ── 往右翻（新页在右侧）：当前页绕**左边缘**（书脊）向左转走 ────────── */
.km-flip-next-leave-active {
  position: relative;
  z-index: 2;
  transform-origin: left center;
  transform: perspective(1800px) rotateY(0deg);
  transition:
    transform 0.62s cubic-bezier(0.42, 0, 0.24, 1),
    opacity 0.62s linear,
    filter 0.62s linear;
}
.km-flip-next-leave-to {
  transform: perspective(1800px) rotateY(-96deg) translateZ(0);
  opacity: 0.35;
  filter: brightness(0.55);
}
/* 新页在下面：轻微反向起手，掀开后显露 */
.km-flip-next-enter-active {
  position: relative;
  z-index: 1;
  transform-origin: right center;
  transition:
    transform 0.62s cubic-bezier(0.42, 0, 0.24, 1),
    opacity 0.4s ease-out;
}
.km-flip-next-enter-from {
  opacity: 0.25;
  transform: perspective(1800px) rotateY(12deg) scale(0.985);
}

/* ── 往左翻（新页在左侧）：镜像 —— 当前页绕**右边缘**向右转走 ────────── */
.km-flip-prev-leave-active {
  position: relative;
  z-index: 2;
  transform-origin: right center;
  transform: perspective(1800px) rotateY(0deg);
  transition:
    transform 0.62s cubic-bezier(0.42, 0, 0.24, 1),
    opacity 0.62s linear,
    filter 0.62s linear;
}
.km-flip-prev-leave-to {
  transform: perspective(1800px) rotateY(96deg) translateZ(0);
  opacity: 0.35;
  filter: brightness(0.55);
}
.km-flip-prev-enter-active {
  position: relative;
  z-index: 1;
  transform-origin: left center;
  transition:
    transform 0.62s cubic-bezier(0.42, 0, 0.24, 1),
    opacity 0.4s ease-out;
}
.km-flip-prev-enter-from {
  opacity: 0.25;
  transform: perspective(1800px) rotateY(-12deg) scale(0.985);
}

/* 减弱动效：不做转场，直接切换 */
@media (prefers-reduced-motion: reduce) {
  .km-flip-next-leave-active,
  .km-flip-next-enter-active,
  .km-flip-prev-leave-active,
  .km-flip-prev-enter-active {
    transition: none;
  }
  .km-flip-next-enter-from,
  .km-flip-prev-enter-from {
    opacity: 1;
    transform: none;
  }
  .km-flip-next-leave-to,
  .km-flip-prev-leave-to {
    opacity: 0;
    transform: none;
  }
}
</style>
