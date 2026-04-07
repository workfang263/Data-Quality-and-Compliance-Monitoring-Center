/**
 * 【新系统】前端 - 用户认证API调用
 * 提供登录、登出、获取当前用户信息等API调用函数
 */
import request from './request'

/**
 * 用户信息
 */
export interface UserInfo {
  id: number
  username: string
  role: string
  can_view_dashboard?: boolean
  can_edit_mappings?: boolean
  can_view_store_ops?: boolean
}

/**
 * 登录参数
 */
export interface LoginParams {
  username: string
  password: string
  remember_me?: boolean
}

/**
 * 注册参数
 */
export interface RegisterParams {
  username: string
  password: string
  confirm_password: string
}

/**
 * 登录响应
 */
export interface LoginResponse {
  token: string
  user: UserInfo
}

/**
 * 用户登录
 */
export function login(params: LoginParams): Promise<LoginResponse> {
  return request.post<LoginResponse>('/auth/login', {
    username: params.username,
    password: params.password,
    remember_me: params.remember_me || false
  })
}

/**
 * 用户登出
 */
export function logout(): Promise<void> {
  return request.post<void>('/auth/logout')
}

/**
 * 用户注册
 */
export function register(params: RegisterParams): Promise<{ user: UserInfo }> {
  return request.post<{ user: UserInfo }>('/auth/register', {
    username: params.username,
    password: params.password,
    confirm_password: params.confirm_password
  })
}

/**
 * 获取当前用户信息
 */
export function getCurrentUser(): Promise<UserInfo> {
  return request.get<UserInfo>('/auth/me')
}

