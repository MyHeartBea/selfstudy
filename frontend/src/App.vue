<script setup>
/**
 * 根组件：主题恢复 + 全局 Toast / Confirm 宿主 + 进入动画 + 动效层
 *
 * 动效层（用户要求"除移动端外尽可能加入"）：
 *   · Lenis 平滑滚动 + GSAP 滚动叙事：由 composables/motion.js 提供，
 *     在这里启动一次（全局）；页面只需在模板上写 data-* 标记
 *   · 自定义光标：ui/AppCursor.vue（**不移除原生光标**；触屏/减弱动效时自动关闭）
 *   · 全局磁吸：任何带 data-magnetic 的元素自动获得磁吸，组件内不必写代码
 *
 * 进入动画的播放时机（踩过一个坑后的定论）：
 *   · **刷新 / 首次打开** -> 要播（用户要的就是"网页进入动画"）
 *   · **站内路由切换**  -> 不播（否则每次点导航都挡一下）
 *   module 变量恰好符合这个语义：刷新时 JS 重新执行 -> 重置（会播）；
 *   站内切路由模块不重新执行 -> 保持（不播）。
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

const booting = ref(true)
const router = useRouter()
let magnets = []
let unbindScroll = null

onMounted(async () => {
  const saved = localStorage.getItem('km-theme')
  if (saved === 'dark') {
    document.documentElement.dataset.theme = 'dark'
  }
  // 平滑滚动与 GSAP 都是动态 import：首屏不为动效付出体积
  await startSmoothScroll()
  // 全局磁吸：带 data-magnetic 的元素自动获得磁吸
  document.querySelectorAll('[data-magnetic]').forEach((el) => {
    magnets.push(magnetic(el))
  })
  await bindMotion()
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
  <BootCalibration v-if="booting" @done="onBootDone" />
</template>
