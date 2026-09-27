// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import axios from 'axios'
import type { AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

// 统一响应体 {code, data, msg}；code !== 0 视为错误
const instance = axios.create({ baseURL: '/api', timeout: 30000 })

// 拦截器已解包为响应体 {code,data,msg}，对外暴露解包后的类型
interface UnwrappedClient {
  get<T = any>(url: string, config?: any): Promise<T>
  post<T = any>(url: string, data?: any, config?: any): Promise<T>
  put<T = any>(url: string, data?: any, config?: any): Promise<T>
  delete<T = any>(url: string, config?: any): Promise<T>
  patch<T = any>(url: string, data?: any, config?: any): Promise<T>
}
const client = instance as unknown as UnwrappedClient

instance.interceptors.request.use((config) => {
  const token = localStorage.getItem('calv_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

instance.interceptors.response.use(
  (resp: AxiosResponse) => {
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code !== 0) {
        ElMessage.error(body.msg || '请求失败')
        return Promise.reject(new Error(body.msg || '请求失败'))
      }
    }
    return body
  },
  (error) => {
    const status = error?.response?.status
    const msg = error?.response?.data?.msg || error?.response?.data?.detail || error.message || '网络错误'
    if (status === 401) {
      localStorage.removeItem('calv_token')
      ElMessage.warning('登录已过期，请重新登录')
      router.push('/login')
    } else {
      ElMessage.error(String(msg))
    }
    return Promise.reject(error)
  }
)

export default client
