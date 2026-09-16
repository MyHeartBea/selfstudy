/**
 * 契约层扩展（core/api/extra）—— 阶段 4 剩余页面的端点
 * ---------------------------------------------------------------------------
 * 与 index.js 同一套规则：URL 只在这里出现；统一解包；标注响应形状。
 *
 * 为什么单独一个文件：index.js 已承载核心页面的端点（复习/录入/错题/知识），
 * 继续往它追加会让"核心"与"外围"混在一起；按阶段拆文件比按大小拆更好读。
 * 未来新页面一律往这里加，或再开 extra2 —— 关键是**视图层永远不出现 URL**。
 */
import { __client as client } from './index'

/** 复用 index.js 的解包逻辑（这里重新实现一份会漂移，所以直接复制同样的语义） */
async function unwrap(promise) {
  const res = await promise
  const body = res.data
  if (!body || typeof body !== 'object' || !('data' in body)) {
    const err = new Error('响应格式不符合约定（缺少 data）')
    err.status = res.status
    throw err
  }
  if (body.code !== undefined && body.code !== 200) {
    const err = new Error(body.message || '请求失败')
    err.status = body.code
    throw err
  }
  return body.data
}

/* ────────────────────────────── 真题库 ────────────────────────────── */
export const papersApi = {
  /**
   * 列表。字段（基线实测）：
   * [{ id, title, year, subject, source_path, answer_path, status, status_note,
   *    question_count, answered_count, created_at }]
   * status 常见值：pending / imported / failed（失败时 status_note 有原因）
   */
  list: () => unwrap(client.get('/papers')),

  /**
   * 扫描真题目录。字段（基线实测）：
   * [{ name, rel_path, kind, size_kb, subject, year, imported, mixed,
   *    sources:[{ kind, rel_path, size_kb }],
   *    answer_path, answer_kind }]
   * kind: question / answer；mixed=true 表示题目与答案在同一文件里
   */
  scan: () => unwrap(client.get('/papers/scan')),
}

/* ────────────────────────────── 模考 ────────────────────────────── */
export const mocksApi = {
  /**
   * 历史模考。字段（基线实测）：
   * [{ id, exam_year, total, correct, score, duration_min, used_seconds, created_at }]
   */
  list: (limit = 24) => unwrap(client.get('/mocks', { params: { limit } })),
}

/* ────────────────────────────── 科目画像 ────────────────────────────── */
export const subjectProfileApi = {
  /**
   * 科目画像。字段（基线实测）：
   * { id, subject_id, focus_areas, review_tips, updated_at }
   * focus_areas / review_tips 是**文本**（不是数组），按行渲染即可。
   */
  get: (subjectId) => unwrap(client.get(`/subjects/${subjectId}/profile`)),

  /**
   * 解题套路（自主练习页用的模板列表）。
   * 契约：GET /api/approaches - **[字符串数组]**（裸数组，不是对象数组）
   */
  approaches: () => unwrap(client.get('/approaches')),
}

/* ────────────────────────────── 自主练习 ────────────────────────────── */
export const practiceApi = {
  /**
   * 常规练习（按薄弱度抽题）。
   * 契约：GET /api/reviews/practice?limit=N - **裸数组**（题目列表，不是分页对象）
   */
  practice: (limit = 10) => unwrap(client.get('/reviews/practice', { params: { limit } })),

  /**
   * 模考式随机抽题。
   * 契约：GET /api/reviews/practice/mock?limit=N - **裸数组**
   */
  mock: (limit = 10) => unwrap(client.get('/reviews/practice/mock', { params: { limit } })),
}

/* ────────────────────────────── 数据导出 ────────────────────────────── */
export const dataApi = {
  /**
   * 全量导出。字段（基线实测）：{ exported_at, mistakes:[...], knowledge:[...] }
   * 用途：换库前的自查、以及"数据一致性"的第三方凭证。
   */
  exportAll: () => unwrap(client.get('/export')),

  /** 导出为可下载的 JSON（前端生成 Blob，不新增后端端点） */
  async downloadJson(filename = 'km-v2-export.json') {
    const data = await dataApi.exportAll()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    // 交给浏览器读完再释放
    setTimeout(() => URL.revokeObjectURL(url), 4000)
  },
}
