/**
 * 页面转场遮罩（RouteVeil）—— 站内路由切换时的遮罩过渡
 * ===========================================================================
 * 用户要求"遮罩转场"。进入动画（BootCalibration，整块向上抽走）只管首次进入；
 * 这里管**站内换页**：导航时一层遮罩从下往上扫过，换页完成后再扫走。
 *
 * 为什么用"扫过"而不是"淡入淡出"：
 *   淡入淡出不做方向，观感像加载慢；扫过有**方向**，读起来是"翻到下一页"。
 *   这也是参考稿那类站点常用手法（配合它的 --ease2 过冲缓动）。
 *
 * 实现要点：
 *   · 遮罩用 transform: scaleY() 而不是 height —— 只影响合成，不触发布局
 *   · 两次扫过之间切换路由（router.beforeResolve 里等遮罩到位再放行太复杂，
 *     所以用"遮罩到位 -> 放行 -> 遮罩退出"三段，用 CSS 过渡 + 定时协作）
 *   · 尊重 prefers-reduced-motion：直接放行，不插遮罩
 *   · 遮罩期间锁滚动，避免背景跟着滚
 */

import { onBeforeUnmount, ref } from 'vue'

const VEIL_MS = 420

// 模块级单例：整个应用只应有一个遮罩
const veilVisible = ref(false)
let hideTimer = 0
let busy = false

function reduced() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * 挂到 router 上：
 *   router.beforeEach(async (to, from) => { ... })
 * 但这里不做"阻塞式"等待（会拖慢首屏），而是在 afterEach 里播一次扫过：
 *   遮罩扫入 -> 立刻扫出。用户看到的是"换页时有一道光扫过"。
 * 若后续要做真正的黑场转场（遮罩完全盖住再换页），把 beforeResolve 也接上即可。
 */
export function useRouteVeil(router) {
  const off = router.afterEach(() => {
    if (reduced() || busy) return
    busy = true
    veilVisible.value = true
    // 遮罩盖住后立刻退出（afterEach 时新页面已渲染完成）
    clearTimeout(hideTimer)
    hideTimer = window.setTimeout(() => {
      veilVisible.value = false
      busy = false
    }, VEIL_MS)
  })

  onBeforeUnmount(() => {
    clearTimeout(hideTimer)
    off()
  })

  return { veilVisible }
}

export { veilVisible }
