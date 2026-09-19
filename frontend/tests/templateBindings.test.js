/**
 * 模板里引用了 setup 没导出的变量 —— 这类 bug 三道关卡全都放过：
 * vite build 不报错（编译成 `_ctx.xxx`，运行时是 undefined）、ESLint 没有对应规则、
 * 单测不渲染那条分支就看不见。实际踩过的两起：
 * `MistakeListView` 漏解构 `loadError`（错误 UI 永不渲染）、
 * `FormulaView` 用了 `<Icon>` 却没 import（图标静默消失）。
 *
 * 所以这里直接拿 Vue 自己的编译器把 60 个 SFC 全过一遍：
 * 模板表达式里凡是编译成 `_ctx.<标识符>` 的，就是 setup 绑定里没有的名字。
 * （`$attrs` / `$slots` / `$emit` 等实例全局本来就走 `_ctx`，单独放过。）
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src')

function sfcFiles(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name)
    if (statSync(full).isDirectory()) sfcFiles(full, out)
    else if (full.endsWith('.vue')) out.push(full)
  }
  return out
}

/** 编译一个 SFC，返回模板里凡是解析不出来的东西。 */
function analyze(file) {
  const { descriptor, errors } = parse(readFileSync(file, 'utf8'), { filename: file })
  if (errors.length || !descriptor.template) return null
  const script = compileScript(descriptor, { id: file, inlineTemplate: false })
  const { code } = compileTemplate({
    source: descriptor.template.content,
    filename: file,
    id: file,
    compilerOptions: { bindingMetadata: script.bindings || {}, prefixIdentifiers: true },
  })
  const identifiers = new Set()
  for (const m of code.matchAll(/_ctx\.([A-Za-z_$][\w$]*)/g)) {
    if (!m[1].startsWith('$')) identifiers.add(m[1])
  }
  // 组件走 resolveComponent("X")：绑定里没有就落到这里，运行时只 warn 一句就什么都不画
  const components = new Set()
  for (const m of code.matchAll(
    /_resolveComponent\("([A-Za-z][\w]*)"|resolveComponent\("([A-Za-z][\w]*)"/g,
  )) {
    components.add(m[1] || m[2])
  }
  return { identifiers: [...identifiers], components: [...components] }
}

/** Vue 内置与 vue-router 提供的全局组件，不需要 import。 */
const BUILTIN_COMPONENTS = new Set([
  'Teleport',
  'Transition',
  'TransitionGroup',
  'KeepAlive',
  'Suspense',
  'BaseTransition',
  'RouterView',
  'RouterLink',
])

describe('模板标识符必须能在 setup 绑定里找到', () => {
  const files = sfcFiles(SRC)

  it('扫到了足够多的 SFC（防止路径写错导致空跑）', () => {
    expect(files.length).toBeGreaterThanOrEqual(50)
  })

  it('没有任何未解析的模板引用', () => {
    const bad = []
    for (const file of files) {
      const r = analyze(file)
      if (r && r.identifiers.length) {
        bad.push(`${path.relative(SRC, file)} -> ${r.identifiers.join(', ')}`)
      }
    }
    expect(bad).toEqual([])
  })

  it('模板里用到的组件都已 import（全站只注册了 v-reveal 指令，没有全局组件）', () => {
    const bad = []
    for (const file of files) {
      const r = analyze(file)
      if (!r) continue
      const missing = r.components.filter((c) => !BUILTIN_COMPONENTS.has(c))
      if (missing.length) bad.push(`${path.relative(SRC, file)} -> ${missing.join(', ')}`)
    }
    expect(bad).toEqual([])
  })

  it('扫描器本身有效（自检：故意引用一个不存在的变量必须被抓到）', () => {
    const { descriptor } = parse(
      '<script setup>\nconst ok = 1\n</script>\n<template><div>{{ ok }} {{ ghostVar }}<GhostComp /></div></template>',
      { filename: 'probe.vue' },
    )
    const script = compileScript(descriptor, { id: 'probe', inlineTemplate: false })
    const { code } = compileTemplate({
      source: descriptor.template.content,
      filename: 'probe.vue',
      id: 'probe',
      compilerOptions: { bindingMetadata: script.bindings, prefixIdentifiers: true },
    })
    expect(code).toMatch(/_ctx\.ghostVar/)
    expect(code).not.toMatch(/_ctx\.ok\b/)
    expect(code).toMatch(/resolveComponent\("GhostComp"\)/)
  })
})
