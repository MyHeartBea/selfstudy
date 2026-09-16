/**
 * 契约层（core/api）—— v3 前端与后端之间的**唯一通道**
 * ---------------------------------------------------------------------------
 * 为什么要有这一层（这是 v2 的痛点）：
 *   v2 里 URL 与 fetch 散落在十几个视图里，后端一改字段就要全局搜。这里定死三条规则：
 *     1. **URL 只在本目录出现**，视图层一律调用函数
 *     2. 统一解包 `{code, data, message}`，只把 `data` 交给上层（失败抛 ApiError）
 *     3. 每个函数标注它依赖的响应形状（与 docs/contract-baseline.json 对应），
 *        改后端时跑 `python scripts/contract_diff.py --check` 就能发现破坏
 *
 * 契约基线里有 28 个只读端点，阶段 3 先接「今日复习」用到的 3 个；
 * 其余按页面推进逐步补齐（不要一次写完再联调）。
 */
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  // AI 相关端点单次可能 165-210 秒（英语整篇精读），所以给足超时
  timeout: 300000,
  // 数组参数序列化为重复键（difficulty=3&difficulty=4），与 FastAPI Query(List[int]) 一致
  paramsSerializer: { indexes: null },
})

/** 后端统一错误：带上 HTTP 状态与后端 message，供 UI 决定提示文案 */
export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const payload = err?.response?.data
    const message = payload?.message || err?.message || '请求失败'
    return Promise.reject(new ApiError(message, err?.response?.status, payload))
  },
)

/** 解包统一响应：只返回 data；code 非 200 视为失败 */
async function unwrap(promise) {
  const res = await promise
  const body = res.data
  if (!body || typeof body !== 'object' || !('data' in body)) {
    throw new ApiError('响应格式不符合约定（缺少 data）', res.status, body)
  }
  if (body.code !== undefined && body.code !== 200) {
    throw new ApiError(body.message || '请求失败', body.code, body)
  }
  return body.data
}

/* ────────────────────────────── 复习 ────────────────────────────── */
export const reviewsApi = {
  /**
   * 今日复习队列。
   * 契约：GET /api/reviews/today - { items, dueTotal, remaining, dailyLimit, reviewedToday }
   * 注意：`items` 是题目数组；字段名以 contract-baseline 为准（question_type 等）
   */
  today: () => unwrap(client.get('/reviews/today')),

  /** 复习统计（仪表盘与复习页头部共用）：GET /api/reviews/stats */
  stats: () => unwrap(client.get('/reviews/stats')),

  /**
   * 提交一次复习结果。
   * 契约：POST /api/mistakes/{id}/review  body { result, note?, user_answer? }
   */
  submit: (mistakeId, { correct, note = '', userAnswer = '' }) =>
    unwrap(
      client.post(`/mistakes/${mistakeId}/review`, {
        result: !!correct,
        note,
        user_answer: userAnswer,
      }),
    ),
}

/* ────────────────────────────── 基础数据 ────────────────────────────── */
export const baseApi = {
  /** GET /api/subjects - [{ id, name, kind }] */
  subjects: () => unwrap(client.get('/subjects')),
  /** GET /api/sub_subjects - [{ id, subject_id, name }] */
  subSubjects: (subjectId) =>
    unwrap(client.get('/sub_subjects', { params: subjectId ? { subject_id: subjectId } : {} })),
}

/** 便于测试替换（单测里注入假 client） */
export const __client = client

/* ────────────────────────────── AI 解析 ────────────────────────────── */
/**
 * 重要事实（实测）：这两个端点**是同步阻塞的**，英语整篇精读实测 165-210 秒。
 * 所以：
 *   - axios 的 timeout 必须给足（上面 client 已设 300000），不要用更短的覆盖
 *   - UI 必须显示**真实阶段**而不是百分比（假进度比没有进度更伤信任）
 */
export const aiApi = {
  /**
   * 英语整篇精读（多图或文本）。
   * 契约：POST /api/ai/english - data 含 passage_text / passage_translation /
   *       english_sentences / english_phrases / english_words / english_questions
   *       （**是响应形状，不是请求形状**，见 ai_english.normalize_english_parsed）
   */
  english: ({ images = [], text = '', instruction = '' }) =>
    unwrap(client.post('/ai/english', { images, text, instruction }, { silent: true })),

  /**
   * 通用 OCR / 题目解析（带参考图时也走这个）。
   * 契约：POST /api/ai/ocr body { image_base64, images, instruction, reference_image_base64 }
   */
  ocr: ({ images = [], instruction = '', referenceImage = '' }) =>
    unwrap(
      client.post(
        '/ai/ocr',
        {
          image_base64: images[0] || '',
          images,
          instruction,
          reference_image_base64: referenceImage,
        },
        { silent: true },
      ),
    ),
}

/* ────────────────────────────── 错题 ────────────────────────────── */
export const mistakesApi = {
  /**
   * 列表。
   * 契约：GET /api/mistakes 不传 page 返回数组；传 page 返回 { items, total, page, page_size }
   */
  list: (params = {}) => unwrap(client.get('/mistakes', { params })),

  /** 详情：GET /api/mistakes/{id} */
  detail: (id) => unwrap(client.get(`/mistakes/${id}`)),

  /** 新建：POST /api/mistakes（字段见 schemas.MistakeCreate） */
  create: (payload) => unwrap(client.post('/mistakes', payload)),

  /** 批量删除：POST /api/mistakes/batch { ids, action } */
  batch: (ids, action = 'delete') => unwrap(client.post('/mistakes/batch', { ids, action })),
}
