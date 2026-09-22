/**
 * 浏览器本地 TTS（speechSynthesis，零 AI 成本）。
 * 只用于英语单词/短语发音；不支持的环境返回 false，由调用方决定要不要提示。
 */
export function speechSupported() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

export function speakEnglish(text, { rate = 0.9 } = {}) {
  if (!speechSupported() || !text) return false
  const synth = window.speechSynthesis
  synth.cancel()
  const u = new SpeechSynthesisUtterance(String(text).trim())
  u.lang = 'en-US'
  u.rate = rate
  synth.speak(u)
  return true
}
