import { ref } from 'vue'

import request from '../api/request'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'

/**
 * 错题列表的批量操作：暂停 / 恢复 / 删除 / 修改来源分类。
 * @param {object} options
 * @param {import('vue').Ref<Array>} options.selectedIds 已勾选 id 列表
 * @param {Function} [options.onDone] 操作成功后的回调（重新加载列表）
 */
export function useBulkActions({ selectedIds, onDone }) {
  const batchRunning = ref(false)

  async function bulkAction(action, extra = {}) {
    if (!selectedIds.value.length) return
    batchRunning.value = true
    try {
      await request.post('/mistakes/batch', {
        ids: selectedIds.value,
        action,
        ...extra,
      })
      toast.success('批量操作完成')
      selectedIds.value = []
      if (onDone) onDone()
    } catch (err) {
      // 错误提示由请求拦截器统一处理
    } finally {
      batchRunning.value = false
    }
  }

  function bulkPause() {
    bulkAction('pause')
  }

  function bulkResume() {
    bulkAction('resume')
  }

  async function bulkSetRealExam() {
    const year = await confirmDialog({
      title: '批量设为真题',
      message: '请输入真题年份，如 2025',
      confirmText: '设为真题',
      input: {
        placeholder: '如 2025',
        pattern: /^(19|20)\d{2}$/,
        error: '请输入四位数年份，如 2025',
      },
    })
    if (year === null) return
    await bulkAction('source_type', {
      source_type: 'real_exam',
      source_year: String(year || '').trim(),
    })
  }

  function bulkSetOther() {
    bulkAction('source_type', { source_type: 'other' })
  }

  async function bulkDelete() {
    const ok = await confirmDialog({
      title: '批量删除确认',
      message: `确定删除选中的 ${selectedIds.value.length} 道错题吗？删除后不可恢复。`,
      danger: true,
      confirmText: '删除',
    })
    if (!ok) return
    bulkAction('delete')
  }

  return {
    batchRunning,
    bulkPause,
    bulkResume,
    bulkSetRealExam,
    bulkSetOther,
    bulkDelete,
  }
}
