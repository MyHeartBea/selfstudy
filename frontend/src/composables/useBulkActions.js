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
      const res = await request.post('/mistakes/batch', {
        ids: selectedIds.value,
        action,
        ...extra,
      })
      // 后端在快照失败时把降级写在 message 里；这里必须用它，
      // 写死"批量操作完成"会让"本次无法一键回滚"这句话永远到不了用户眼前。
      const snapshot = res.data?.data?.snapshot
      if (action === 'delete' && !snapshot) {
        toast.warning(res.data?.message || '批量删除完成，但本次快照失败，无法一键回滚')
      } else {
        toast.success(res.data?.message || '批量操作完成')
      }
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
      // 不说"不可恢复"：删之前后端会打一份整库快照，「数据备份」页能回滚；
      // 但快照不含图片文件，配图删了就是真没了，这句必须留在确认框里。
      message: `确定删除选中的 ${selectedIds.value.length} 道错题吗？数据可整库回滚（「数据备份」页），配图文件会一并删除且回滚找不回来。`,
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
