/** 客观题判分纯函数：复习作答组件与模考交卷共用（无副作用，可单测）。 */

/** 归一化字母答案：大写、只保留 A-D、升序排列（'b a' → 'AB'）。 */
export function normalizeLetters(value) {
  return String(value || '')
    .toUpperCase()
    .split('')
    .filter((ch) => ch >= 'A' && ch <= 'D')
    .sort()
    .join('')
}

/**
 * 客观题判分：单选要求等值；多选要求集合相等（顺序无关、全对才算对）。
 * @param {string} answer 学生答案，如 'A' 或 'ABD'，空串视为未作答
 * @param {string} correct 正确答案，如 'B' 或 'AC'
 */
export function scoreLetters(answer, correct) {
  const ans = String(answer || '').trim()
  if (!ans) return false
  return normalizeLetters(ans) === normalizeLetters(correct)
}
