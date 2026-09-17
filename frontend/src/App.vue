<script setup>
/**
 * 根组件：主题恢复 + 全局宿主 + 进入动画 + 站内换页遮罩 + 动效层
 *
 * 动效层（用户要求"除移动端外尽可能加入"）：
 *   · Lenis 平滑滚动 + GSAP 滚动叙事（composables/motion.js）
 *   · 自定义光标（ui/AppCursor.vue）—— 挂载成功才隐藏原生指针（安全网）
 *   · 全局磁吸：带 data-magnetic 的元素自动获得
 *   · 噪点层（composables/grain.js）
 *   · 站内换页遮罩（ui/RouteVeil.vue + composables/routeVeil.js）
 *
 * 两种转场的分工：
 *   · BootCalibration：首次进入/刷新 —— 整块向上抽走
 *   · RouteVeil：站内换页 —— 一道遮罩扫过
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import ToastHost from './ui/ToastHost.vue'
import ConfirmHost from './ui/ConfirmHost.vue'
import BootCalibration from './ui/BootCalibration.vue'
import AppCursor from './ui/AppCursor.vue'
import RouteVeil from './ui/RouteVeil.vue'
import { useRouter } from 'vue-router'
import {
  bindScrollMotion,
  magnetic,
  startSmoothScroll,
  stopSmoothScroll,
} from './composables/motion'
import { useGrain } from './composables/grain'
import { useRouteVeil } from './composables/routeVeil'
import { startLiveHover } from './composables/kmLive'

// 噪点层：纯色底加材料感（学自参考稿的 feTurbulence + steps 位移）
useGrain()

const booting = ref(true)
const router = useRouter()
// 站内换页遮罩
const { veilVisible } = useRouteVeil(router)

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
  <router-view />
  <ToastHost />
  <ConfirmHost />
  <AppCursor />
  <RouteVeil :visible="veilVisible" />
  <BootCalibration v-if="booting" @done="onBootDone" />
</template>
