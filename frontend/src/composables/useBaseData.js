import { reactive } from 'vue'

import request from '../api/request'

export const baseData = reactive({
  subjects: [],
  subSubjects: [],
  subjectMap: {},
  subSubjectMap: {},
})

// 模块级加载缓存：Layout 与 PracticeView 等重复调用时只发一次请求
let loadPromise = null

export function loadBaseData() {
  if (!loadPromise) {
    loadPromise = (async () => {
      try {
        const [subjectRes, subSubjectRes] = await Promise.all([
          request.get('/subjects'),
          request.get('/sub_subjects'),
        ])
        baseData.subjects = subjectRes.data.data || []
        baseData.subSubjects = subSubjectRes.data.data || []
        baseData.subjectMap = {}
        baseData.subSubjectMap = {}
        baseData.subjects.forEach((item) => {
          baseData.subjectMap[item.id] = item.name
        })
        baseData.subSubjects.forEach((item) => {
          baseData.subSubjectMap[item.id] = item.name
        })
      } catch (err) {
        // 错误提示由请求拦截器统一处理；失败后允许下次重试
        loadPromise = null
      }
    })()
  }
  return loadPromise
}

export function subjectName(id) {
  return baseData.subjectMap[id] || '通用'
}

export function subSubjectName(id) {
  return baseData.subSubjectMap[id] || ''
}

/** 科目类型（math/english/politics/cs/generic），驱动按科目定制的题型与交互。 */
export function subjectKind(id) {
  const subject = baseData.subjects.find((item) => item.id === id)
  return subject?.kind || ''
}

export function subjectColor(id) {
  return {
    1: '#b0392e',
    2: '#b45309',
    3: '#1a7f42',
    4: '#2f6db3',
  }[id] || '#8f887c'
}

export const sourceTypes = [
  { value: 'real_exam', label: '真题', color: '#a16207' },
  { value: 'mock', label: '模拟题', color: '#6d5bd0' },
  { value: 'other', label: '自编/其他', color: '#8f887c' },
]

export function sourceTypeName(type) {
  if (type === 'self') type = 'other'
  return sourceTypes.find((item) => item.value === type)?.label || '其他'
}

export function sourceTypeColor(type) {
  if (type === 'self') type = 'other'
  return sourceTypes.find((item) => item.value === type)?.color || '#8f887c'
}

export function questionTypeName(type) {
  return {
    choice: '选择题',
    multi: '多选题',
    fill: '填空题',
    translation: '翻译',
    solution: '解答题',
  }[type] || '选择题'
}

export function questionTypeColor(type) {
  return {
    choice: '#2f6db3',
    multi: '#6d5bd0',
    fill: '#1a7f42',
    translation: '#0e7568',
    solution: '#b45309',
  }[type] || '#8f887c'
}

/**
 * 按科目类型返回可选题型（存储值与全局题型枚举一致）。
 * politics: 单选/多选/分析题；english: 客观题/翻译/作文；其余: 选择/填空/解答。
 */
export function questionTypesForKind(kind) {
  if (kind === 'politics') {
    return [
      { value: 'choice', label: '单选题' },
      { value: 'multi', label: '多选题' },
      { value: 'solution', label: '分析题' },
    ]
  }
  if (kind === 'english') {
    return [
      { value: 'choice', label: '客观题' },
      { value: 'translation', label: '翻译' },
      { value: 'solution', label: '作文/简答' },
    ]
  }
  return [
    { value: 'choice', label: '选择题' },
    { value: 'fill', label: '填空题' },
    { value: 'solution', label: '解答题' },
  ]
}

/** 按科目类型返回常用错因/思路快选。 */
export function approachPresetsForKind(kind) {
  if (kind === 'english') {
    return ['词汇不识', '长难句误读', '定位错误', '过度推断', '固定搭配', '粗心看错']
  }
  if (kind === 'politics') {
    return ['知识点未记牢', '干扰项混淆', '多选漏选', '时政盲区', '审题失误', '概念混淆']
  }
  return []
}

export function formatTime(value) {
  if (!value) return ''
  const date = new Date(String(value).replace(' ', 'T') + 'Z')
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

export function truncate(text, length) {
  const value = String(text || '')
  return value.length > length ? `${value.slice(0, length)}...` : value
}
