import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import request from '../api/request'

/**
 * 错题列表的导入 / 导出逻辑。
 * @param {object} options
 * @param {Function} options.buildParams 由当前筛选条件构建请求参数（不含分页）
 * @param {Function} [options.onImported] 导入成功后的回调（重新加载列表）
 */
export function useImportExport({ buildParams, onImported }) {
  const fileInput = ref(null)
  const importDialogVisible = ref(false)
  const pendingImport = ref([])
  const importing = ref(false)

  async function exportJson() {
    try {
      const params = buildParams()
      params.page_size = 1000
      const [exportRes, listRes] = await Promise.all([
        request.get('/export'),
        request.get('/mistakes', { params }),
      ])
      const payload = exportRes.data.data
      payload.mistakes = listRes.data.data.items || []
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `考研错题本_${new Date().toISOString().slice(0, 10)}.json`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      ElMessage.error('导出失败')
    }
  }

  async function onImportFile(event) {
    const file = event.target.files[0]
    event.target.value = ''
    if (!file) return
    let parsed
    try {
      parsed = JSON.parse(await file.text())
    } catch (err) {
      ElMessage.error('JSON 文件解析失败')
      return
    }
    const mistakes = Array.isArray(parsed) ? parsed : parsed.mistakes || []
    if (!mistakes.length) {
      ElMessage.warning('文件中没有可导入的错题')
      return
    }
    pendingImport.value = mistakes
    importDialogVisible.value = true
  }

  async function confirmImport() {
    importing.value = true
    try {
      const res = await request.post('/import', { mistakes: pendingImport.value })
      const result = res.data.data
      ElMessage.success(
        `导入完成：成功 ${result.created} 条${result.failed.length ? `，失败 ${result.failed.length} 条` : ''}`,
      )
      importDialogVisible.value = false
      pendingImport.value = []
      if (onImported) onImported()
    } catch (err) {
      // 错误提示由请求拦截器统一处理
    } finally {
      importing.value = false
    }
  }

  return {
    fileInput,
    importDialogVisible,
    pendingImport,
    importing,
    exportJson,
    onImportFile,
    confirmImport,
  }
}
