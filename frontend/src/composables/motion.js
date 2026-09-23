/**
 * 动效层（motion）—— Lenis 平滑滚动 + GSAP 滚动叙事 + 磁吸 + 视差
 * ===========================================================================
 * 用户要求"除移动端外尽可能加入"：弹簧、惯性、阻尼、延迟、错峰、
 * 自定义光标、磁吸按钮、悬停变形、滚动叙事、视差、遮罩转场、逐字/逐行揭示。
 *
 * 本文件负责其中四项（滚动/磁吸/视差/揭示），光标单独在 ui/AppCursor.vue。
 *
 * 三条硬约束（全站统一，不遵守就会出问题）：
 *   1. **尊重 prefers-reduced-motion**：命中即全部关闭（返回 no-op），只保留静态呈现
 *   2. **只动 transform / opacity**：GSAP 用 x/y/scale/opacity，不用 width/top/left
 *   3. **可用性优先于炫技**：
 *      · Lenis 只在"内容比视口长"时启用；短页面不接管滚动
 *      · 不移除键盘滚动、不影响锚点跳转与滚动条
 *      · 触屏不启用（原生滚动在触屏上更顺；用户也明确说移动端不搞）
 *
 * 惰性加载：Lenis 与 GSAP 都是动态 import —— 首屏不为动效付出体积。
 */

let lenis = null
let gsapMod = null
let started = false

/**
 * 是否应该启用动效：尊重偏好 + 触屏不接管 + 有滚动空间。
 * 三个条件任一不满足就退化为原生行为。
 */
export function motionAllowed() {
  if (typeof window === 'undefined') return false
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  // 触屏不接管滚动（原生更顺，也避免与手势冲突）
  if (matchMedia('(pointer: coarse)').matches) return false
  return true
}

/** 动态拿到 gsap（只加载一次） */
async function loadGsap() {
  if (!gsapMod) {
    const mod = await import('gsap')
    gsapMod = mod.gsap || mod.default
  }
  return gsapMod
}

/**
 * 启动 Lenis 平滑滚动，并把它接到 GSAP 的 ticker 上。
 *
 * 为什么要接 ticker：Lenis 需要每帧更新；如果各用各的 rAF，
 * 滚动与滚动驱动的动画会差一帧，表现为"字与滚动不同步"的黏滞感。
 * 接进 GSAP ticker 后两者同帧，观感才跟手。
 */
export async function startSmoothScroll() {
  if (started || !motionAllowed()) return null
  const { default: Lenis } = await import('lenis')
  const gsap = await loadGsap()

  lenis = new Lenis({
    // 时长与曲线：0.9s 的指数缓出，接近"惯性滑行"而不是等速
    duration: 0.9,
    easing: (t) => 1 - Math.pow(1 - t, 3),
    smoothWheel: true,
    // 不接管触屏（已在 motionAllowed 里判过，这里再保险一次）
    syncTouch: false,
  })

  lenis.on('scroll', () => {
    if (gsapMod?.ScrollTrigger) gsapMod.ScrollTrigger.update()
  })
  gsap.ticker.add((time) => lenis.raf(time * 1000))
  gsap.ticker.lagSmoothing(0)

  started = true
  return lenis
}

export function stopSmoothScroll() {
  if (lenis) {
    lenis.destroy()
    lenis = null
  }
  started = false
}

/** 供锚点/程序化滚动使用（有 Lenis 时走它，观感一致；否则退回原生） */
export function scrollToTarget(target, opts = {}) {
  if (lenis) {
    lenis.scrollTo(target, { offset: -80, ...opts })
    return
  }
  const el = typeof target === 'string' ? document.querySelector(target) : target
  if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

/* ────────────────────────── 磁吸 ────────────────────────── */
/**
 * 磁吸：指针靠近时元素被"吸"过去，离开时用弹簧回位。
 * 位移上限 max（默认 18px）—— 不设上限会变成"跟着指针跑"，那不是磁吸。
 */
export function magnetic(el, { strength = 0.32, max = 18, scale = 1.03 } = {}) {
  if (!el || !motionAllowed()) return () => {}
  let raf = 0
  let tx = 0
  let ty = 0
  let cx = 0
  let cy = 0
  let hover = false

  const onMove = (e) => {
    const r = el.getBoundingClientRect()
    tx = Math.max(-max, Math.min(max, (e.clientX - r.left - r.width / 2) * strength))
    ty = Math.max(-max, Math.min(max, (e.clientY - r.top - r.height / 2) * strength))
  }
  const onEnter = () => {
    hover = true
  }
  const onLeave = () => {
    hover = false
    tx = 0
    ty = 0
  }
  // lerp 跟随 + 弹簧式回位（松手后按阻尼逼近 0）
  const loop = () => {
    const ease = hover ? 0.18 : 0.12
    cx += (tx - cx) * ease
    cy += (ty - cy) * ease
    const s = hover ? scale : 1
    el.style.transform = `translate3d(${cx.toFixed(2)}px, ${cy.toFixed(2)}px, 0) scale(${s})`
    raf = requestAnimationFrame(loop)
  }

  el.addEventListener('pointermove', onMove)
  el.addEventListener('pointerenter', onEnter)
  el.addEventListener('pointerleave', onLeave)
  raf = requestAnimationFrame(loop)

  return () => {
    cancelAnimationFrame(raf)
    el.removeEventListener('pointermove', onMove)
    el.removeEventListener('pointerenter', onEnter)
    el.removeEventListener('pointerleave', onLeave)
    el.style.transform = ''
  }
}

/* ────────────────────────── 滚动叙事 ────────────────────────── */
/**
 * 逐词/逐行揭示 + 视差，全部交给 GSAP ScrollTrigger。
 *
 * 选择器约定（写在模板上即可，不必在页面里写动画代码）：
 *   [data-reveal-words]  文本容器：内部的词组按滚动进度依次点亮
 *   [data-reveal-lines]  行容器：内部的 .line 依次位移揭示
 *   [data-parallax]      视差层：值越大位移越多
 *
 * 返回一个清理函数；组件卸载时必须调用，否则 ScrollTrigger 会泄漏。
 */
export async function bindScrollMotion(root) {
  if (!root || !motionAllowed()) return () => {}
  const gsap = await loadGsap()
  const { ScrollTrigger } = await import('gsap/ScrollTrigger')
  gsap.registerPlugin(ScrollTrigger)

  const ctx = gsap.context(() => {
    // 1) 逐词点亮：把容器的文本切成词块 span（中文按 1-4 字 + 标点边界）
    root.querySelectorAll('[data-reveal-words]').forEach((host) => {
      if (host.dataset.split === '1') return
      const raw = (host.textContent || '').trim()
      if (!raw) return
      const chunks = raw.match(/[^，。；、！？]{1,4}[，。；、！？]?/g) || [raw]
      host.textContent = ''
      const spans = chunks.map((c) => {
        const s = document.createElement('span')
        s.textContent = c
        s.style.display = 'inline-block'
        s.style.opacity = '0.12'
        s.style.willChange = 'opacity'
        host.appendChild(s)
        return s
      })
      host.dataset.split = '1'
      // 用 opacity 逐块点亮（只动 opacity，不触发布局）
      gsap.to(spans, {
        opacity: 1,
        ease: 'none',
        stagger: 0.06,
        scrollTrigger: {
          trigger: host,
          // 从"元素顶到视口 95%"到"顶到 35%" —— 首屏元素也留出可感知的滚动距离，
          // 否则 scrub 区间在元素进入视口时已经走完，看不到逐块点亮（实测踩过）
          start: 'top 95%',
          end: 'top 35%',
          scrub: true,
        },
      })
    })

    // 2) 逐行揭示：行内元素从下方顶上来（遮罩由 CSS overflow:hidden 提供）
    root.querySelectorAll('[data-reveal-lines]').forEach((host) => {
      let lines = host.querySelectorAll('.line, .line__i, [data-line]')

      // 没有预置行结构时（v2 的面板标题是纯文本），自动包一层：
      // 外层做遮罩、内层做位移 —— 与参考稿的 .line / .line__i 同构。
      // 不这么做的话 querySelectorAll 返回空集合，补间作用在空集合上，
      // 实测表现为"滚动到标题什么也没发生"。
      // 只对【纯文本】host 才自动包裹：host 里有元素子节点（如热力图的格子矩阵）时
      // textContent='' 会把整个组件 DOM 抹掉换成一行文字（真踩过，热力图因此消失）。
      if (
        !lines.length &&
        host.children.length === 0 &&
        host.textContent &&
        host.textContent.trim()
      ) {
        const raw = host.textContent.trim()
        host.textContent = ''
        host.style.overflow = 'hidden'
        const inner = document.createElement('span')
        inner.textContent = raw
        inner.style.display = 'block'
        host.appendChild(inner)
        lines = [inner]
        host.dataset.splitLines = '1'
      }
      if (!lines.length) return

      gsap.from(lines, {
        yPercent: 105,
        duration: 1.05,
        ease: 'power3.out',
        stagger: 0.09,
        scrollTrigger: { trigger: host, start: 'top 92%' },
      })
    })

    // 2.5) 图表生长：按滚动进度长出来（用户要求"全部加入"）
    //   条形用 scaleX、柱子用 scaleY、折线用 stroke-dashoffset —— 都只动合成属性，
    //   不碰 width/height（那会触发布局抖动）。
    root.querySelectorAll('[data-grow]').forEach((host) => {
      const kind = host.dataset.grow
      const trigger = {
        trigger: host,
        start: 'top 96%',
        end: 'top 40%',
        scrub: 0.6,
      }

      if (kind === 'bars') {
        // 只选真正的"条"：v2 里条都写成 <i>。之前用宽选择器（i, .w-bar i, span[style]）
        // 会把图例色块也算进来，缩放后出现莫名其妙的空白。
        const bars = host.querySelectorAll('i')
        if (!bars.length) return
        gsap.set(bars, { transformOrigin: 'left center' })
        // 用 fromTo 而不是 from：from 在元素已进入触发区时会立刻应用起始值，
        // 若 scrub 进度已是 1 就**永远停在 scaleX(0)**（实测过的 bug）。
        gsap.fromTo(
          bars,
          { scaleX: 0 },
          { scaleX: 1, ease: 'none', stagger: 0.05, scrollTrigger: trigger },
        )
        return
      }

      if (kind === 'steps') {
        const cols = host.querySelectorAll(':scope > *')
        if (!cols.length) return
        gsap.set(cols, { transformOrigin: 'bottom center' })
        gsap.fromTo(
          cols,
          { scaleY: 0 },
          { scaleY: 1, ease: 'none', stagger: 0.06, scrollTrigger: trigger },
        )
        return
      }

      if (kind === 'chart') {
        const paths = host.querySelectorAll('path, polyline, line')
        const dots = host.querySelectorAll('circle')
        paths.forEach((el) => {
          // 用 let + try 包住：某些浏览器对不可见 SVG 调 getTotalLength 会抛错
          let len
          try {
            len = el.getTotalLength ? el.getTotalLength() : 0
          } catch {
            len = 0
          }
          if (!len) return
          gsap.set(el, { strokeDasharray: len, strokeDashoffset: len })
          gsap.to(el, { strokeDashoffset: 0, ease: 'none', scrollTrigger: trigger })
        })
        if (dots.length) {
          gsap.from(dots, {
            opacity: 0,
            scale: 0.6,
            ease: 'none',
            stagger: 0.04,
            scrollTrigger: trigger,
          })
        }
        return
      }

      if (kind === 'ring') {
        const arc = host.querySelector('circle')
        if (!arc) return
        const r = arc.r?.baseVal?.value || 0
        const len = 2 * Math.PI * r
        if (!len) return
        gsap.set(arc, { strokeDasharray: len, strokeDashoffset: len })
        gsap.to(arc, { strokeDashoffset: 0, ease: 'none', scrollTrigger: trigger })
      }
    })

    // 3) 视差：按 data-parallax 的值决定位移幅度（默认 60px）
    root.querySelectorAll('[data-parallax]').forEach((el) => {
      const amount = Number(el.dataset.parallax) || 60
      gsap.fromTo(
        el,
        { y: amount * 0.5 },
        {
          y: -amount * 0.5,
          ease: 'none',
          scrollTrigger: { trigger: el, start: 'top bottom', end: 'bottom top', scrub: true },
        },
      )
    })
  }, root)

  return () => ctx.revert()
}
