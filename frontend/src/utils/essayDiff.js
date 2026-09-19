/** 作文改错逐词对比：把「原句与改句」拆成 same/del/ins 片段，前端用删除线/下划线呈现。 */

function splitWords(text) {
  // 英文按空白切，标点跟随前面的词（避免 "home." vs "home" 被判成两处改动）
  return String(text || '')
    .split(/(\s+)/)
    .filter((t) => t !== '')
}

function normalize(word) {
  return word.toLowerCase().replace(/[.,!?;:]+$/, '')
}

/**
 * 经典 LCS 逐词 diff。句子长度有限（AI 只给整句），O(n*m) 足够。
 * 返回 [{ type: 'same' | 'del' | 'ins', text }]。
 */
export function wordDiff(original, corrected) {
  const a = splitWords(original).filter((w) => w.trim() !== '')
  const b = splitWords(corrected).filter((w) => w.trim() !== '')
  const n = a.length
  const m = b.length
  if (!n && !m) return []
  if (!n) return [{ type: 'ins', text: b.join(' ') }]
  if (!m) return [{ type: 'del', text: a.join(' ') }]

  // dp[i][j] = a[i:] 与 b[j:] 的最长公共子序列长度
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      dp[i][j] =
        normalize(a[i]) === normalize(b[j])
          ? dp[i + 1][j + 1] + 1
          : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const out = []
  const push = (type, text) => {
    if (out.length && out[out.length - 1].type === type) {
      out[out.length - 1].text += ` ${text}`
    } else {
      out.push({ type, text })
    }
  }
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (normalize(a[i]) === normalize(b[j])) {
      push('same', a[i])
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push('del', a[i])
      i += 1
    } else {
      push('ins', b[j])
      j += 1
    }
  }
  while (i < n) {
    push('del', a[i])
    i += 1
  }
  while (j < m) {
    push('ins', b[j])
    j += 1
  }
  return out
}

/** diff 片段数（用于「改了多少」的粗略度量） */
export function wordDiffStats(original, corrected) {
  const parts = wordDiff(original, corrected)
  const del = parts.filter((p) => p.type === 'del').length
  const ins = parts.filter((p) => p.type === 'ins').length
  return { changed: del + ins, hasChange: del + ins > 0 }
}
