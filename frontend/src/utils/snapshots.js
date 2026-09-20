/** 「数据备份与回滚」页的展示层纯函数（放外面是为了能被单测直接钉住）。 */

const LABEL_RULES = [
  { prefix: 'before-restore', text: '回滚前的现场' },
  { prefix: 'before-batch-delete-', text: '批量删除前' },
  { prefix: 'before-import-', text: '导入前' },
  { prefix: 'manual', text: '手动快照' },
]

/**
 * 快照文件名里的来源标记 -> 人话。
 *
 * 空串是**启动自动备份**（`backup_database()` 不带 label）。显示成空白会让人以为
 * 这份备份坏了或者被清空过，所以这里必须给名字而不是留空。
 */
export function labelText(label) {
  const raw = String(label || '')
  if (!raw) return '启动自动备份'
  for (const rule of LABEL_RULES) {
    if (raw === rule.prefix) return rule.text
    if (rule.prefix.endsWith('-') && raw.startsWith(rule.prefix)) {
      const n = raw.slice(rule.prefix.length)
      return /^\d+$/.test(n) ? `${rule.text}（${n} 条）` : raw
    }
  }
  return raw
}

/** 1.1 MB 比 1123456 KB 直观；后端给的是 KB。 */
export function formatKb(kb) {
  const n = Number(kb) || 0
  if (n < 1024) return `${n % 1 === 0 ? n : n.toFixed(1)} KB`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} MB`
  return `${(n / (1024 * 1024)).toFixed(2)} GB`
}

/** `created_at` 是 "YYYY-MM-DD HH:MM:SS"（本地时间字符串）；手工解析，别交给 Date 猜时区。 */
function parseTime(text) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(String(text || ''))
  if (!m) return null
  const d = new Date(
    Number(m[1]),
    Number(m[2]) - 1,
    Number(m[3]),
    Number(m[4]),
    Number(m[5]),
    Number(m[6] || 0),
  )
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * "3 天前"这种相对说法只在当天之外有意义；当天的每一份要说清时刻，
 * 因为一天里可能连着好几份（启动备份 + 导入 + 回滚前现场）。
 */
export function ageText(createdAt, now = new Date()) {
  const d = parseTime(createdAt)
  if (!d) return '时间未知'
  const minutes = Math.floor((now.getTime() - d.getTime()) / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const days = Math.floor(minutes / 1440)
  if (days < 1) return `今天 ${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (days === 1) return `昨天 ${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (days < 30) return `${days} 天前`
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function pad(n) {
  return String(n).padStart(2, '0')
}

/**
 * 顶部四块瓷砖。
 *
 * "最早一份能回到哪天"是这页真正要回答的问题（回滚不是撤销，是回到某一次），
 * 所以它和"最新一份"并列，而不是只在表格里露一次。
 */
export function snapshotTiles(items, now = new Date()) {
  const list = Array.isArray(items) ? items : []
  const totalKb = list.reduce((sum, it) => sum + (Number(it.size_kb) || 0), 0)
  const dated = list.filter((it) => parseTime(it.created_at))
  const sorted = dated.sort((a, b) => parseTime(b.created_at) - parseTime(a.created_at))
  const newest = sorted[0]
  const oldest = sorted[sorted.length - 1]
  return [
    {
      key: 'count',
      label: '可用快照',
      value: list.length,
      unit: '份',
      tone: 'accent',
      icon: 'clock',
    },
    {
      key: 'newest',
      label: '最新一份',
      value: newest ? ageText(newest.created_at, now) : '暂无',
      tone: newest ? 'green' : 'gold',
      icon: 'refresh',
    },
    {
      key: 'oldest',
      label: '最早一份可回到',
      value: oldest ? ageText(oldest.created_at, now) : '暂无',
      tone: 'blue',
      icon: 'calendar',
    },
    {
      key: 'size',
      label: '备份目录占用',
      value: formatKb(totalKb),
      tone: 'violet',
      icon: 'layers',
    },
  ]
}
