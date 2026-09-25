/** 客观题判分纯函数：复习作答组件与模考交卷共用（无副作用，可单测）。
 *
 *  口径必须与后端 app/services/answer_service.py::judge_letters **完全一致**
 *  （取 A-G、去重、排序后整体相等）：这里只负责即时反馈，落库结果由服务端复核，
 *  两边漂移会让成绩单和 SM-2 记录说的是两回事。改动务必同步 tests/examScoring.test.js
 *  里那张与后端共享的用例表。
 */

/** 归一化字母答案：大写、只保留 A-G、去重升序排列（'b a a' 归一为 'AB'）。 */
export function normalizeLetters(value) {
  return [
    ...new Set(
      String(value || '')
        .toUpperCase()
        .split('')
        .filter((ch) => ch >= 'A' && ch <= 'G'),
    ),
  ]
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
