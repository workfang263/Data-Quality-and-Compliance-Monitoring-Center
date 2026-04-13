/**
 * 店铺运营员工表：可排序列与行比较（与 StoreOps 报表行字段一致）
 */

export const SORT_PROPS = [
  'direct_sales',
  'allocated_from_public_pool',
  'total_sales',
  'fb_spend',
  'roas',
  'direct_order_count',
] as const

export type StoreOpsSortProp = (typeof SORT_PROPS)[number]

export type StoreOpsSortOrder = 'ascending' | 'descending'

export function isSortProp(p: string | undefined | null): p is StoreOpsSortProp {
  return !!p && (SORT_PROPS as readonly string[]).includes(p)
}

/** ROAS 排序：null/undefined 视为负无穷，升序时在最上、降序时在最下 */
export function normalizeRoasForSort(v: number | null | undefined): number {
  if (v === null || v === undefined) return Number.NEGATIVE_INFINITY
  return Number(v)
}

export interface StoreOpsEmployeeSortRow {
  employee_slug: string
  direct_sales: number
  allocated_from_public_pool: number
  total_sales: number
  direct_order_count: number
  fb_spend: number
  roas: number | null
}

function primaryValue(
  row: StoreOpsEmployeeSortRow,
  prop: StoreOpsSortProp,
): number {
  if (prop === 'roas') return normalizeRoasForSort(row.roas)
  const v = row[prop as keyof StoreOpsEmployeeSortRow]
  if (typeof v === 'number') return v
  return Number(v ?? 0)
}

/**
 * 先按当前指标比较，相等时按 employee_slug 升序（第二关键字）
 */
export function compareRows(
  a: StoreOpsEmployeeSortRow,
  b: StoreOpsEmployeeSortRow,
  prop: StoreOpsSortProp,
  order: StoreOpsSortOrder,
): number {
  const va = primaryValue(a, prop)
  const vb = primaryValue(b, prop)
  let cmp = 0
  if (va < vb) cmp = -1
  else if (va > vb) cmp = 1
  else {
    cmp = a.employee_slug.localeCompare(b.employee_slug)
  }
  return order === 'ascending' ? cmp : -cmp
}
