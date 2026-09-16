/**
 * usePageMotion —— 页面级动效统一入口
 * ---------------------------------------------------------------------------
 * 为什么需要它（实测问题）：
 *   六条动效原语写好了，但只有规格页与统计页在用；复习/录入/错题/知识/生词/公式
 *   六个页面是 **0 处**滚动动效 —— 表现为"点进去之后没有动态滑动效果"。
 *   根因不是原语不好用，而是每页都要自己写 onMounted + 选择器 + 清理，成本太高就容易漏。
 *
 * 这一层把"页面该有的动效"变成一行调用：
 *   - 自动拾取容器内所有 `[data-reveal]` 元素，按 DOM 顺序错峰入场
 *   - 自动为容器挂上 `data-parallax` 的背景层加视差（可选）
 *   - 自动清理（卸载时断开所有观察器与 rAF）
 *   - `prefers-reduced-motion` 下**由原语内部直接加 .in**，所以内容一定可见
 *
 * 用法（vue）：
 *   const page = ref(null)
 *   usePageMotion(page, { stagger: 55 })
 *   <main ref="page"> <section data-reveal> ... </section> </main>
 */
import { onBeforeUnmount, onMounted } from 'vue'

import {
  isElement,
  magnetic,
  parallax,
  prefersReduced,
  revealOnScroll,
  traceOnScroll,
} from './motion'

/**
 * @param {import('vue').Ref<HTMLElement|null>} rootRef 页面根元素 ref
 * @param {{stagger?: number, threshold?: number, parallaxDepth?: number, magnetSelector?: string, traceSelector?: string}} opts
 * @returns {() => void} 手动重扫（内容异步加载后调用，例如列表接口返回后）
 */
export function usePageMotion(rootRef, opts = {}) {
  const {
    stagger = 55,
    threshold = 0.12,
    parallaxDepth = 10,
    magnetSelector = '[data-magnet]',
    traceSelector = '[data-trace]',
  } = opts

  /** 已处理过的元素，避免重复观察（WeakSet 不阻止回收） */
  const seen = new WeakSet()
  let stops = []
  let observer = null
  let rescanTimer = 0

  function cleanup() {
    stops.forEach((fn) => {
      if (typeof fn === 'function') fn()
    })
    stops = []
    clearTimeout(rescanTimer)
    if (observer) {
      observer.disconnect()
      observer = null
    }
  }

  /** 重新扫描（异步内容渲染后调用） */
  function scan() {
    const root = rootRef?.value
    if (!isElement(root)) return

    // 1) 错峰入场：按 DOM 顺序给 delay，逐个观察
    const reveals = root.querySelectorAll('[data-reveal]')
    let i = 0
    reveals.forEach((el) => {
      if (seen.has(el)) return
      seen.add(el)
      if (!prefersReduced()) {
        el.style.transitionDelay = `${Math.min(i, 16) * stagger}ms`
      }
      i += 1
      stops.push(revealOnScroll(el, { threshold }))
    })

    // 2) 背景层视差（装饰性元素才加，正文元素不要加，否则读起来晃）
    if (parallaxDepth > 0) {
      root.querySelectorAll('[data-parallax]').forEach((el) => {
        if (seen.has(el)) return
        seen.add(el)
        stops.push(parallax(el, { depth: Number(el.dataset.parallax) || parallaxDepth }))
      })
    }

    // 3) 磁吸（显式标注的元素才吸，避免到处都是浮动按钮）
    root.querySelectorAll(magnetSelector).forEach((el) => {
      if (seen.has(el)) return
      seen.add(el)
      stops.push(magnetic(el))
    })

    // 4) 描绘：SVG 路径按真实长度写出
    root.querySelectorAll(traceSelector).forEach((el) => {
      if (seen.has(el)) return
      seen.add(el)
      stops.push(traceOnScroll(el))
    })
  }

  onMounted(() => {
    scan()
    // 懒加载分块与图片可能稍后才撑开布局，观察器对后来的元素无效，所以再扫一次
    requestAnimationFrame(() => requestAnimationFrame(scan))

    // 关键补强：`data-reveal` 元素常常在 v-if 之后才挂载（骨架屏 - 数据到达）。
    // 初次扫描会全部漏掉，表现为"列表出来了但没有任何滚动动效"。
    // 用 MutationObserver 监听子节点变化并防抖重扫 —— seen 保证不会重复处理。
    const root = rootRef?.value
    if (isElement(root) && 'MutationObserver' in window) {
      observer = new MutationObserver(() => {
        clearTimeout(rescanTimer)
        rescanTimer = setTimeout(scan, 60)
      })
      observer.observe(root, { childList: true, subtree: true })
    }
  })
  onBeforeUnmount(cleanup)

  return scan
}
