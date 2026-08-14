import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import request from '../api/request'

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
      ElMessage.success('批量操作完成')
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
    try {
      const promptResult = await ElMessageBox.prompt(
        '请输入真题年份，如 2025',
        '批量设为真题',
        {
          inputPattern: /^(19|20)\d{2}$/,
          inputErrorMessage: '请输入四位数年份，如 2025',
        },
      )
      await bulkAction('source_type', {
        source_type: 'real_exam',
        source_year: String(promptResult.value || '').trim(),
      })
    } catch (err) {
      // 用户取消
    }
  }

  function bulkSetOther() {
    bulkAction('source_type', { source_type: 'other' })
  }

  async function bulkDelete() {
    try {
      await ElMessageBox.confirm(
        `确定删除选中的 ${selectedIds.value.length} 道错题吗？删除后不可恢复。`,
        '批量删除确认',
        {
          type: 'warning',
          confirmButtonText: '删除',
          cancelButtonText: '取消',
        },
      )
    } catch (err) {
      return
    }
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
