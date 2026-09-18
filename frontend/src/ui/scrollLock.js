/**
 * 全站唯一的 body 滚动锁（计数式）。
 *
 * 为什么不能各遮罩自己写 `body.style.overflow`：这些层是能叠的
 * （编辑弹窗 -> 确认框 -> 图片灯箱 -> Ctrl+K 命令面板），谁关自己那一层就
 * 无条件写回 ''，等于把下面还开着的层的锁一起解掉 —— 表现为"弹窗还开着，
 * 背景又能滚了"。命令面板原先就是硬写 ''，而它是全局快捷键唤起的，最容易撞上。
 */
let count = 0
let saved = ''

export function lockBodyScroll() {
  if (!count) saved = document.body.style.overflow
  count++
  document.body.style.overflow = 'hidden'
}

export function unlockBodyScroll() {
  count = Math.max(0, count - 1)
  if (!count) document.body.style.overflow = saved
}
