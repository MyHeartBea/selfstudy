/**
 * 动效原语单测
 *
 * 重点是**入参守卫**：本项目的真实事故是把非元素（组件实例代理 / null / 字符串）
 * 传进原语，抛 `el.addEventListener is not a function`，异常发生在 onMounted 内部，
 * 导致同一钩子里后面的原语全部不执行 —— 表现为"元素永远不出现"，极难排查。
 * 所以这里把每个原语的非法入参都钉死：必须静默跳过、返回可调用的清理函数、不抛异常。
 */
import { describe, expect, it, vi } from 'vitest'

import {
  CURVE,
  focusRing,
  isElement,
  magnetic,
  parallax,
  prefersReduced,
  revealAll,
  revealOnScroll,
  scanGuard,
  traceOnScroll,
} from '../src/design/motion'

const BAD_INPUTS = [null, undefined, 'div', 42, {}, { nodeType: 1 }]

describe('isElement 守卫', () => {
  it('只接受真正的元素', () => {
    expect(isElement(document.createElement('div'))).toBe(true)
    BAD_INPUTS.forEach((bad) => expect(isElement(bad)).toBe(false))
  })

  it('是对象但没有 addEventListener 时判定为 false（组件实例代理就是这种）', () => {
    expect(isElement({ nodeType: 1, style: {} })).toBe(false)
  })
})

describe('原语对非法入参必须静默跳过', () => {
  it('revealOnScroll：返回可调用清理函数且不抛', () => {
    BAD_INPUTS.forEach((bad) => {
      const stop = revealOnScroll(bad)
      expect(typeof stop).toBe('function')
      expect(() => stop()).not.toThrow()
    })
  })

  it('revealAll：过滤掉非法项，只处理元素', () => {
    const good = document.createElement('div')
    const stop = revealAll([null, good, {}, 'x'])
    expect(typeof stop).toBe('function')
    expect(() => stop()).not.toThrow()
  })

  it('magnetic / parallax：不抛且清理安全', () => {
    BAD_INPUTS.forEach((bad) => {
      expect(() => magnetic(bad)()).not.toThrow()
      expect(() => parallax(bad)()).not.toThrow()
    })
  })

  it('traceOnScroll：无 host 或无路径时不抛', () => {
    BAD_INPUTS.forEach((bad) => {
      expect(() => traceOnScroll(bad)()).not.toThrow()
    })
    const empty = document.createElement('div')
    expect(() => traceOnScroll(empty)()).not.toThrow()
  })

  it('focusRing / scanGuard：不抛', () => {
    BAD_INPUTS.forEach((bad) => {
      expect(() => focusRing(bad)).not.toThrow()
      expect(() => scanGuard(bad)).not.toThrow()
    })
  })
})

describe('原语对合法元素的正常行为', () => {
  it('revealOnScroll 在无 IntersectionObserver 时直接加 .in（降级不丢内容）', () => {
    const el = document.createElement('div')
    const original = globalThis.IntersectionObserver
    // 模拟不支持观察器的环境
    delete globalThis.IntersectionObserver
    try {
      const stop = revealOnScroll(el)
      expect(el.classList.contains('in')).toBe(true)
      expect(() => stop()).not.toThrow()
    } finally {
      globalThis.IntersectionObserver = original
    }
  })

  it('magnetic 在悬停不可用的环境下不绑定监听（触屏/无 hover）', () => {
    const el = document.createElement('div')
    // 不能依赖 happy-dom 默认值：它对任意查询都返回 matches:true。这里显式模拟触屏环境。
    const original = window.matchMedia
    window.matchMedia = (q) => ({
      matches: false,
      media: q,
      addEventListener() {},
      removeEventListener() {},
    })
    const addSpy = vi.spyOn(el, 'addEventListener')
    try {
      const stop = magnetic(el)
      expect(addSpy).not.toHaveBeenCalled()
      expect(() => stop()).not.toThrow()
    } finally {
      addSpy.mockRestore()
      window.matchMedia = original
    }
  })
})

describe('契约常量', () => {
  it('三条曲线与 tokens.css 的变量语义一致（名称固定）', () => {
    expect(Object.keys(CURVE).sort()).toEqual(['drift', 'flare', 'settle'])
    Object.values(CURVE).forEach((v) => expect(v.startsWith('cubic-bezier(')).toBe(true))
  })

  it('prefersReduced 返回布尔值', () => {
    expect(typeof prefersReduced()).toBe('boolean')
  })
})
