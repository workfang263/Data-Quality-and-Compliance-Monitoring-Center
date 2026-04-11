/**
 * 映射资源操作审计 API
 */
import request from './request'

export interface MappingAuditItem {
  id: number
  action: string
  resource_type: string
  resource_id: string
  owner: string | null
  operator_user_id: number | null
  operator_username: string | null
  request_payload: string | null
  result_status: string
  result_message: string | null
  created_at: string | null
}

export interface MappingAuditListData {
  items: MappingAuditItem[]
  total: number
  limit: number
  offset: number
}

export interface MappingAuditQuery {
  limit?: number
  offset?: number
  resource_type?: string
  action?: string
  result_status?: string
}

export function getMappingResourceAudits(
  params: MappingAuditQuery
): Promise<MappingAuditListData> {
  return request.get<MappingAuditListData>('/audit/mapping-resources', { params })
}
