/**
 * 公式挖空默写：把内容里的公式段替换成 KaTeX 下划线空位（长度按原段大致等比）。
 *
 * 只处理 `\\(...\\)` 与 `$$...$$` 两种定界（公式库统一用它们包裹，见 AGENTS 第 7 节）；
 * 纯文本部分原样保留——考的是公式，不是把整句都藏起来。
 */
export function clozeFormula(content) {
  const blank = (len) => {
    const units = Math.max(2, Math.min(16, Math.round(len / 8)))
    return `\\(\\underline{${'\\;'.repeat(units)}}\\)`
  }
  return String(content || '')
    .replace(/\\\([\s\S]*?\\\)/g, (m) => blank(m.length))
    .replace(/\$\$[\s\S]*?\$\$/g, (m) => blank(m.length))
}
