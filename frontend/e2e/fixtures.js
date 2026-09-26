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
 * 让某个打桩返回自定义 `message`。
 *
 * 后端把**通道降级原因**放在响应的 `message` 里（如"英语整篇解析完成（首选通道 X 失败，
 * 已降级）"），而不是 data 里 —— 只用 `ok(data)` 的默认 'success' 就永远测不到这条链路。
 */
export function withMessage(data, message) {
  return { __withMessage: true, data, message }
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
 * 样例作文批改记录。形状必须对齐 routers/essay.py：
 * 列表是 {items:[_row_brief], total}，详情在 brief 之上加 essay_text + result（批改 JSON）。
 */
export const essayResult = {
  kind: 'e2_long',
  kind_name: '英语二 大作文（图表作文 15 分）',
  max_score: 15,
  score: 11,
  band: '第四档',
  dimensions: { content: 5, structure: 2, language: 3, format: 1 },
  estimated_word_count: 152,
  corrections: [
    {
      original: 'The number of students go up.',
      corrected: 'The number of students goes up.',
      type: '主谓一致',
      note: 'the number of 作主语谓语用单数',
    },
  ],
  highlights: ['定语从句使用自然'],
  overall: '要点齐全，语言基本准确。',
  top_errors: ['主谓一致'],
  weakness_advice: '专项练三单。',
  upgrade_tips: ['I think it is important -> It is widely acknowledged that...'],
  model_version: 'As is vividly shown in the chart above.',
  raw_transcript: 'The number of students go up.',
}

export const essayRows = [
  {
    id: 301,
    kind: 'e2_long',
    kind_name: '英语二 大作文（图表作文 15 分）',
    prompt_text: 'Write an essay of 150 words on the chart below.',
    score: 11,
    max_score: 15,
    created_at: '2026-09-18 20:30:00',
    excerpt: 'The number of students go up.',
  },
]

/**
 * 全站搜索（`/api/search`，命令面板 Ctrl+K）的样例命中。
 * 形状必须对齐 services/search_service.search_all：
 * `{q, limit, total, groups:[{key,label,total,items:[{id,title,subtitle,meta}]}]}`，
 * 组顺序即面板分段顺序（错题 → 知识点 → 公式），摊平成键盘导航的一维列表。
 */
export const searchGroups = [
  {
    key: 'mistakes',
    label: '错题',
    total: 3,
    items: [{ id: 501, title: '…中值定理的条件…', subtitle: '数学二', meta: 'choice' }],
  },
  {
    key: 'knowledge',
    label: '知识点',
    total: 1,
    items: [{ id: 101, title: '中值定理', subtitle: '注意开区间可导', meta: '数学二' }],
  },
  {
    key: 'formulas',
    label: '公式',
    total: 1,
    items: [
      { id: 202, title: '拉格朗日中值定理', subtitle: "f(b)-f(a)=f'(ξ)(b-a)", meta: '高等数学' },
    ],
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

/**
 * 数据体检（`/api/system/integrity`，只读巡检页）的报告。
 * 形状照 `integrity_service.scan()`：字段名写错页面会静默显示 0（不报错），
 * 所以这里的键要与后端逐一对应。
 */
export const integrityReport = {
  referenced: 50,
  files: 152,
  bytes_total: 15000000,
  orphans: [
    { rel: 'images/dead.png', size: 5000, mtime: '2026-08-01', kind: 'image' },
    { rel: 'images/_thumbs/dead.webp', size: 900, mtime: '2026-08-02', kind: 'thumb' },
  ],
  orphan_total: 102,
  orphan_bytes: 1123456,
  orphan_truncated: true,
  protected_recent: 21,
  missing: [{ name: 'gone.png', refs: ['mistakes#12'] }],
  missing_total: 1,
  unparseable_refs: 0,
  keep_days: 1,
  images_dir_exists: true,
}

/**
 * 冲刺计划（`GET /api/sprint/plan`）。形状照 `sprint_service.get_sprint_plan()`：
 * 日期非法/已考时后端只回三态字段，daily_target 为 null —— 页面按此降级。
 */
export const sprintPlan = {
  exam_date: '2026-12-19',
  today: '2026-09-22',
  days_left: 88,
  passed: false,
  date_invalid: false,
  total_active: 320,
  due_now: 120,
  never_started: 56,
  reviewed_today: 12,
  daily_target: 3,
  quota_note: '每天 3 题，考前刚好过完一遍全部积压',
  subjects: [{ name: '数学二', total: 180, due: 80, never: 30, mastery: 42 }],
  weeks: [
    { label: '第 1 周', days: 7, end_date: '2026-09-29', target: 21 },
    { label: '第 2 周', days: 7, end_date: '2026-10-06', target: 21 },
  ],
}

/**
 * 数据备份与回滚（`/api/snapshots`、`POST /api/snapshots/restore`）。
 * 形状照 `database.list_snapshots()` / `restore_snapshot()`：
 * `label` 为空串就是启动自动备份（前端要显示成"启动自动备份"，不能留空白）；
 * `tables_*` 里 `null` 表示"那份快照里没有这张表"，与 0 条是两件事。
 */
export const snapshotRows = [
  {
    name: 'kaoyan_mistakes_20260920_090000.db',
    label: '',
    size_kb: 2048,
    created_at: '2026-09-20 09:00:00',
  },
  {
    name: 'kaoyan_mistakes_20260101_080000_before-import-5.db',
    label: 'before-import-5',
    size_kb: 1024,
    created_at: '2026-01-01 08:00:00',
  },
]

export const snapshotRestoreResult = {
  name: snapshotRows[0].name,
  safety_snapshot: 'kaoyan_mistakes_20260920_120000_before-restore.db',
  tables_before: {
    mistakes: 20,
    review_records: 9,
    knowledge_base: 3,
    vocab_items: 0,
    exam_papers: null,
  },
  tables_after: {
    mistakes: 5,
    review_records: 2,
    knowledge_base: 1,
    vocab_items: 0,
    exam_papers: 0,
  },
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
    if (data && data.__withMessage) {
      return route.fulfill({ status: 200, json: ok(data.data, data.message) })
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
  exam_countdown: { days: 91, date: '2026-12-19', passed: false },
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
  // 命令面板的全站搜索：漏打桩会让 Ctrl+K 用例假绿（groups 为空 → 面板只显示"没有匹配结果"）
  if (path === '/api/search') return { q: '中值', limit: 5, total: 5, groups: searchGroups }
  if (path === '/api/system/integrity') return integrityReport
  // 快照列表 GET / 手动备份 POST 打在同一个路径上，必须按方法分开打桩
  if (path === '/api/snapshots') {
    return method === 'POST' ? { name: snapshotRows[1].name } : snapshotRows
  }
  if (path === '/api/snapshots/restore') return snapshotRestoreResult
  if (path === '/api/mistakes') return { items: [], total: 0 }
  if (path === '/api/mistakes/approaches') return []
  if (path === '/api/vocab') return { items: [], total: 0 }
  if (path === '/api/vocab/due') return { items: [] }
  if (path === '/api/vocab/stats') return { total: 0, mastered: 0, due: 0, distribution: [] }
  // 闪卡真题语境回链（按 vocab id 命中，闪卡背面才请求）
  if (/^\/api\/vocab\/\d+\/context$/.test(path)) return []
  if (path === '/api/papers') return []
  // 真实接口返回的就是数组（不是 {items:[]}）——写成对象会让 .filter 直接抛异常
  if (path === '/api/papers/scan') return []
  if (path === '/api/mocks') return []
  // 冲刺计划页：漏打桩会渲染成"考试日期没配置好"的空态而不是计划本身
  if (path === '/api/sprint/plan') return sprintPlan
  // 作文档案：列表 {items,total}，详情 = brief + essay_text + result
  if (path === '/api/essays') return { items: essayRows, total: essayRows.length }
  // 进步曲线：全量得分率时间正序（EssayView 挂载即取，必须打桩否则 unstubbed 404 假红）
  if (path === '/api/essays/trend') {
    return essayRows.map((r) => ({
      id: r.id,
      kind: r.kind,
      score: r.score,
      max_score: r.max_score,
      created_at: r.created_at,
      pct: Math.round((r.score / (r.max_score || 1)) * 100),
    }))
  }
  if (/^\/api\/essays\/\d+$/.test(path)) {
    return { ...essayRows[0], essay_text: essayResult.raw_transcript, result: essayResult }
  }

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
  if (path === '/api/reviews/blocks')
    return [
      { key: 'math', name: '数学', due: 0, total: 0 },
      { key: 'cs408', name: '408', due: 0, total: 0 },
      { key: 'english', name: '英语', due: 0, total: 0 },
      { key: 'politics', name: '政治', due: 0, total: 0 },
    ]
  if (path === '/api/reviews/forecast') return { overdue: 0, items: [] }
  // 日历热力图接口返回数组（ReviewHeatmap 直接 for..of 遍历）；返回对象会 TypeError
  if (path === '/api/reviews/calendar') return []
  // 稍后再看/每日配额（复习页加载即请求剩余次数）
  if (path === '/api/reviews/snooze') {
    return method === 'POST' ? { mistake_id: 0, remaining: 2 } : { remaining: 3 }
  }
  if (path === '/api/reviews/quota') {
    return method === 'PUT' ? { daily_limit: 50 } : { daily_limit: 50 }
  }
  if (/^\/api\/mistakes\/\d+\/star$/.test(path))
    return { id: Number(path.split('/')[3]), starred: true }
  if (path === '/api/reviews/practice') return { items: [] }
  if (path === '/api/health') return { status: 'ok', database: true, version: 'e2e', metrics: {} }
  // 全局倒计时印（外壳每个页面都取；漏打桩 → 11 条烟测全红，正是想要的兜底）
  if (path === '/api/exam-countdown') return { days: 91, date: '2026-12-19', passed: false }
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
