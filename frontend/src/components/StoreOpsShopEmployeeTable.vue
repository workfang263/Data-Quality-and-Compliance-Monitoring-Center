<template>
  <el-table
    ref="innerTableRef"
    class="store-ops-employee-table"
    :data="sortedRows"
    row-key="employee_slug"
    border
    stripe
    show-summary
    :summary-method="employeeTableSummary"
    :default-sort="defaultSortConfig"
    @sort-change="onSortChange"
  >
    <el-table-column
      label="员工 Slug"
      min-width="140"
      fixed="left"
      :sortable="false"
    >
      <template #default="{ row }">
        <div class="flex items-center gap-2">
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold"
            :class="avatarClasses(row.employee_slug)"
          >
            {{ initialLetter(row.employee_slug) }}
          </div>
          <span class="text-sm font-semibold text-slate-700">
            {{ row.employee_slug }}
          </span>
        </div>
      </template>
    </el-table-column>
    <el-table-column
      prop="direct_sales"
      label="直接销售额"
      min-width="120"
      sortable="custom"
    >
      <template #default="{ row }">
        <span class="text-sm font-medium text-slate-600">
          ${{ formatMoney(row.direct_sales) }}
        </span>
      </template>
    </el-table-column>
    <el-table-column
      prop="allocated_from_public_pool"
      label="公共池分摊"
      min-width="120"
      sortable="custom"
    >
      <template #default="{ row }">
        <span class="text-sm font-medium text-slate-600">
          ${{ formatMoney(row.allocated_from_public_pool) }}
        </span>
      </template>
    </el-table-column>
    <el-table-column
      prop="total_sales"
      label="合计销售额"
      min-width="130"
      sortable="custom"
    >
      <template #default="{ row }">
        <div
          class="flex items-center gap-1 text-sm font-bold text-slate-900"
        >
          ${{ formatMoney(row.total_sales) }}
          <el-icon
            v-if="row.total_sales > 0"
            class="text-emerald-500"
            :size="14"
          >
            <TopRight />
          </el-icon>
        </div>
      </template>
    </el-table-column>
    <el-table-column
      prop="fb_spend"
      label="广告花费"
      min-width="110"
      sortable="custom"
    >
      <template #default="{ row }">
        <span class="text-sm font-medium text-slate-600">
          ${{ formatMoney(row.fb_spend ?? 0) }}
        </span>
      </template>
    </el-table-column>
    <el-table-column
      prop="roas"
      label="ROAS"
      min-width="88"
      sortable="custom"
    >
      <template #default="{ row }">
        <span class="text-sm font-medium text-slate-600">
          {{
            row.roas === null || row.roas === undefined
              ? '—'
              : formatRoas(row.roas)
          }}
        </span>
      </template>
    </el-table-column>
    <el-table-column
      prop="direct_order_count"
      label="直接订单数"
      min-width="120"
      align="right"
      sortable="custom"
    >
      <template #default="{ row }">
        <span
          class="inline-flex min-w-[1.75rem] items-center justify-center rounded-full px-2.5 py-0.5 text-xs font-bold"
          :class="
            row.direct_order_count > 0
              ? 'bg-emerald-100 text-emerald-700'
              : 'bg-slate-100 text-slate-500'
          "
        >
          {{ row.direct_order_count }}
        </span>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TableColumnCtx, TableInstance } from 'element-plus'
import { TopRight } from '@element-plus/icons-vue'
import type { StoreOpsReportShop } from '../api/storeOps'
import {
  compareRows,
  isSortProp,
  type StoreOpsEmployeeSortRow,
  type StoreOpsSortOrder,
  type StoreOpsSortProp,
} from '../utils/storeOpsSort'

const AVATAR_PALETTES: [string, string][] = [
  ['bg-indigo-100', 'text-indigo-700'],
  ['bg-violet-100', 'text-violet-700'],
  ['bg-sky-100', 'text-sky-700'],
  ['bg-emerald-100', 'text-emerald-700'],
  ['bg-amber-100', 'text-amber-800'],
  ['bg-rose-100', 'text-rose-700'],
]

function slugHue(slug: string): number {
  let h = 0
  for (let i = 0; i < slug.length; i++) {
    h = (h + slug.charCodeAt(i) * (i + 1)) % 997
  }
  return h
}

function avatarClasses(slug: string): string {
  const [bg, fg] = AVATAR_PALETTES[slugHue(slug) % AVATAR_PALETTES.length]!
  return `${bg} ${fg}`
}

function initialLetter(slug: string): string {
  const s = (slug || '?').trim()
  return s ? s.charAt(0).toUpperCase() : '?'
}

function formatMoney(n: number) {
  if (n === undefined || n === null) return '0.00'
  return Number(n).toFixed(2)
}

function formatRoas(n: number) {
  return Number(n).toFixed(2)
}

const props = defineProps<{
  shop: StoreOpsReportShop
  sortProp: StoreOpsSortProp
  sortOrder: StoreOpsSortOrder
}>()

const emit = defineEmits<{
  'sort-change': [
    payload: {
      column: unknown
      prop: string | undefined
      order: string | null
    },
  ]
}>()

const innerTableRef = ref<TableInstance | null>(null)

/** 避免模板内联对象每次渲染新引用，触发 ElTableHeader 无限同步（与 sortProp/order 绑定） */
const defaultSortConfig = computed(() => ({
  prop: props.sortProp,
  order: props.sortOrder,
}))

const sortedRows = computed((): StoreOpsEmployeeSortRow[] => {
  const rows = props.shop?.employee_rows ?? []
  const p = props.sortProp
  const o = props.sortOrder
  if (!rows.length) return []
  if (!isSortProp(p) || !o) return rows as StoreOpsEmployeeSortRow[]
  const copy = [...rows] as StoreOpsEmployeeSortRow[]
  copy.sort((a, b) => compareRows(a, b, p, o))
  return copy
})

/**
 * 表尾汇总行：对当前表格 data（与排序顺序无关，加总不变）按列求和。
 * ROAS 汇总为表级加权：Σ合计销售额 / Σ广告花费（非行 ROAS 平均）；Σ广告花费为 0 时显示「—」。
 */
function employeeTableSummary(param: {
  columns: TableColumnCtx<StoreOpsEmployeeSortRow>[]
  data: StoreOpsEmployeeSortRow[]
}): string[] {
  const { columns, data } = param
  const sums: string[] = []

  for (const column of columns) {
    const prop = column.property as keyof StoreOpsEmployeeSortRow | undefined

    if (!prop) {
      sums.push('汇总')
      continue
    }

    switch (prop) {
      case 'direct_sales':
      case 'allocated_from_public_pool':
      case 'total_sales': {
        const sum = data.reduce(
          (acc, row) => acc + Number(row[prop] ?? 0),
          0,
        )
        sums.push(`$${formatMoney(sum)}`)
        break
      }
      case 'fb_spend': {
        const sum = data.reduce(
          (acc, row) => acc + Number(row.fb_spend ?? 0),
          0,
        )
        sums.push(`$${formatMoney(sum)}`)
        break
      }
      case 'roas': {
        const sumTotal = data.reduce(
          (acc, row) => acc + Number(row.total_sales ?? 0),
          0,
        )
        const sumFb = data.reduce(
          (acc, row) => acc + Number(row.fb_spend ?? 0),
          0,
        )
        if (sumFb > 0) {
          sums.push(formatRoas(sumTotal / sumFb))
        } else {
          sums.push('—')
        }
        break
      }
      case 'direct_order_count': {
        const sum = data.reduce(
          (acc, row) => acc + Number(row.direct_order_count ?? 0),
          0,
        )
        sums.push(String(sum))
        break
      }
      default:
        sums.push('')
    }
  }

  return sums
}

function onSortChange(payload: {
  column: unknown
  prop: string | undefined
  order: string | null
}) {
  emit('sort-change', payload)
}

function applySort(prop: string, order: string) {
  innerTableRef.value?.sort(prop, order)
}

defineExpose({ applySort })
</script>

<style scoped>
.store-ops-employee-table :deep(.el-table__header th) {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgb(100 116 139);
  background-color: rgb(248 250 252 / 0.9);
}

.store-ops-employee-table :deep(.el-table__body td) {
  border-color: rgb(241 245 249);
}

.store-ops-employee-table :deep(.el-table__footer-wrapper td) {
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(15 23 42);
  background-color: rgb(248 250 252 / 0.95);
  border-color: rgb(241 245 249);
}
</style>
