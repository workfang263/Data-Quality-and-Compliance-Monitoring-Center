/**
 * 【新系统】Vue前端 - 看板数据API
 * 封装看板相关的API调用
 */
import request from './request'
import type { AxiosResponse } from 'axios'

// 看板数据项类型定义
export interface DashboardDataItem {
  time_hour: string // ISO 8601格式的时间字符串
  total_gmv: number // 总销售额
  total_orders: number // 总订单数
  total_visitors: number // 总访客数
  total_spend: number // 总广告花费
  avg_order_value: number // 平均客单价
}

// 获取看板数据的参数类型
export interface GetDashboardDataParams {
  shop_domain?: string // 店铺域名，不传或传"ALL_STORES"表示总店铺
  start_date: string // 开始日期，格式：YYYY-MM-DD
  end_date: string // 结束日期，格式：YYYY-MM-DD
  granularity?: 'hour' | 'day' // 粒度，可选值：hour（小时）、day（天），默认：hour
  start_hour?: number // 开始小时（0-23），用于日内时段筛选
  end_hour?: number // 结束小时（0-23），用于日内时段筛选
}

/**
 * 获取看板数据（折线图数据）
 * @param params 查询参数
 * @returns 看板数据数组
 */
export function getDashboardData(params: GetDashboardDataParams): Promise<DashboardDataItem[]> {
  return request.get<DashboardDataItem[]>('/dashboard/data', {
    params: {
      shop_domain: params.shop_domain || 'ALL_STORES',
      start_date: params.start_date,
      end_date: params.end_date,
      granularity: params.granularity || 'hour',
      start_hour: params.start_hour,
      end_hour: params.end_hour
    }
  })
}



