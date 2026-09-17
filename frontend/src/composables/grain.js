/**
 * 颗粒噪点层（Grain）—— 学自参考稿
 * ===========================================================================
 * 参考稿里最"廉价但有效"的一招：一层 SVG feTurbulence 生成的噪点，
 * 用 steps() 让它每隔几帧跳一次位移（模拟胶片颗粒的随机抖动，而不是平滑滚动）。
 *
 * 为什么值得加：
 *   · 纯色/渐变底在暗场里会显得"平、廉价、像 PPT 背景"
 *   · 噪点加上去立刻有"材料感"，而成本是一个 SVG data-URI（约 400 字节）+ 一次合成
 *   · steps() 而不是 linear：颗粒应该**跳**，平滑移动会变成"雾在飘"，不像颗粒
 *
 * 两个实现细节（参考稿的做法，照学）：
 *   · 容器 inset 用负值（-120px），位移时不会露出边缘
 *   · opacity 压到 0.04 上下；高了会显脏，低了看不见
 */

import { onBeforeUnmount, onMounted } from 'vue'

/** SVG feTurbulence 噪点（data-URI，不引外部图片） */
const NOISE =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E" +
  "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.82' numOctaves='3' stitchTiles='stitch'/%3E" +
  "%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)'/%3E%3C/svg%3E"

let el = null

/** 挂载颗粒层（幂等：重复挂载只会有一层） */
export function mountGrain() {
  if (typeof document === 'undefined' || el) return
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return

  el = document.createElement('div')
  el.className = 'km-grain'
  el.setAttribute('aria-hidden', 'true')
  // 用内联样式而不是全局 CSS：这个组件自包含，不污染 v2 的 base.css
  Object.assign(el.style, {
    position: 'fixed',
    inset: '-120px',
    zIndex: '9000',
    pointerEvents: 'none',
    opacity: '0.042',
    backgroundImage: `url("${NOISE}")`,
  })
  document.body.appendChild(el)
  el.animate(
    [
      { transform: 'translate(0,0)' },
      { transform: 'translate(-30px,10px)' },
      { transform: 'translate(20px,-25px)' },
      { transform: 'translate(-15px,25px)' },
      { transform: 'translate(25px,15px)' },
      { transform: 'translate(0,0)' },
    ],
    // steps(6)：颗粒要"跳"，不是平滑滑动
    { duration: 6000, iterations: Infinity, easing: 'steps(6)' },
  )
}

export function unmountGrain() {
  if (el) {
    el.remove()
    el = null
  }
}

/** 组合式：在组件里一行挂上，卸载自动清理 */
export function useGrain() {
  onMounted(mountGrain)
  onBeforeUnmount(unmountGrain)
}
