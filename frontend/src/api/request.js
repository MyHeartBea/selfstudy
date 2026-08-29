import axios from 'axios'

import { toast } from '../ui/toast'

const request = axios.create({
  baseURL: '/api',
  timeout: 120000,
  // 数组参数序列化为重复键（difficulty=3&difficulty=4），与 FastAPI Query(List[int]) 契约一致
  paramsSerializer: { indexes: null },
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    // 在 error 上附加 HTTP 状态码，供页面按需分支（如 502 提示 AI 未配置）
    error.status = error.response?.status
    const silent = error.config?.silent === true
    if (!silent) {
      const message = error.response?.data?.message || error.message || '请求失败'
      toast.error(message)
    }
    return Promise.reject(error)
  },
)

export default request
