/**
 * 换页幕布时序（routeVeil.js）
 * ===========================================================================
 * 上一版的问题：幕布在 afterEach 里播"扫一下"，两段方向不一致、且中间露出一帧
 * 新页面 —— 用户说"换页动画太丑"。

 * 改成**覆盖式**转场（用户看不到换页那一帧）：
 *   ① 导航开始 -> 幕布从下方移入盖住（等 300ms，略短于动画 340ms，
 *      让幕布"几乎到位"就放行，避免体感迟滞）
 *   ② 放行导航 -> 换页在幕布后面发生
 *   ③ 导航完成 -> 幕布继续向上移出
 *
 * 关键取舍：为什么在 beforeEach 里就 await？
 *   不 await 的话换页会发生在幕布到达之前，用户会看到新页面闪一下
 *   （这正是上一版"丑"的原因之一）。await 的代价是每次换页多约 300ms，
 *   但换来的是"干净的覆盖"。为了不让它显得迟钝，幕布的入场做成 340ms 且
 *   缓出曲线前段很快 —— 体感上只有"一瞬的黑"。
 *
 * 尊重 prefers-reduced-motion：直接放行，不插幕布。
 */

import { onBeforeUnmount, ref } from 'vue'

// 幕布盖住所需时间（略短于 CSS 的 340ms，让放行时幕布已基本到位）
const COVER_MS = 300
// 幕布离场动画时长（与 CSS 的 420ms 对齐）
const REVEAL_MS = 430

/** 'idle' | 'cover' | 'reveal' —— 模块级单例：全应用只有一个幕布 */
export const veilPhase = ref('idle')

function reduced() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export function useRouteVeil(router) {
  let busy = false
  let revealTimer = 0

  const offBefore = router.beforeEach(async (to, from) => {
    // 同页跳转（只改 query/hash）不插幕布，否则筛选操作会一直闪
    if (to.path === from.path) return true
    if (reduced() || busy || !from.name) return true

    busy = true
    veilPhase.value = 'cover'
    await sleep(COVER_MS)
    return true
  })

  const offAfter = router.afterEach(() => {
    if (veilPhase.value !== 'cover') return
    // 换页已在幕布后完成，让幕布继续向上离场
    veilPhase.value = 'reveal'
    clearTimeout(revealTimer)
    revealTimer = window.setTimeout(() => {
      veilPhase.value = 'idle'
      busy = false
    }, REVEAL_MS)
  })

  const offError = router.onError(() => {
    // 导航失败绝不能把用户留在幕布后面
    veilPhase.value = 'idle'
    busy = false
    clearTimeout(revealTimer)
  })

  onBeforeUnmount(() => {
    clearTimeout(revealTimer)
    offBefore()
    offAfter()
    offError()
  })

  return { veilPhase }
}
