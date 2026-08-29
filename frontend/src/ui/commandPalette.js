/**
 * 命令面板状态服务：Ctrl+K 呼出，多范围搜索（错题/知识点/公式）+ 页面跳转。
 */
import { reactive } from 'vue'
import request from '../api/request'

export const paletteState = reactive({
  open: false,
  query: '',
  scope: 'mistake', // mistake | knowledge | formula
  results: [],
  searching: false,
  activeIndex: 0,
})

export const NAV_COMMANDS = [
  { icon: 'chart', label: '学习统计', hint: '概览', path: '/stats' },
  { icon: 'list', label: '错题列表', hint: '题库', path: '/mistakes' },
  { icon: 'plus-circle', label: '智能录入', hint: '新错题', path: '/capture' },
  { icon: 'refresh', label: '今日复习', hint: '复习', path: '/review' },
  { icon: 'pencil', label: '自主练习', hint: '练习', path: '/practice' },
  { icon: 'book', label: '生词本', hint: '英语', path: '/vocab' },
  { icon: 'layers', label: '知识点库', hint: '资料', path: '/knowledge' },
  { icon: 'sigma', label: '公式背诵', hint: '资料', path: '/formulas' },
  { icon: 'compass', label: '科目指南', hint: '资料', path: '/subjects' },
]

export const SCOPES = [
  { value: 'mistake', label: '错题', icon: 'list' },
  { value: 'knowledge', label: '知识点', icon: 'book' },
  { value: 'formula', label: '公式', icon: 'sigma' },
]

export function openPalette() {
  paletteState.open = true
  paletteState.query = ''
  paletteState.results = []
  paletteState.searching = false
  paletteState.activeIndex = 0
}

export function closePalette() {
  paletteState.open = false
}

export function setScope(scope) {
  paletteState.scope = scope
  paletteState.activeIndex = 0
  runSearch(paletteState.query, scope)
}

let searchTimer = null
let searchSeq = 0

// 公式库全量缓存（量小，客户端过滤）
let formulaCache = null

export function onPaletteInput(query) {
  paletteState.query = query
  paletteState.activeIndex = 0
  if (searchTimer) clearTimeout(searchTimer)
  const trimmed = query.trim()
  if (!trimmed) {
    paletteState.results = []
    paletteState.searching = false
    return
  }
  paletteState.searching = true
  const seq = ++searchSeq
  searchTimer = setTimeout(() => runSearch(trimmed, paletteState.scope, seq), 200)
}

async function runSearch(query, scope, seq = ++searchSeq) {
  const trimmed = String(query || '').trim()
  if (!trimmed) {
    paletteState.results = []
    paletteState.searching = false
    return
  }
  try {
    if (scope === 'mistake') {
      const res = await request.get('/mistakes', {
        params: { search: trimmed, page: 1, page_size: 8 },
        silent: true,
      })
      if (seq !== searchSeq) return
      paletteState.results = (res.data.data?.items || []).map((item) => ({
        kind: 'mistake',
        id: item.id,
        title: item.question,
        type: item.question_type,
        subject: item.subject_id,
        target: '/mistakes',
      }))
    } else if (scope === 'knowledge') {
      const res = await request.get('/knowledge', {
        params: { tag: trimmed, page: 1, page_size: 8 },
        silent: true,
      })
      if (seq !== searchSeq) return
      const data = res.data.data
      const items = Array.isArray(data) ? data : data?.items || []
      paletteState.results = items.map((item) => ({
        kind: 'knowledge',
        id: item.id,
        title: item.tag_name,
        sub: item.summary || '',
        target: `/knowledge?tag=${encodeURIComponent(item.tag_name)}`,
      }))
    } else {
      if (!formulaCache) {
        const res = await request.get('/formulas', { silent: true })
        formulaCache = res.data.data || []
      }
      if (seq !== searchSeq) return
      const keyword = trimmed.toLowerCase()
      paletteState.results = formulaCache
        .filter(
          (item) =>
            (item.title || '').toLowerCase().includes(keyword) ||
            (item.content || '').toLowerCase().includes(keyword),
        )
        .slice(0, 8)
        .map((item) => ({
          kind: 'formula',
          id: item.id,
          title: item.title,
          sub: item.category,
          target: '/formulas',
        }))
    }
  } catch (err) {
    if (seq === searchSeq) paletteState.results = []
  } finally {
    if (seq === searchSeq) paletteState.searching = false
  }
}

export function moveActive(delta, max) {
  const total = max <= 0 ? 0 : max
  if (!total) return
  paletteState.activeIndex = (paletteState.activeIndex + delta + total) % total
}
