<template>
  <PageShell>
    <PageHeaderBar
      title="店铺运营概览"
      subtitle="数据来自店匠同步；金额按北京时间业务日汇总。两店数据分开展示。"
    >
      <template #actions>
        <el-button v-if="canEditConfig" @click="goToConfig">
          配置中心
        </el-button>
        <el-button type="primary" :loading="syncing" @click="handleSync">
          <el-icon class="mr-1"><RefreshRight /></el-icon>
          立即同步
        </el-button>
      </template>
    </PageHeaderBar>

        <section
          class="mb-8 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6"
        >
          <div class="flex flex-wrap items-end gap-4 sm:gap-6">
            <div class="min-w-0 flex-1 space-y-2 sm:flex-initial">
              <label
                class="block text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                日期范围
              </label>
              <div class="store-ops-date-picker">
                <el-date-picker
                  v-model="dateRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  value-format="YYYY-MM-DD"
                  :disabled-date="disabledFuture"
                  @change="loadReport"
                />
              </div>
            </div>
          </div>
        </section>

        <div v-loading="loading" class="min-h-[200px]">
          <div v-if="report" class="grid gap-8">
            <section
              v-for="(shop, idx) in report.shops"
              :key="shop.shop_domain"
              class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
            >
              <div class="border-b border-slate-100 bg-slate-50/50 px-4 py-4 sm:px-6">
                <div
                  class="flex flex-wrap items-center justify-between gap-4"
                >
                  <div class="flex min-w-0 items-center gap-3">
                    <div
                      class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-violet-600 text-white shadow-sm"
                    >
                      <el-icon :size="20"><Shop /></el-icon>
                    </div>
                    <div class="min-w-0">
                      <h2 class="text-lg font-bold text-slate-800">
                        {{ shop.display_name || `店铺 ${idx + 1}` }}
                      </h2>
                      <p
                        class="truncate text-xs font-medium text-slate-500 sm:text-sm"
                      >
                        {{ shop.shop_domain }}
                      </p>
                    </div>
                  </div>
                  <div class="flex flex-wrap items-center gap-4 sm:gap-6">
                    <div class="text-right">
                      <p
                        class="text-[10px] font-bold uppercase tracking-widest text-slate-400"
                      >
                        公共池销售额
                      </p>
                      <p class="text-lg font-bold text-slate-800">
                        ${{ formatMoney(shop.public_pool_sales_total) }}
                      </p>
                    </div>
                    <div class="hidden h-8 w-px bg-slate-200 sm:block" />
                    <div class="text-right">
                      <p
                        class="text-[10px] font-bold uppercase tracking-widest text-slate-400"
                      >
                        公共池订单数
                      </p>
                      <p class="text-lg font-bold text-slate-800">
                        {{ shop.public_pool_order_count }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div class="overflow-x-auto">
                <StoreOpsShopEmployeeTable
                  :ref="(el) => registerStoreOpsTableRef(shop.shop_domain, el)"
                  :shop="shop"
                  :sort-prop="getSortState(shop.shop_domain).prop"
                  :sort-order="getSortState(shop.shop_domain).order"
                  @sort-change="
                    (p) => onSortChange(shop.shop_domain, p)
                  "
                />
              </div>

              <div
                class="border-t border-slate-100 bg-slate-50/40 px-4 py-3 sm:px-6"
              >
                <div
                  class="flex flex-wrap gap-x-10 gap-y-2 text-sm text-slate-800"
                >
                  <div>
                    <span class="text-xs font-semibold text-slate-500">店铺总订单数（含公共池）</span>
                    <span class="ml-2 font-bold text-slate-900">
                      {{ shopGrandOrdersWithPublicPool(shop) }}
                    </span>
                  </div>
                </div>
              </div>

              <div
                class="border-t border-slate-100 bg-slate-50/20 px-4 py-3 text-xs font-medium text-slate-500 sm:px-6 sm:py-4"
              >
                共 {{ (shop.employee_rows ?? []).length }} 名员工
              </div>
            </section>
          </div>

          <div
            v-else-if="!loading"
            class="rounded-2xl border border-dashed border-slate-200 bg-white py-16 text-center text-sm text-slate-500"
          >
            请选择日期范围
          </div>
        </div>
  </PageShell>
</template>

<script setup lang="ts">
import {
  ref,
  onMounted,
  watch,
  nextTick,
  shallowRef,
} from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElNotification } from 'element-plus'
import { RefreshRight, Shop } from '@element-plus/icons-vue'
import PageShell from '../components/PageShell.vue'
import PageHeaderBar from '../components/PageHeaderBar.vue'
import StoreOpsShopEmployeeTable from '../components/StoreOpsShopEmployeeTable.vue'
import { getCurrentUser } from '../api/auth'
import {
  fetchStoreOpsReport,
  triggerStoreOpsSync,
  type StoreOpsReportData,
  type StoreOpsReportShop,
} from '../api/storeOps'
import {
  isSortProp,
  type StoreOpsSortOrder,
  type StoreOpsSortProp,
} from '../utils/storeOpsSort'

const router = useRouter()

function apiErrorMessage(e: unknown): string {
  if (axios.isAxiosError(e) && e.response?.data) {
    const d = e.response.data as { detail?: unknown; message?: string }
    if (typeof d.detail === 'string') return d.detail
    if (Array.isArray(d.detail)) {
      return d.detail
        .map((x: { msg?: string }) => x?.msg)
        .filter(Boolean)
        .join('; ')
    }
    if (d.message) return d.message
  }
  if (e instanceof Error) return e.message
  return '请求失败'
}

const loading = ref(false)
const syncing = ref(false)
const report = ref<StoreOpsReportData | null>(null)
const canEditConfig = ref(false)

/** 按店记忆排序；loadReport 只替换 report，不清空本对象（规格 §2） */
const sortStateByShop = ref<
  Record<string, { prop: StoreOpsSortProp; order: StoreOpsSortOrder }>
>({})

const isSyncingHeader = ref(false)
const headerSyncGeneration = ref(0)

const tableRefByShop = shallowRef<
  Record<string, InstanceType<typeof StoreOpsShopEmployeeTable> | null>
>({})

function registerStoreOpsTableRef(domain: string, el: unknown) {
  if (!domain) return
  const map = tableRefByShop.value
  if (el) {
    const inst = el as InstanceType<typeof StoreOpsShopEmployeeTable>
    if (map[domain] !== inst) {
      map[domain] = inst
    }
  } else if (map[domain]) {
    delete map[domain]
  }
}

function getSortState(domain: string): {
  prop: StoreOpsSortProp
  order: StoreOpsSortOrder
} {
  const s = sortStateByShop.value[domain]
  if (s) return s
  return { prop: 'direct_sales', order: 'descending' }
}

function sameSortState(
  a: { prop: StoreOpsSortProp; order: StoreOpsSortOrder },
  b: { prop: StoreOpsSortProp; order: StoreOpsSortOrder },
): boolean {
  return a.prop === b.prop && a.order === b.order
}

async function onSortChange(
  domain: string,
  payload: {
    column: unknown
    prop: string | undefined
    order: string | null
  },
) {
  if (isSyncingHeader.value) return

  let nextProp: StoreOpsSortProp
  let nextOrder: StoreOpsSortOrder

  if (payload.order === 'ascending' || payload.order === 'descending') {
    nextOrder = payload.order
    nextProp = isSortProp(payload.prop) ? payload.prop : 'direct_sales'
  } else {
    // 第三态：取消排序 → 回退默认列与降序（规格 §8）
    nextProp = 'direct_sales'
    nextOrder = 'descending'
  }

  const next = { prop: nextProp, order: nextOrder }
  if (sameSortState(next, getSortState(domain))) return

  sortStateByShop.value = { ...sortStateByShop.value, [domain]: next }

  // 同一日期内取消排序时 report 不变，watch(report) 不会跑，需单独对齐表头（规格 §8）
  if (payload.order === null) {
    const gen = ++headerSyncGeneration.value
    isSyncingHeader.value = true
    try {
      await nextTick()
      const st = getSortState(domain)
      tableRefByShop.value[domain]?.applySort(st.prop, st.order)
      await nextTick()
      await new Promise<void>((r) => setTimeout(r, 50))
    } finally {
      if (gen === headerSyncGeneration.value) {
        isSyncingHeader.value = false
      }
    }
  }
}

watch(
  () => report.value,
  async (newReport) => {
    if (!newReport?.shops?.length) return
    const gen = ++headerSyncGeneration.value
    isSyncingHeader.value = true
    try {
      await nextTick()
      for (const shop of newReport.shops) {
        const domain = shop.shop_domain
        const st = getSortState(domain)
        tableRefByShop.value[domain]?.applySort(st.prop, st.order)
      }
      await nextTick()
      await new Promise<void>((r) => setTimeout(r, 50))
    } finally {
      if (gen === headerSyncGeneration.value) {
        isSyncingHeader.value = false
      }
    }
  },
  { flush: 'post' },
)

const today = () => {
  const d = new Date()
  const z = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`
}

const dateRange = ref<[string, string]>([today(), today()])

const disabledFuture = (d: Date) => d.getTime() > Date.now()

function formatMoney(n: number) {
  if (n === undefined || n === null) return '0.00'
  return Number(n).toFixed(2)
}

function sumEmployeeDirectOrders(shop: StoreOpsReportShop): number {
  return (shop.employee_rows ?? []).reduce(
    (acc, row) => acc + Number(row.direct_order_count ?? 0),
    0,
  )
}

/** 公共池订单数 + 各员工直接订单数之和（按店） */
function shopGrandOrdersWithPublicPool(shop: StoreOpsReportShop): number {
  return (
    Number(shop.public_pool_order_count ?? 0) + sumEmployeeDirectOrders(shop)
  )
}

const loadReport = async () => {
  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择日期范围')
    return
  }
  const [start, end] = dateRange.value
  loading.value = true
  try {
    report.value = await fetchStoreOpsReport(start, end)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载失败'
    ElMessage.error(msg)
    report.value = null
  } finally {
    loading.value = false
  }
}

const handleSync = async () => {
  syncing.value = true
  try {
    const data = await triggerStoreOpsSync()
    ElNotification({
      title: '同步任务已提交',
      message: `批次 ${data.sync_run_id}。后台执行中，报表将按当前日期范围自动更新；排障请查 store_ops_sync_runs 或后端日志。`,
      type: 'success',
      duration: 10000,
    })
    void loadReport()
  } catch (e: unknown) {
    ElNotification({
      title: '同步请求失败',
      message: apiErrorMessage(e),
      type: 'error',
      duration: 10000,
    })
  } finally {
    syncing.value = false
  }
}

async function loadCurrentUser() {
  try {
    const user = await getCurrentUser()
    canEditConfig.value =
      user.role === 'admin' || user.can_edit_store_ops_config === true
  } catch {
    canEditConfig.value = false
  }
}

function goToConfig() {
  void router.push('/store-ops/edit')
}

onMounted(() => {
  void loadCurrentUser()
  void loadReport()
})
</script>

<style scoped>
.store-ops-date-picker :deep(.el-date-editor) {
  width: 100%;
  max-width: 20rem;
}

@media (min-width: 640px) {
  .store-ops-date-picker :deep(.el-date-editor) {
    max-width: 22rem;
  }
}

.store-ops-date-picker :deep(.el-input__wrapper) {
  border-radius: 0.5rem;
  border: 1px solid rgb(226 232 240);
  background-color: rgb(248 250 252);
  box-shadow: none;
}

.store-ops-date-picker :deep(.el-input__wrapper:hover) {
  border-color: rgb(203 213 225);
}

.store-ops-date-picker :deep(.el-input__wrapper.is-focus) {
  border-color: rgb(99 102 241);
  box-shadow: 0 0 0 2px rgb(199 210 254 / 0.5);
}
</style>
