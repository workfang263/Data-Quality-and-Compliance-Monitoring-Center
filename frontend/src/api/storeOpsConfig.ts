import request from './request'

export interface StoreOpsShopItem {
  id: number
  shop_domain: string
  is_enabled: number
  created_at?: string | null
  updated_at?: string | null
}

export interface StoreOpsAvailableShopItem {
  shop_domain: string
  owner?: string | null
  already_bound?: boolean
}

export interface StoreOpsAdAccountItem {
  id: number
  shop_domain: string
  ad_account_id: string
  is_enabled: number
  created_at?: string | null
  updated_at?: string | null
}

export interface StoreOpsAvailableAdAccountItem {
  ad_account_id: string
  owner?: string | null
  bound_shop_domain?: string | null
  already_bound?: boolean
}

export type StoreOpsOperatorStatus = 'active' | 'blocked'

export interface StoreOpsOperatorItem {
  id: number
  employee_slug: string
  display_name: string
  utm_keyword: string
  campaign_keyword: string
  status: StoreOpsOperatorStatus
  sort_order: number
  deleted_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type StoreOpsAuditResourceType = 'shop' | 'ad_whitelist' | 'operator'
export type StoreOpsAuditAction =
  | 'create'
  | 'update'
  | 'delete'
  | 'enable'
  | 'disable'
  | 'block'
  | 'unblock'

export interface StoreOpsAuditPayload {
  before?: Record<string, unknown>
  after?: Record<string, unknown>
  changes?: Record<string, unknown>
}

export interface StoreOpsAuditItem {
  id: number
  resource_type: StoreOpsAuditResourceType
  resource_key: string
  action: StoreOpsAuditAction
  actor_user_id?: number | null
  actor_username?: string | null
  request_payload?: StoreOpsAuditPayload
  result_status?: string | null
  result_message?: string | null
  created_at: string
}

export interface StoreOpsAuditListData {
  total: number
  limit: number
  offset: number
  items: StoreOpsAuditItem[]
}

export function fetchStoreOpsConfigShops(): Promise<StoreOpsShopItem[]> {
  return request.get<StoreOpsShopItem[]>('/store-ops/config/shops')
}

export function fetchStoreOpsAvailableShops(): Promise<StoreOpsAvailableShopItem[]> {
  return request.get<StoreOpsAvailableShopItem[]>('/store-ops/config/available-shops')
}

export function createStoreOpsShop(shopDomain: string): Promise<StoreOpsShopItem> {
  return request.post<StoreOpsShopItem>('/store-ops/config/shops', {
    shop_domain: shopDomain,
  })
}

export function patchStoreOpsShop(
  shopId: number,
  payload: { is_enabled: boolean },
): Promise<StoreOpsShopItem & { changed?: boolean }> {
  return request.patch<StoreOpsShopItem & { changed?: boolean }>(
    `/store-ops/config/shops/${shopId}`,
    payload,
  )
}

export function deleteStoreOpsShop(
  shopId: number,
): Promise<StoreOpsShopItem & { changed?: boolean }> {
  return request.delete<StoreOpsShopItem & { changed?: boolean }>(
    `/store-ops/config/shops/${shopId}`,
  )
}

export function fetchStoreOpsConfigAdAccounts(
  shopDomain?: string,
): Promise<StoreOpsAdAccountItem[]> {
  return request.get<StoreOpsAdAccountItem[]>('/store-ops/config/ad-accounts', {
    params: {
      shop_domain: shopDomain || undefined,
    },
  })
}

export function fetchStoreOpsAvailableAdAccounts(): Promise<
  StoreOpsAvailableAdAccountItem[]
> {
  return request.get<StoreOpsAvailableAdAccountItem[]>(
    '/store-ops/config/available-ad-accounts',
  )
}

export function createStoreOpsAdAccount(payload: {
  shop_domain: string
  ad_account_id: string
}): Promise<StoreOpsAdAccountItem> {
  return request.post<StoreOpsAdAccountItem>('/store-ops/config/ad-accounts', payload)
}

export function patchStoreOpsAdAccount(
  adAccountId: number,
  payload: { is_enabled?: boolean; shop_domain?: string },
): Promise<StoreOpsAdAccountItem & { changed?: boolean }> {
  return request.patch<StoreOpsAdAccountItem & { changed?: boolean }>(
    `/store-ops/config/ad-accounts/${adAccountId}`,
    payload,
  )
}

export function deleteStoreOpsAdAccount(
  adAccountId: number,
): Promise<StoreOpsAdAccountItem & { changed?: boolean }> {
  return request.delete<StoreOpsAdAccountItem & { changed?: boolean }>(
    `/store-ops/config/ad-accounts/${adAccountId}`,
  )
}

export function fetchStoreOpsOperators(params?: {
  include_deleted?: boolean
  status?: StoreOpsOperatorStatus
}): Promise<StoreOpsOperatorItem[]> {
  return request.get<StoreOpsOperatorItem[]>('/store-ops/config/operators', {
    params: {
      include_deleted: params?.include_deleted,
      status: params?.status,
    },
  })
}

export function createStoreOpsOperator(payload: {
  employee_slug: string
  display_name?: string
  utm_keyword?: string
  campaign_keyword?: string
  sort_order?: number
}): Promise<StoreOpsOperatorItem> {
  return request.post<StoreOpsOperatorItem>('/store-ops/config/operators', payload)
}

export function patchStoreOpsOperator(
  operatorId: number,
  payload: {
    display_name?: string
    utm_keyword?: string
    campaign_keyword?: string
    sort_order?: number
    operator_status?: StoreOpsOperatorStatus
  },
): Promise<StoreOpsOperatorItem & { changed?: boolean }> {
  return request.patch<StoreOpsOperatorItem & { changed?: boolean }>(
    `/store-ops/config/operators/${operatorId}`,
    payload,
  )
}

export function deleteStoreOpsOperator(
  operatorId: number,
): Promise<StoreOpsOperatorItem & { changed?: boolean }> {
  return request.delete<StoreOpsOperatorItem & { changed?: boolean }>(
    `/store-ops/config/operators/${operatorId}`,
  )
}

export function fetchStoreOpsConfigAudit(params?: {
  resource_type?: StoreOpsAuditResourceType
  action?: StoreOpsAuditAction
  resource_key?: string
  limit?: number
  offset?: number
}): Promise<StoreOpsAuditListData> {
  return request.get<StoreOpsAuditListData>('/store-ops/config/audit', {
    params: {
      resource_type: params?.resource_type,
      action: params?.action,
      resource_key: params?.resource_key,
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    },
  })
}
