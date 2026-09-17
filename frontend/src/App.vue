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
    页面内容转场：不遮盖，让新页面自己推上来。
      · mode="out-in"：旧页面走完再上新页面，避免两层内容叠在一起
      · 时长刻意做短（进 320ms / 出 180ms）——站内换页要"利落"，
        超过 400ms 就会被感觉成"卡"
      · 只动 opacity / transform
  -->
  <RouterView v-slot="{ Component, route }">
    <Transition name="km-page" mode="out-in">
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
.km-page-enter-active {
  transition:
    opacity 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.42s cubic-bezier(0.22, 1, 0.36, 1);
}
.km-page-leave-active {
  /* 出场更快：旧内容不该占着时间 */
  transition:
    opacity 0.18s ease,
    transform 0.22s ease;
}
.km-page-enter-from {
  opacity: 0;
  transform: translateY(18px);
}
.km-page-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 减弱动效：不做转场，直接切换 */
@media (prefers-reduced-motion: reduce) {
  .km-page-enter-active,
  .km-page-leave-active {
    transition: none;
  }
  .km-page-enter-from,
  .km-page-leave-to {
    opacity: 1;
    transform: none;
  }
}
</style>
