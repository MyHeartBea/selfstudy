import { reactive } from 'vue'

import request from '../api/request'

export const baseData = reactive({
  subjects: [],
  subSubjects: [],
  subjectMap: {},
  subSubjectMap: {},
})

export async function loadBaseData() {
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
    // 错误提示由请求拦截器统一处理
  }
}

export function subjectName(id) {
  return baseData.subjectMap[id] || '通用'
}

export function subSubjectName(id) {
  return baseData.subSubjectMap[id] || ''
}

export function subjectColor(id) {
  return {
    1: '#c0392b',
    2: '#d97706',
    3: '#2e7d32',
    4: '#1f5aa8',
  }[id] || '#64748b'
}

export const sourceTypes = [
  { value: 'real_exam', label: '真题', color: '#b7791f' },
  { value: 'mock', label: '模拟题', color: '#7c5bb0' },
  { value: 'other', label: '自编/其他', color: '#64748b' },
]

export function sourceTypeName(type) {
  if (type === 'self') type = 'other'
  return sourceTypes.find((item) => item.value === type)?.label || '其他'
}

export function sourceTypeColor(type) {
  if (type === 'self') type = 'other'
  return sourceTypes.find((item) => item.value === type)?.color || '#64748b'
}

export function questionTypeName(type) {
  return {
    choice: '选择题',
    fill: '填空题',
    solution: '解答题',
  }[type] || '选择题'
}

export function questionTypeColor(type) {
  return {
    choice: '#1f5aa8',
    fill: '#2e7d32',
    solution: '#b45309',
  }[type] || '#64748b'
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
