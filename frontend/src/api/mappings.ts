/**
 * 【新系统】前端 - 映射编辑API调用
 * 提供映射相关的API调用函数
 */
import request from './request'

/**
 * 店铺映射项
 */
export interface StoreMapping {
  id: number
  shop_domain: string
  owner: string
  created_at: string | null
  updated_at: string | null
}

/**
 * 广告账户映射项
 */
export interface AdAccountMapping {
  id: number
  ad_account_id: string
  owner: string
  created_at: string | null
  updated_at: string | null
}

/**
 * 更新映射的参数
 */
export interface UpdateMappingParams {
  owner: string
}

/**
 * 更新映射的响应
 */
export interface UpdateMappingResponse {
  id: number
  shop_domain?: string
  ad_account_id?: string
  owner: string
  affected_dates_count: number
}

/**
 * 获取店铺映射列表
 */
export function getStoreMappings(): Promise<StoreMapping[]> {
  return request.get<StoreMapping[]>('/mappings/stores')
}

/**
 * 获取Facebook广告账户映射列表
 */
export function getFacebookMappings(): Promise<AdAccountMapping[]> {
  return request.get<AdAccountMapping[]>('/mappings/facebook')
}

/**
 * 获取TikTok广告账户映射列表
 */
export function getTikTokMappings(): Promise<AdAccountMapping[]> {
  return request.get<AdAccountMapping[]>('/mappings/tiktok')
}

/** GET 负责人联想（三表去重，需映射编辑权限） */
export function getOwnerSuggestions(q?: string, limit?: number): Promise<string[]> {
  return request.get<string[]>('/mappings/owners/suggestions', {
    params: { q: q ?? '', limit: limit ?? 40 }
  })
}

/**
 * 更新店铺映射
 */
export function updateStoreMapping(id: number, owner: string): Promise<UpdateMappingResponse> {
  return request.put<UpdateMappingResponse>(`/mappings/stores/${id}`, { owner })
}

/**
 * 更新Facebook广告账户映射
 */
export function updateFacebookMapping(id: number, owner: string): Promise<UpdateMappingResponse> {
  return request.put<UpdateMappingResponse>(`/mappings/facebook/${id}`, { owner })
}

/**
 * 更新TikTok广告账户映射
 */
export function updateTikTokMapping(id: number, owner: string): Promise<UpdateMappingResponse> {
  return request.put<UpdateMappingResponse>(`/mappings/tiktok/${id}`, { owner })
}

/** POST 创建/更新店铺映射 */
export interface CreateStoreMappingResponse {
  shop_domain: string
  owner: string
  is_active: boolean
}

export function createStoreMapping(payload: {
  shop_domain: string
  owner: string
  access_token: string
  is_active: boolean
}): Promise<CreateStoreMappingResponse> {
  return request.post<CreateStoreMappingResponse>('/mappings/stores', payload)
}

/** 时区拉取结果（FB/TT 新增接口返回） */
export interface TimezoneSyncPayload {
  ok: boolean
  platform?: string
  ad_account_id?: string
  message?: string
  timezone?: string
  timezone_offset?: number
}

export interface CreateAdMappingResponse {
  ad_account_id: string
  owner: string
  timezone_sync: TimezoneSyncPayload
}

export function createFacebookMapping(payload: {
  ad_account_id: string
  owner: string
}): Promise<CreateAdMappingResponse> {
  return request.post<CreateAdMappingResponse>('/mappings/facebook', payload)
}

export function createTikTokMapping(payload: {
  ad_account_id: string
  owner: string
}): Promise<CreateAdMappingResponse> {
  return request.post<CreateAdMappingResponse>('/mappings/tiktok', payload)
}

