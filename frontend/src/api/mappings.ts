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



