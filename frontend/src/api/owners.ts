/**
 * 【新系统】前端 - 负责人汇总API调用
 * 提供负责人相关的API调用函数
 */
import request from './request'

/**
 * 负责人汇总数据项
 */
export interface OwnerSummaryItem {
  owner: string
  total_gmv: number
  total_orders: number
  total_visitors: number
  avg_order_value: number
  total_spend: number  // Facebook广告花费
  tt_total_spend: number  // TikTok广告花费
  total_spend_all: number  // 总广告花费
  roas: number | null
  conversion_rate: number
}

/**
 * 负责人小时数据项
 */
export interface OwnerHourlyItem {
  time_hour: string
  total_gmv: number
  total_orders: number
  total_visitors: number
  total_spend: number  // Facebook广告花费
  tt_total_spend: number  // TikTok广告花费
  total_spend_all: number  // 总广告花费
  avg_order_value: number
  roas: number | null
  conversion_rate: number
}

/**
 * 获取负责人汇总数据的参数
 */
export interface GetOwnersSummaryParams {
  start_date: string
  end_date: string
  sort_by?: 'owner' | 'gmv' | 'orders' | 'visitors' | 'aov' | 'spend' | 'roas'
  sort_order?: 'asc' | 'desc'
}

/**
 * 获取负责人小时数据的参数
 */
export interface GetOwnerHourlyParams {
  owner: string
  start_date: string
  end_date: string
}

/**
 * 获取负责人汇总数据
 */
export function getOwnersSummary(params: GetOwnersSummaryParams): Promise<OwnerSummaryItem[]> {
  return request.get<OwnerSummaryItem[]>('/owners/summary', {
    params: {
      start_date: params.start_date,
      end_date: params.end_date,
      sort_by: params.sort_by || 'owner',
      sort_order: params.sort_order || 'asc'
    }
  })
}

/**
 * 获取负责人小时数据
 */
export function getOwnerHourly(params: GetOwnerHourlyParams): Promise<OwnerHourlyItem[]> {
  return request.get<OwnerHourlyItem[]>(`/owners/${encodeURIComponent(params.owner)}/hourly`, {
    params: {
      start_date: params.start_date,
      end_date: params.end_date
    }
  })
}

