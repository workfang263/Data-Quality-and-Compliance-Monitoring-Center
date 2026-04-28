/**
 * 【新系统】前端 - 权限管理API调用
 * 提供权限管理相关的API调用函数（仅管理员可访问）
 */
import request from './request'

/**
 * 用户信息（用于权限管理）
 */
export interface PermissionUser {
  id: number
  username: string
  role: string
  can_view_dashboard?: boolean
  can_edit_mappings?: boolean
  can_view_store_ops?: boolean
  can_edit_store_ops_config?: boolean
}

/**
 * 扩展权限
 */
export interface ExtendedPermissions {
  can_view_dashboard: boolean
  can_edit_mappings: boolean
  can_view_store_ops: boolean
  can_edit_store_ops_config: boolean
}

/**
 * 获取所有用户列表
 */
export function getUsers(): Promise<PermissionUser[]> {
  return request.get<PermissionUser[]>('/permissions/users')
}

/**
 * 获取所有负责人列表
 */
export function getOwners(): Promise<string[]> {
  return request.get<string[]>('/permissions/owners')
}

/**
 * 获取指定用户的授权列表
 */
export function getUserPermissions(userId: number): Promise<string[]> {
  return request.get<string[]>(`/permissions/users/${userId}/owners`)
}

/**
 * 获取指定用户的扩展权限
 */
export function getUserExtendedPermissions(userId: number): Promise<ExtendedPermissions> {
  return request.get<ExtendedPermissions>(`/permissions/users/${userId}/extended`)
}

/**
 * 更新指定用户的权限
 */
export interface UpdatePermissionsParams {
  owners: string[]
  can_view_dashboard?: boolean
  can_edit_mappings?: boolean
  can_view_store_ops?: boolean
  can_edit_store_ops_config?: boolean
}

export function updateUserPermissions(
  userId: number,
  params: UpdatePermissionsParams
): Promise<void> {
  return request.put<void>(`/permissions/users/${userId}/owners`, params)
}

