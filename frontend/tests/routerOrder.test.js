/**
 * NAV_ORDER 与真实路由名的一致性。
 *
 * 钉住的理由写在 router/index.js 的注释里：navIndexOf() 对**不认识**的名字返回数组长度，
 * 于是"任意两页都算同一个编号"，换页方向恒为 prev —— 第一版就是因为表里写了
 * home / mistakes / papers 这类根本不存在的路由名而翻过车，而三道具检页
 * （integrity / snapshots / design）都是**手工在两处各写一遍**（路由表 + NAV_ORDER），
 * 漂了不会红。这里把它钉成一条断言。
 */
import { describe, expect, it } from 'vitest'

import router, { NAV_ORDER, navIndexOf } from '../src/router'

const routeNames = new Set()
for (const r of router.options.routes) {
  for (const c of r.children || []) if (c.name) routeNames.add(c.name)
}

describe('NAV_ORDER 必须与真实路由名一致', () => {
  it('表里每个名字都能在路由表里找到（写错名字不会红，只会让翻页方向永远算错）', () => {
    expect(routeNames.size).toBeGreaterThan(10)
    expect(NAV_ORDER.filter((n) => !routeNames.has(n))).toEqual([])
  })

  it('每个带名字的页面都在表里排了序（新增页面漏登记 = 方向按"最后"算）', () => {
    const missing = [...routeNames].filter((n) => !NAV_ORDER.includes(n))
    expect(missing).toEqual([])
  })

  it('名字不重复，且维护页排在日常页之后（顺序就是"左右"的定义）', () => {
    expect(new Set(NAV_ORDER).size).toBe(NAV_ORDER.length)
    expect(NAV_ORDER.indexOf('data-snapshots')).toBeGreaterThan(NAV_ORDER.indexOf('stats'))
    expect(NAV_ORDER.indexOf('data-integrity')).toBeLessThan(NAV_ORDER.indexOf('data-snapshots'))
  })

  it('未知名字仍然排到最后（保留旧兜底语义，不许变成 -1 混进比较）', () => {
    expect(navIndexOf('no-such-route')).toBe(NAV_ORDER.length)
    expect(navIndexOf('stats')).toBe(0)
  })

  it('未知路径落到 404 兜底路由（没有 catch-all 时未知路径渲染成空白外壳）', () => {
    expect(router.resolve('/no/such/page').name).toBe('not-found')
  })
})
