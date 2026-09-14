/**
 * E2E 公共夹具：API 打桩 + 真实 PNG 构造 + 真实粘贴事件。
 *
 * 设计原则：**不启动后端**。所有 /api/** 都在浏览器层拦截并返回项目统一的
 * `{code, data, message}` 结构，所以这些用例在任何机器上都能跑，也不会碰到真实数据。
 */
import { test, expect } from '@playwright/test'
import zlib from 'node:zlib'

export { test, expect }

/** 项目统一响应包（与后端 app.responses.ok 一致，默认 message 也是 'success'）。 */
export function ok(data, message = 'success') {
  return { code: 200, data, message }
}

/**
 * CRC32（PNG 分块校验用）。
 *
 * 不用 `zlib.crc32`：那是 Node ≥20.15 才有的 API（22.2.0 才回移到 22.x），
 * 而 package.json 没有 engines 约束 —— 本机 Node 18/早期 20 会直接
 * `TypeError: zlib.crc32 is not a function`。手搓一张查表实现（15 行）彻底免掉这个版本坑。
 */
const CRC_TABLE = (() => {
  const table = new Int32Array(256)
  for (let n = 0; n < 256; n += 1) {
    let c = n
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[n] = c
  }
  return table
})()

function crc32(buf) {
  let c = 0xffffffff
  for (let i = 0; i < buf.length; i += 1) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

/** 造一张合法的最小 PNG（纯 zlib 手搓，不依赖任何图形库）。 */
export function tinyPng({ w = 8, h = 8, rgb = [255, 255, 255] } = {}) {
  const chunk = (tag, data) => {
    const len = Buffer.alloc(4)
    len.writeUInt32BE(data.length)
    const body = Buffer.concat([Buffer.from(tag, 'ascii'), data])
    const crc = Buffer.alloc(4)
    crc.writeUInt32BE(crc32(body))
    return Buffer.concat([len, body, crc])
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(w, 0)
  ihdr.writeUInt32BE(h, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 2 // truecolor
  // 每行前面一个 filter 字节 0，随后每像素 3 字节
  const raw = Buffer.concat(
    Array.from({ length: h }, () =>
      Buffer.concat([
        Buffer.from([0]),
        Buffer.concat(Array.from({ length: w }, () => Buffer.from(rgb))),
      ]),
    ),
  )
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

/**
 * 在页面里真实派发一次 `paste` 事件（带一张图片），走的是组件真正的 onPaste 分支。
 * 单元测试只能手搓事件对象，这里用的是浏览器原生 ClipboardEvent + DataTransfer。
 */
export async function pasteImage(page, { name = 'shot.png', rgb = [255, 255, 255] } = {}) {
  const b64 = tinyPng({ rgb }).toString('base64')
  await page.evaluate(
    async ({ b64, name }) => {
      const bin = atob(b64)
      const bytes = new Uint8Array(bin.length)
      for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i)
      const file = new File([bytes], name, { type: 'image/png' })
      const dt = new DataTransfer()
      dt.items.add(file)
      window.dispatchEvent(
        new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }),
      )
    },
    { b64, name },
  )
}

/**
 * 按 data-testid 走「选择图片」路径（主图那个 input）。
 *
 * 为什么不按序号定位：页面上同时存在多个 `input[type=file]`（主图、参考图，
 * 附图区渲染后还有"继续添加"），`nth(1)` 很可能落到参考图那个 input 上 ——
 * 点击"成功"但文件进了别处，比直接失败更难查。testid 不受 DOM 顺序与文案影响。
 */
export async function pickImageByTestId(
  page,
  testId,
  { name = 'picked.png', rgb = [255, 255, 255] } = {},
) {
  await page.getByTestId(testId).setInputFiles({
    name,
    mimeType: 'image/png',
    buffer: tinyPng({ rgb }),
  })
}

/** 样例知识点：字段与 /api/knowledge 返回的 row 一致。 */
export const knowledgeRows = [
  {
    id: 101,
    tag_name: '泰勒公式',
    subject_id: 1,
    sub_subject_id: 11,
    summary: '用多项式逼近函数，注意展开点与余项。',
    related_tags: ['中值定理'],
    created_at: '2026-09-01 10:00:00',
  },
  {
    id: 102,
    tag_name: '长难句拆分',
    subject_id: 2,
    sub_subject_id: 21,
    summary: '先找主谓，再挂从句。',
    related_tags: [],
    created_at: '2026-09-02 10:00:00',
  },
]

/** 样例公式。 */
export const formulaRows = [
  {
    id: 201,
    category: '高等数学',
    title: '牛顿-莱布尼茨公式',
    content: '$\\int_a^b f(x)dx = F(b) - F(a)$',
    created_at: '2026-09-01 09:00:00',
  },
]

/**
 * 给页面装上 API 打桩。
 * 返回一个 `calls` 数组，记录每个被拦截请求的 {method, url, body}，供断言"只调用一次"。
 */
/** 读请求体：JSON 优先，非 JSON（如 form）退回原文；两者都不会抛。 */
function readBody(request) {
  try {
    return request.postDataJSON()
  } catch {
    return request.postData() ?? null
  }
}

export async function mockApi(page, overrides = {}) {
  const calls = []
  // 用正则而不是 glob：glob `**/api/**` 要求 api 后还有 `/`，会漏掉 `/api/subjects`
  // 这种一级路径，漏掉的请求就会打到真实代理上（本机 8000 甚至真在跑）。
  // **必须用 ^ 锚定路径开头**：宽泛匹配 /api/ 会把 `/src/api/request.js` 这个真实的
  // 前端模块也拦掉，页面直接白屏（踩过）。
  await page.route(/^https?:\/\/[^/]+\/api(\/|$|\?)/, async (route, request) => {
    const url = new URL(request.url())
    const path = url.pathname
    // 记下请求体：多图用例要断言"一次请求带了几张图"，这是核心回归点
    const body = readBody(request)
    const entry = { method: request.method(), path, url: url.toString(), body }
    calls.push(entry)

    const data = resolver(path, request.method(), overrides)
    if (data === undefined) {
      // 漏打桩必须**可断言**：只回 404 的话，axios 拦截器只弹 toast（不写 console），
      // Playwright 的 page.on('console') 也抓不到「Failed to load resource」这类
      // DevTools Log 域消息 —— 页面于是照样渲染静态标题，烟测假绿。见 expectAllApiStubbed。
      entry.unmatched = true
      return route.fulfill({
        status: 404,
        json: { code: 404, data: null, message: '未打桩：' + path },
      })
    }
    return route.fulfill({ status: 200, json: ok(data) })
  })
  return calls
}

/**
 * 用例收尾断言：本次会话里**没有任何未打桩的接口**。
 *
 * 不这么做的后果：新增一个视图调用时忘了补桩 → 页面数据全空但静态文案还在 →
 * render-smoke 依然全绿（marker 命中的多是各页写死的 h2）。
 */
export function expectAllApiStubbed(calls) {
  const missed = calls.filter((c) => c.unmatched).map((c) => `${c.method} ${c.path}`)
  expect(missed, `以下接口未打桩，测试结论不可信：${[...new Set(missed)].join(', ')}`).toHaveLength(
    0,
  )
}

/**
 * 装上页面级错误守卫，返回 errors 数组（用例收尾断言其为空）。
 *
 * 只有 render-smoke 装了守卫是不够的：capture / card-click 里如果 Vue 渲染抛错
 * （走 console.error）或未捕获异常，测试会照样绿。
 */
export function guardPageErrors(page) {
  const errors = []
  page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`))
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`)
  })
  return errors
}

/** 空壳但**形状正确**的响应：真实接口字段名保证页面 computed 不炸（如 stats.total_mistakes）。 */
const emptyStats = {
  total_mistakes: 0,
  today_new: 0,
  by_subject: [],
  by_sub_subject: [],
  by_question_type: [],
  by_source_type: [],
}
const emptyReviewStats = {
  due_today: 0,
  reviewed_today: 0,
  total_reviews: 0,
  total_accuracy: 0,
  accuracy_today: 0,
  avg_mastery: 0,
  streak_days: 0,
  mastery_distribution: [],
  by_subject: [],
  weakest_tags: [],
  last_7_days: [],
}

function resolver(path, method, overrides) {
  if (overrides[path] !== undefined) {
    return typeof overrides[path] === 'function'
      ? overrides[path]({ path, method })
      : overrides[path]
  }
  // 带路径参数的接口：/api/subjects/<id>/profile 等
  if (/^\/api\/subjects\/\d+\/profile$/.test(path)) {
    // 形状对齐 routers/subjects.py:66 的"无档案"分支
    return { subject_id: Number(path.split('/')[3]), focus_areas: [], review_tips: '' }
  }
  // —— 业务数据 ——
  if (path === '/api/knowledge') return { items: knowledgeRows, total: knowledgeRows.length }
  // 真实接口返回 [{tag, mistake_count}] 数组（routers/knowledge.py），不是 {items:[字符串]}：
  // 写成后者会让 MistakeForm 的 `.map((item) => item.tag)` 抛 TypeError，且被它自己的
  // catch 静默吞掉 —— E2E 里标签联想恒为空，与生产行为不一致。
  if (path === '/api/knowledge/tags') {
    return knowledgeRows.map((r) => ({ tag: r.tag_name, mistake_count: 1 }))
  }
  if (path === '/api/formulas') return formulaRows
  if (path === '/api/mistakes') return { items: [], total: 0 }
  if (path === '/api/mistakes/approaches') return []
  if (path === '/api/vocab') return { items: [], total: 0 }
  if (path === '/api/vocab/due') return { items: [] }
  if (path === '/api/vocab/stats') return { total: 0, mastered: 0, due: 0, distribution: [] }
  if (path === '/api/papers') return []
  // 真实接口返回的就是数组（不是 {items:[]}）——写成对象会让 .filter 直接抛异常
  if (path === '/api/papers/scan') return []
  if (path === '/api/mocks') return []

  // —— 基础数据 ——
  if (path === '/api/subjects') {
    return [
      { id: 1, name: '数学二', kind: 'math' },
      { id: 2, name: '英语二', kind: 'english' },
    ]
  }
  if (path === '/api/sub_subjects') {
    return [
      { id: 11, subject_id: 1, name: '高等数学' },
      { id: 21, subject_id: 2, name: '阅读理解' },
    ]
  }

  // —— 统计聚合与复习 ——
  if (path === '/api/dashboard') return { stats: emptyStats, reviews: emptyReviewStats }
  if (path === '/api/stats') return emptyStats
  if (path === '/api/reviews/stats') return emptyReviewStats
  if (path === '/api/reviews/today') return { items: [], dueTotal: 0, remaining: 0 }
  if (path === '/api/reviews/forecast') return { overdue: 0, items: [] }
  // 日历热力图接口返回数组（ReviewHeatmap 直接 for..of 遍历）；返回对象会 TypeError
  if (path === '/api/reviews/calendar') return []
  if (path === '/api/reviews/practice') return { items: [] }
  if (path === '/api/health') return { status: 'ok', database: true, version: 'e2e', metrics: {} }
  if (path === '/api/knowledge/linked-mistakes') return { items: [] }
  if (path === '/api/ai/weekly-report') return { causes: [], summary: '', week_count: 0 }
  if (path === '/api/export') return { mistakes: [], vocab: [] }
  if (path === '/api/export/anki') return ''
  return undefined
}

/** 断言某个接口在本次会话里只被调用了一次（多图暂存的核心回归点）。 */
export function callsTo(calls, path, method = 'POST') {
  return calls.filter((c) => c.path === path && c.method === method)
}
