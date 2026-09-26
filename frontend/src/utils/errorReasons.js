/** 错因归因四类的展示名（与后端 mistake_service.ERROR_REASONS 一一对应，别两边各写一份）。 */
export const ERROR_REASON_LABELS = {
  knowledge: '知识盲区',
  read: '审题失误',
  calc: '计算失误',
  careless: '粗心大意',
}

export function errorReasonLabel(key) {
  return ERROR_REASON_LABELS[key] || key || ''
}
