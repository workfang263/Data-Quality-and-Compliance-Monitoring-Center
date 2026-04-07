<template>
  <div class="min-h-screen bg-[#F8FAFC] font-sans text-slate-900 antialiased">
    <main class="mx-auto max-w-7xl">
      <header
        class="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white/80 px-4 backdrop-blur-md sm:px-8"
      >
        <h1 class="text-xl font-semibold text-slate-800">店铺运营概览</h1>
      </header>

      <div class="p-4 sm:p-8">
        <p class="mb-6 text-sm leading-relaxed text-slate-500">
          数据来自店匠同步；金额按北京时间业务日汇总。两店数据分开展示。
        </p>

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
            <button
              type="button"
              class="flex h-10 shrink-0 items-center gap-2 rounded-lg border border-slate-200 bg-white px-5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 sm:px-6"
              :disabled="syncing"
              @click="handleSync"
            >
              <el-icon class="text-base" :class="{ 'animate-spin': syncing }">
                <RefreshRight />
              </el-icon>
              立即同步
            </button>
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
                        店铺 {{ idx + 1 }}
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
                <table class="w-full border-collapse text-left">
                  <thead>
                    <tr class="border-b border-slate-100 bg-slate-50/30">
                      <th
                        class="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-500 sm:px-6 sm:py-4"
                      >
                        员工 Slug
                      </th>
                      <th
                        class="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-500 sm:px-6 sm:py-4"
                      >
                        直接销售额
                      </th>
                      <th
                        class="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-500 sm:px-6 sm:py-4"
                      >
                        公共池分摊
                      </th>
                      <th
                        class="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-500 sm:px-6 sm:py-4"
                      >
                        合计销售额
                      </th>
                      <th
                        class="px-4 py-3 text-right text-xs font-bold uppercase tracking-wider text-slate-500 sm:px-6 sm:py-4"
                      >
                        直接订单数
                      </th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-100">
                    <tr
                      v-for="row in shop.employee_rows"
                      :key="row.employee_slug"
                      class="transition-colors hover:bg-slate-50/80"
                    >
                      <td class="px-4 py-3 sm:px-6 sm:py-4">
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
                      </td>
                      <td
                        class="px-4 py-3 text-sm font-medium text-slate-600 sm:px-6 sm:py-4"
                      >
                        ${{ formatMoney(row.direct_sales) }}
                      </td>
                      <td
                        class="px-4 py-3 text-sm font-medium text-slate-600 sm:px-6 sm:py-4"
                      >
                        ${{ formatMoney(row.allocated_from_public_pool) }}
                      </td>
                      <td class="px-4 py-3 sm:px-6 sm:py-4">
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
                      </td>
                      <td class="px-4 py-3 text-right sm:px-6 sm:py-4">
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
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div
                class="border-t border-slate-100 bg-slate-50/20 px-4 py-3 text-xs font-medium text-slate-500 sm:px-6 sm:py-4"
              >
                共 {{ shop.employee_rows.length }} 名员工
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
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElNotification } from 'element-plus'
import { RefreshRight, Shop, TopRight } from '@element-plus/icons-vue'
import {
  fetchStoreOpsReport,
  triggerStoreOpsSync,
  type StoreOpsReportData,
} from '../api/storeOps'

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

onMounted(() => {
  loadReport()
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
