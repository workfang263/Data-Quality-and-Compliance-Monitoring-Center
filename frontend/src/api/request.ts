/**
 * 【新系统】Vue前端 - HTTP请求封装
 * 统一管理API请求，添加拦截器，统一错误处理
 */
import axios from 'axios'
import type {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios'

type TypedRequest = Omit<
  AxiosInstance,
  'get' | 'post' | 'put' | 'patch' | 'delete'
> & {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
}

// 创建axios实例
const request: AxiosInstance = axios.create({
  baseURL: '/api', // 使用代理，所以使用相对路径
  timeout: 30000, // 请求超时时间（30秒）
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 添加token到请求头
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => {
    // 对请求错误做些什么
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse) => {
    // 对响应数据做点什么
    const res = response.data
    
    // 如果后端返回的数据格式是 { code, message, data }
    // 可以根据code判断是否成功
    if (res.code !== undefined && res.code !== 200) {
      // 如果code不是200，说明请求失败
      console.error('API请求失败:', res.message || '未知错误')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    
    // 返回data字段（如果存在），否则返回整个响应
    return res.data !== undefined ? res.data : res
  },
  (error: AxiosError) => {
    // 对响应错误做点什么
    console.error('响应错误:', error)
    
    // 处理HTTP错误状态码
    if (error.response) {
      const status = error.response.status
      switch (status) {
        case 400:
          console.error('请求参数错误')
          break
        case 401:
          console.error('未授权，请重新登录')
          // 清除token并跳转到登录页
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          // 使用 window.location 跳转，避免循环依赖
          if (window.location.pathname !== '/login') {
            window.location.href = '/login'
          }
          break
        case 403:
          console.error('拒绝访问')
          break
        case 404:
          console.error('请求的资源不存在')
          break
        case 500:
          console.error('服务器内部错误')
          break
        default:
          console.error('请求失败:', error.message)
      }
    } else if (error.request) {
      // 请求已发出，但没有收到响应
      console.error('网络错误，请检查网络连接')
    } else {
      // 在设置请求时发生了一些事情，触发了一个错误
      console.error('请求配置错误:', error.message)
    }
    
    return Promise.reject(error)
  }
)

// 运行时响应拦截器已经把 AxiosResponse 收敛为 res.data，这里同步收窄 TS 类型。
export default request as TypedRequest

