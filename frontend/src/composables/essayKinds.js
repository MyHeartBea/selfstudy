/** 考研英语作文类型（与后端 app/services/ai_essay.py 的 ESSAY_KINDS 对齐） */
export const ESSAY_KINDS = [
  { value: 'e2_short', label: '英语二 小作文（应用文 10 分）', max: 10 },
  { value: 'e2_long', label: '英语二 大作文（图表作文 15 分）', max: 15 },
  { value: 'e1_short', label: '英语一 小作文（应用文 10 分）', max: 10 },
  { value: 'e1_long', label: '英语一 大作文（图画作文 20 分）', max: 20 },
]

export const DIMENSION_LABELS = {
  content: '内容要点',
  structure: '结构衔接',
  language: '语言准确',
  format: '格式语域',
}

export function essayKindMeta(value) {
  return ESSAY_KINDS.find((k) => k.value === value) || ESSAY_KINDS[1]
}

/** 批改结果里的分数换算成百分比（进度条用） */
export function essayScorePct(score, maxScore) {
  if (!maxScore) return 0
  return Math.max(0, Math.min(100, Math.round((score / maxScore) * 100)))
}
