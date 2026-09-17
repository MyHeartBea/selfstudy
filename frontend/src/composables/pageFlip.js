/**
 * 翻书转场的**方向**状态（模块级单例）
 * ===========================================================================
 * 为什么单独一个文件：转场发生在 AppLayout 内部的 RouterView，
 * 而方向的判定要在路由变化时更新 —— 放在组件里会与布局耦合。
 *
 * 方向由 **导航顺序** 决定（router/index.js 的 NAV_ORDER）：
 * "左右"只能由导航里的先后顺序定义，路由表本身不含这个信息。
 */
import { ref } from 'vue'

import { navIndexOf } from '../router'

/** 'next' = 新页在当前页右边；'prev' = 在左边 */
export const pageDir = ref('next')

/** 挂到 router 上；返回取消函数 */
export function initPageFlip(router) {
  return router.beforeEach((to, from) => {
    if (!from.name) return true
    // 注意方向语义：next 表示"新页在当前页右边"。
    // 第一版写成 >= 导致方向整体反了（用户实测反馈），这里用 > 判定。
    pageDir.value = navIndexOf(to.name) > navIndexOf(from.name) ? 'next' : 'prev'
    return true
  })
}
