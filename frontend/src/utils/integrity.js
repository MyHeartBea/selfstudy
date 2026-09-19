/** 「数据体检」页的展示层纯函数（放外面是为了能被单测直接钉住）。 */

export const KIND_LABEL = {
  image: '错题配图',
  thumb: '缩略图',
  exam_page: '真题页图',
}

/** 孤儿/缺图清单要按体积读，1.1 MB 比 1123456 字节直观。 */
export function formatBytes(bytes) {
  const n = Number(bytes) || 0
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * 顶部四块瓷砖。
 *
 * 缺图那条特意把 0 也画出来："0 条"是这页最有价值的信息（没有破图），
 * 而不是没数据；所以这里不做"为 0 就隐藏"。
 */
export function summaryTiles(report) {
  const r = report || {}
  return [
    {
      key: 'referenced',
      label: '库里在用的图片',
      value: r.referenced ?? 0,
      unit: '张',
      tone: 'accent',
      icon: 'image',
    },
    {
      key: 'files',
      label: '磁盘上的图片文件',
      value: r.files ?? 0,
      unit: '个',
      tone: 'blue',
      icon: 'layers',
    },
    {
      key: 'orphans',
      label: '没人引用的文件',
      value: r.orphan_total ?? 0,
      unit: `个 / ${formatBytes(r.orphan_bytes)}`,
      tone: (r.orphan_total ?? 0) > 0 ? 'gold' : 'green',
      icon: 'inbox',
    },
    {
      key: 'missing',
      label: '打不开的图（缺图）',
      value: r.missing_total ?? 0,
      unit: '条',
      tone: (r.missing_total ?? 0) > 0 ? 'violet' : 'green',
      icon: 'alert',
    },
  ]
}

/** 「缺图」条目上显示是谁在引用它（后端给的是 `表#id`）。 */
export function locatorLabel(refs) {
  const list = refs || []
  if (!list.length) return ''
  const first = list[0].split('#')[0]
  const where = first === 'mistakes' ? '错题' : first === 'exam_questions' ? '真题' : first
  const more = list.length > 1 ? ` 等 ${list.length} 处` : ''
  return `${where} ${list[0].split('#')[1]}${more}`
}
