/**
 * 命令面板状态服务：Ctrl+K 呼出，**一次搜全站**（错题/知识点/公式/生词/作文）+ 页面跳转。
 *
 * 以前是"先选范围再搜"的三个互斥 scope（各自打不同接口、公式还整库缓存到前端过滤），
 * 结果是"记得住分类才知道去哪搜"。现在默认 `all` 一次拿回五组命中，scope 退化成**过滤器**。
 */
import { reactive } from 'vue'
import request from '../api/request'

export const paletteState = reactive({
  open: false,
  query: '',
  scope: 'all', // all | mistakes | knowledge | formulas | vocab | essays
  groups: [], // 后端 /api/search 的原始分组（只含命中的组）
  searching: false,
  activeIndex: 0,
})

export const NAV_COMMANDS = [
  { icon: 'chart', label: '学习统计', hint: '概览', path: '/stats' },
  { icon: 'list', label: '错题列表', hint: '题库', path: '/mistakes' },
  { icon: 'plus-circle', label: '智能录入', hint: '新错题', path: '/capture' },
  { icon: 'refresh', label: '今日复习', hint: '复习', path: '/review' },
  { icon: 'pencil', label: '自主练习', hint: '练习', path: '/practice' },
  { icon: 'calendar', label: '真题模考', hint: '组卷', path: '/practice' },
  { icon: 'book', label: '生词本', hint: '英语', path: '/vocab' },
  { icon: 'layers', label: '知识点库', hint: '资料', path: '/knowledge' },
  { icon: 'sigma', label: '公式背诵', hint: '资料', path: '/formulas' },
  { icon: 'compass', label: '科目指南', hint: '资料', path: '/subjects' },
  { icon: 'image', label: '数据体检', hint: '只读巡检', path: '/integrity' },
]

// 快捷动作：不走路由，派发全局事件（AppLayout 监听）
export const QUICK_ACTIONS = [
  { icon: 'sun', label: '切换深浅主题', hint: '墨漫纸面', event: 'km:toggle-theme' },
  { icon: 'notebook', label: '快捷键速查', hint: '?', event: 'km:show-shortcuts' },
]

/** 实体 -> (显示名, 图标, 跳回哪)。target 用 `search` 参数，与错题库自己的筛选参数同名。 */
export const ENTITY_META = {
  mistakes: { label: '错题', icon: 'list', path: '/mistakes' },
  knowledge: { label: '知识点', icon: 'layers', path: '/knowledge' },
  formulas: { label: '公式', icon: 'sigma', path: '/formulas' },
  vocab: { label: '生词', icon: 'book', path: '/vocab' },
  essays: { label: '作文', icon: 'pencil', path: '/essays' },
}

export const SCOPES = [
  { value: 'all', label: '全部', icon: 'search' },
  ...Object.entries(ENTITY_META).map(([value, meta]) => ({
    value,
    label: meta.label,
    icon: meta.icon,
  })),
]

export function openPalette() {
  paletteState.open = true
  paletteState.query = ''
  paletteState.scope = 'all'
  paletteState.groups = []
  paletteState.searching = false
  paletteState.activeIndex = 0
}

export function closePalette() {
  paletteState.open = false
}

export function setScope(scope) {
  paletteState.scope = scope
  paletteState.activeIndex = 0
}

/** 把后端分组摊平成键盘可导航的一维列表（带跳转目标）。 */
export function visibleItems(state = paletteState) {
  const q = String(state.query || '').trim()
  const groups =
    state.scope === 'all' ? state.groups : state.groups.filter((g) => g.key === state.scope)
  const out = []
  for (const group of groups) {
    const meta = ENTITY_META[group.key] || { label: group.label, icon: 'search', path: '/mistakes' }
    for (const item of group.items || []) {
      out.push({
        kind: group.key,
        groupLabel: group.label || meta.label,
        icon: meta.icon,
        id: item.id,
        title: item.title,
        sub: item.subtitle || '',
        meta: item.meta || '',
        target: targetOf(group.key, item, meta.path, q),
      })
    }
  }
  return out
}

function targetOf(key, item, path, q) {
  if (key === 'knowledge') {
    // 知识笺墙按标签筛，所以回带标签名而不是 id（与旧的知识点 scope 行为一致）
    return `/knowledge?tag=${encodeURIComponent(item.title || '')}`
  }
  return `${path}?search=${encodeURIComponent(q || item.title || '')}`
}

/**
 * 摊平的列表按实体分段，但每行仍带着**它在一维列表里的下标**。
 * 分段渲染最容易错的正是这里：一旦 `activeIndex` 按"组内序号"走，
 * 上下方向键与鼠标高亮就会各指一条（组多时更是完全对不上）。
 */
export function visibleSections(state = paletteState) {
  const out = []
  visibleItems(state).forEach((item, index) => {
    const last = out[out.length - 1]
    if (last && last.label === item.groupLabel) last.rows.push({ item, index })
    else out.push({ label: item.groupLabel, rows: [{ item, index }] })
  })
  return out
}

let searchTimer = null
let searchSeq = 0

export function onPaletteInput(query) {
  paletteState.query = query
  paletteState.activeIndex = 0
  if (searchTimer) clearTimeout(searchTimer)
  const trimmed = String(query || '').trim()
  if (!trimmed) {
    paletteState.groups = []
    paletteState.searching = false
    return
  }
  paletteState.searching = true
  const seq = ++searchSeq
  searchTimer = setTimeout(() => runSearch(trimmed, seq), 200)
}

async function runSearch(query, seq = ++searchSeq) {
  const trimmed = String(query || '').trim()
  if (!trimmed) {
    paletteState.groups = []
    paletteState.searching = false
    return
  }
  try {
    const res = await request.get('/search', { params: { q: trimmed }, silent: true })
    if (seq !== searchSeq) return
    paletteState.groups = res.data.data?.groups || []
  } catch (err) {
    // 失败要清结果：留着上一次命中会显示成"这次搜到了"，是假数据
    if (seq === searchSeq) paletteState.groups = []
  } finally {
    if (seq === searchSeq) paletteState.searching = false
  }
}

export function moveActive(delta, max) {
  const total = max <= 0 ? 0 : max
  if (!total) return
  paletteState.activeIndex = (paletteState.activeIndex + delta + total) % total
}
