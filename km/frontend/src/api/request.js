import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api',
  timeout: 120000,
  // 数组参数序列化为重复键（difficulty=3&difficulty=4），与 FastAPI Query(List[int]) 契约一致
  paramsSerializer: { indexes: null },
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.message || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default request
