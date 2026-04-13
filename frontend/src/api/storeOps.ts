/**
 * 店铺运营 / 员工归因 API
 */
import request from './request'

export interface StoreOpsReportShop {
  shop_domain: string
  public_pool_sales_total: number
  public_pool_order_count: number
  employee_rows: Array<{
    employee_slug: string
    direct_sales: number
    allocated_from_public_pool: number
    total_sales: number
    direct_order_count: number
    /** Facebook 广告花费（USD，店铺运营配置的账户汇总） */
    fb_spend: number
    /** 倍数 total_sales/fb_spend；无花费时为 null，前端显示 — */
    roas: number | null
  }>
}

export interface StoreOpsReportData {
  date_start: string
  date_end: string
  shops: StoreOpsReportShop[]
}

export function fetchStoreOpsReport(
  startDate: string,
  endDate: string,
  shopDomain?: string
): Promise<StoreOpsReportData> {
  return request.get<StoreOpsReportData>('/store-ops/report', {
    params: {
      start_date: startDate,
      end_date: endDate,
      shop_domain: shopDomain || undefined
    }
  })
}

export interface SyncAcceptedData {
  status: string
  sync_run_id: string
  message: string
}

export function triggerStoreOpsSync(): Promise<SyncAcceptedData> {
  return request.post<SyncAcceptedData>('/internal/store-ops/sync', {})
}

/** 与后端 store_ops_sync_runs 对应的单次同步结果 */
export interface StoreOpsSyncRunDetail {
  sync_run_id: string
  status: 'running' | 'success' | 'partial' | 'failed'
  shops: string[] | null
  biz_dates: string[] | null
  orders_seen: number
  orders_upserted_paid: number
  orders_skipped_not_paid: number
  error_count: number
  errors: string[] | null
  per_shop: Array<{
    shop_domain: string
    orders_seen: number
    orders_upserted_paid: number
    orders_skipped_not_paid: number
    error_count: number
    errors: string[]
  }> | null
  exception_message: string | null
  started_at: string | null
  finished_at: string | null
}

export function fetchStoreOpsSyncRun(
  syncRunId: string
): Promise<StoreOpsSyncRunDetail> {
  return request.get<StoreOpsSyncRunDetail>(
    `/store-ops/sync-run/${encodeURIComponent(syncRunId)}`
  )
}

export function fetchStoreOpsSyncRunsList(
  limit = 20
): Promise<{ items: StoreOpsSyncRunDetail[] }> {
  return request.get<{ items: StoreOpsSyncRunDetail[] }>('/store-ops/sync-runs', {
    params: { limit }
  })
}
