<template>
  <PageShell>
    <PageHeaderBar title="看板" />
    <div class="dashboard-inner w-full">
    <DashboardFilters v-model="filters" @change="handleFiltersChange" />
    
    <el-skeleton v-if="isInitialLoad" :rows="5" animated />
    
    <el-alert v-if="error" type="error" :closable="false" show-icon style="margin-bottom: 20px">
      {{ error }}
    </el-alert>
    
    <el-alert
      v-if="!canViewDashboard && isAllStores"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 20px"
    >
      您没有权限查看看板总数据，请联系管理员授权
    </el-alert>
    
    <div v-loading="!isInitialLoad && loading">
      <DashboardSummary 
        v-if="data.length > 0 && (canViewDashboard || !isAllStores)" 
        :data="data" 
        :granularity="filters.granularity"
        :compare-data="compareData.length > 0 ? compareData[0] : undefined"
        :compare-label="compareLabel"
      />
      
      <DashboardChart 
        v-if="data.length > 0 && (canViewDashboard || !isAllStores)" 
        :data="data" 
        :compare-data="compareData"
        :loading="false" 
      />
      
      <el-card v-if="data.length > 0" shadow="never" style="margin-top: 20px">
        <el-table :data="data" border style="width: 100%">
          <el-table-column prop="time_hour" label="时间" width="180" />
          <el-table-column prop="total_gmv" label="销售额" width="120">
            <template #default="{ row }">
              ${{ row.total_gmv.toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column prop="total_orders" label="订单数" width="100" />
          <el-table-column prop="total_visitors" label="访客数" width="100" />
          <el-table-column prop="total_spend" label="广告花费" width="120">
            <template #default="{ row }">
              ${{ row.total_spend.toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column prop="avg_order_value" label="客单价" width="120">
            <template #default="{ row }">
              ${{ row.avg_order_value.toFixed(2) }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      
      <el-empty v-else description="该时间段内没有数据" />
    </div>
    </div>
  </PageShell>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { getDashboardData, type DashboardDataItem } from '../api/dashboard'
import DashboardFilters, { type DashboardFilters as FiltersType } from '../components/DashboardFilters.vue'
import DashboardChart from '../components/DashboardChart.vue'
import DashboardSummary from '../components/DashboardSummary.vue'
import { ElSkeleton, ElAlert, ElCard, ElTable, ElTableColumn, ElEmpty } from 'element-plus'
import { getCurrentUser } from '../api/auth'
import PageShell from '../components/PageShell.vue'
import PageHeaderBar from '../components/PageHeaderBar.vue'

const loading = ref(false)
const isInitialLoad = ref(true)
const error = ref('')
const data = ref<DashboardDataItem[]>([])
const compareData = ref<DashboardDataItem[][]>([])
const canViewDashboard = ref(false)

const toDateStr = (d: Date): string => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const today = new Date()
const todayStr: string = toDateStr(today)
const yesterday = new Date(today)
yesterday.setDate(yesterday.getDate() - 1)
const yesterdayStr: string = toDateStr(yesterday)

const filters = ref<FiltersType>({
  startDate: todayStr,
  endDate: todayStr,
  cmpStartDate: yesterdayStr,
  cmpEndDate: yesterdayStr,
  granularity: 'hour',
  startHour: 0,
  endHour: 11,
  cmpStartHour: 0,
  cmpEndHour: 11,
  hourSymmetric: true,
  enableComparison: true
})

const isAllStores = computed(() => {
  const shopDomain = (filters.value as any).shopDomain
  return !shopDomain || shopDomain === 'ALL_STORES'
})

const compareLabel = computed(() => {
  if (!filters.value.enableComparison) return ''
  const s = filters.value.startDate
  const e = filters.value.endDate
  const cs = filters.value.cmpStartDate
  const ce = filters.value.cmpEndDate
  if (!cs || !ce) return ''

  const fmtSingle = (d: string) => {
    const dt = new Date(d)
    return `${dt.getMonth() + 1}/${dt.getDate()}`
  }
  const fmtRange = (start: string, end: string) => {
    if (start === end) return fmtSingle(start)
    return `${fmtSingle(start)}~${fmtSingle(end)}`
  }

  return `${fmtRange(s, e)} / ${fmtRange(cs, ce)}`
})

const checkUserPermissions = async () => {
  try {
    const user = await getCurrentUser()
    if (user.role === 'admin') { canViewDashboard.value = true; return }
    canViewDashboard.value = user.can_view_dashboard === true
  } catch { canViewDashboard.value = false }
}

const fetchDashboardData = async () => {
  loading.value = true
  error.value = ''

  try {
    const f = filters.value

    // 主数据请求（天粒度不传小时参数）
    const params: any = { shop_domain: 'ALL_STORES', start_date: f.startDate, end_date: f.endDate, granularity: f.granularity }
    if (f.granularity !== 'day' && f.startHour !== undefined && f.endHour !== undefined) {
      params.start_hour = f.startHour; params.end_hour = f.endHour
    }
    data.value = await getDashboardData(params)

    // 对比数据：对称模式用主时段小时，不对称模式用独立对比小时
    if (f.enableComparison && f.cmpStartDate && f.cmpEndDate) {
      const cmpParams: any = { shop_domain: 'ALL_STORES', start_date: f.cmpStartDate, end_date: f.cmpEndDate, granularity: f.granularity }
      if (f.granularity !== 'day') {
        const sh = f.hourSymmetric ? f.startHour : f.cmpStartHour
        const eh = f.hourSymmetric ? f.endHour : f.cmpEndHour
        if (sh !== undefined && eh !== undefined) {
          cmpParams.start_hour = sh; cmpParams.end_hour = eh
        }
      }
      const cmp = await getDashboardData(cmpParams)
      compareData.value = cmp.length > 0 ? [cmp] : []
    } else {
      compareData.value = []
    }
    isInitialLoad.value = false
  } catch (err: any) {
    console.error('获取看板数据失败:', err)
    error.value = err.message || '获取数据失败'
  } finally {
    loading.value = false
  }
}

const handleFiltersChange = () => { fetchDashboardData() }

onMounted(async () => {
  await checkUserPermissions()
  fetchDashboardData()
})
</script>

<style scoped>
.dashboard-inner {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}
.dashboard-inner > * { width: 100%; }
</style>
