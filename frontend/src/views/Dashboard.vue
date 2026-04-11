<template>
  <PageShell>
    <PageHeaderBar title="看板" />
    <div class="dashboard-inner w-full">
    <!-- 筛选条件 -->
    <DashboardFilters v-model="filters" @change="handleFiltersChange" />
    
    <!-- 对比模式 -->
    <DashboardCompare v-model="compareConfig" @change="handleCompareChange" />
    
    <!-- 加载状态 -->
    <el-skeleton v-if="loading" :rows="5" animated />
    
    <!-- 错误提示 -->
    <el-alert v-if="error" type="error" :closable="false" show-icon style="margin-bottom: 20px">
      {{ error }}
    </el-alert>
    
    <!-- 权限提示 -->
    <el-alert
      v-if="!canViewDashboard && isAllStores"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 20px"
    >
      您没有权限查看看板总数据，请联系管理员授权
    </el-alert>
    
    <!-- 数据展示 -->
    <div v-if="!loading && !error">
      <!-- 核心指标汇总 -->
      <DashboardSummary 
        v-if="data.length > 0 && (canViewDashboard || !isAllStores)" 
        :data="data" 
        :granularity="filters.granularity" 
      />
      
      <!-- 折线图 -->
      <DashboardChart 
        v-if="data.length > 0 && (canViewDashboard || !isAllStores)" 
        :data="data" 
        :compare-data="compareData"
        :loading="false" 
      />
      
      <!-- 数据表格 -->
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
import DashboardCompare, { type CompareRange } from '../components/DashboardCompare.vue'
import { ElSkeleton, ElAlert, ElCard, ElTable, ElTableColumn, ElEmpty } from 'element-plus'
import { getCurrentUser } from '../api/auth'
import PageShell from '../components/PageShell.vue'
import PageHeaderBar from '../components/PageHeaderBar.vue'

// 响应式数据
const loading = ref(false)
const error = ref('')
const data = ref<DashboardDataItem[]>([])
const compareData = ref<DashboardDataItem[][]>([])

// 权限检查
const canViewDashboard = ref(false)

// 筛选条件
const today = new Date()
const todayStr = today.toISOString().split('T')[0]

const filters = ref<FiltersType>({
  startDate: todayStr,
  endDate: todayStr,
  granularity: 'hour',
  timeRange: 'all',
  shopDomain: 'ALL_STORES'
})

// 计算属性：是否查询总数据
const isAllStores = computed(() => {
  // 如果filters中有shopDomain字段且不是'ALL_STORES'，则不是总数据
  const shopDomain = (filters.value as any).shopDomain
  return !shopDomain || shopDomain === 'ALL_STORES'
})

// 检查用户权限
const checkUserPermissions = async () => {
  try {
    const user = await getCurrentUser()
    // 管理员自动拥有所有权限
    if (user.role === 'admin') {
      canViewDashboard.value = true
      return
    }
    
    // 普通用户检查扩展权限
    canViewDashboard.value = user.can_view_dashboard === true
  } catch (err) {
    // 获取用户信息失败，默认无权限
    canViewDashboard.value = false
  }
}

// 对比配置
const compareConfig = ref({
  enabled: false,
  ranges: [] as CompareRange[]
})

// 获取看板数据
const fetchDashboardData = async () => {
  loading.value = true
  error.value = ''
  
  try {
    // 获取主时间段数据
    const params: any = {
      shop_domain: 'ALL_STORES',
      start_date: filters.value.startDate,
      end_date: filters.value.endDate,
      granularity: filters.value.granularity
    }
    
    // 添加时段筛选
    if (filters.value.timeRange !== 'all' && filters.value.startHour !== undefined && filters.value.endHour !== undefined) {
      params.start_hour = filters.value.startHour
      params.end_hour = filters.value.endHour
    }
    
    const result = await getDashboardData(params)
    data.value = result
    
    // 如果启用对比模式，获取对比数据
    if (compareConfig.value.enabled && compareConfig.value.ranges.length > 0) {
      const comparePromises = compareConfig.value.ranges.map(async (range) => {
        const compareParams: any = {
          shop_domain: 'ALL_STORES',
          start_date: range.startDate,
          end_date: range.endDate,
          granularity: filters.value.granularity
        }
        
        if (range.timeRange !== 'all' && range.startHour !== undefined && range.endHour !== undefined) {
          compareParams.start_hour = range.startHour
          compareParams.end_hour = range.endHour
        }
        
        return await getDashboardData(compareParams)
      })
      
      const compareResults = await Promise.all(comparePromises)
      compareData.value = compareResults
    } else {
      compareData.value = []
    }
  } catch (err: any) {
    console.error('获取看板数据失败:', err)
    error.value = err.message || '获取数据失败'
  } finally {
    loading.value = false
  }
}

// 筛选条件变化
const handleFiltersChange = () => {
  fetchDashboardData()
}

// 对比配置变化
const handleCompareChange = () => {
  fetchDashboardData()
}

// 组件挂载时获取数据
onMounted(async () => {
  // 先检查权限
  await checkUserPermissions()
  
  // 获取数据
  fetchDashboardData()
})
</script>

<style scoped>
/* 与 StoreOps 等页一致：宽度由 PageShell 约束，此处只负责子块顶满一行 */
.dashboard-inner {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.dashboard-inner > * {
  width: 100%;
}
</style>
