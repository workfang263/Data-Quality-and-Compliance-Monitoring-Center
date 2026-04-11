<template>
  <!-- 外壳与页头：与其它后台页一致的背景与标题行 -->
  <PageShell>
    <PageHeaderBar title="负责人汇总">
      <template #actions>
        <!-- 显式触发拉取：与筛选变更共用 fetchData，避免重复请求逻辑 -->
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="fetchData">
          刷新数据
        </el-button>
      </template>
    </PageHeaderBar>

    <!-- 单卡片：工具条 + 表格集中在一处，层次更接近设计稿 -->
    <el-card class="rounded-xl border border-gray-100 shadow-sm" shadow="never">
      <!-- 工具条：大屏左右分布，小屏纵向堆叠 -->
      <div
        class="mb-6 flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end lg:justify-between"
      >
        <div class="flex flex-col gap-3">
          <div class="text-sm text-gray-500">日期范围</div>
          <div class="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <el-date-picker
              v-model="filters.dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              class="owners-date-picker"
              @change="handleDateRangeChange"
            />
            <el-button-group class="shrink-0">
              <el-button @click="setQuickDate('today')">今天</el-button>
              <el-button @click="setQuickDate('yesterday')">昨天</el-button>
              <el-button @click="setQuickDate('last7days')">最近7天</el-button>
              <el-button @click="setQuickDate('last30days')">最近30天</el-button>
            </el-button-group>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="mr-1 text-sm text-gray-500">排序</span>
          <el-select
            v-model="filters.sortBy"
            class="w-[150px]"
            @change="handleFiltersChange"
          >
            <el-option label="负责人名称" value="owner" />
            <el-option label="销售额" value="gmv" />
            <el-option label="订单数" value="orders" />
            <el-option label="访客数" value="visitors" />
            <el-option label="客单价" value="aov" />
            <el-option label="广告花费" value="spend" />
            <el-option label="ROAS" value="roas" />
          </el-select>
          <el-select
            v-model="filters.sortOrder"
            class="w-[120px]"
            @change="handleFiltersChange"
          >
            <el-option label="升序" value="asc" />
            <el-option label="降序" value="desc" />
          </el-select>
        </div>
      </div>

      <el-skeleton v-if="loading" :rows="10" animated />

      <el-alert
        v-else-if="error"
        type="error"
        :closable="false"
        show-icon
        class="mb-0"
      >
        {{ error }}
      </el-alert>

      <el-table
        v-else
        :data="data"
        stripe
        class="owners-table w-full"
        style="width: 100%"
      >
        <!-- fixed：横向滚动时负责人列固定，关键信息不丢 -->
        <el-table-column prop="owner" label="负责人" width="150" fixed="left">
          <template #default="{ row }">
            <el-button type="primary" link @click="showOwnerChart(row.owner)">
              {{ row.owner }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="total_gmv" label="总销售额" min-width="120" sortable>
          <template #default="{ row }">
            ${{ row.total_gmv.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_orders" label="总订单数" min-width="100" sortable />
        <el-table-column prop="total_visitors" label="总访客数" min-width="100" sortable />
        <el-table-column prop="avg_order_value" label="平均客单价" min-width="120" sortable>
          <template #default="{ row }">
            ${{ row.avg_order_value.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_spend" label="Facebook广告花费" min-width="150" sortable>
          <template #default="{ row }">
            ${{ row.total_spend.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="tt_total_spend" label="TikTok广告花费" min-width="150" sortable>
          <template #default="{ row }">
            ${{ row.tt_total_spend.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_spend_all" label="总广告花费" min-width="120" sortable>
          <template #default="{ row }">
            ${{ row.total_spend_all.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="roas" label="ROAS" min-width="112" sortable>
          <!-- 插槽：按阈值展示不同 tag，比纯数字更易扫读 -->
          <template #default="{ row }">
            <el-tag v-if="row.roas === null" type="info" size="small" effect="plain">
              N/A
            </el-tag>
            <el-tag
              v-else
              :type="row.roas >= ROAS_GOOD_THRESHOLD ? 'success' : 'warning'"
              size="small"
              effect="plain"
            >
              {{ row.roas.toFixed(2) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="conversion_rate" label="转化率" min-width="110" sortable>
          <template #default="{ row }">
            <span class="text-sm tabular-nums text-gray-800">
              {{ row.conversion_rate.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 负责人折线图弹窗 -->
    <el-dialog
      v-model="chartDialogVisible"
      :title="`${selectedOwner} - 小时趋势`"
      width="80%"
      :close-on-click-modal="false"
    >
      <div v-if="chartLoading" style="text-align: center; padding: 40px">
        <el-icon class="is-loading"><Loading /></el-icon>
        <p>加载中...</p>
      </div>
      <div v-else-if="chartError" style="text-align: center; padding: 40px">
        <el-alert type="error" :closable="false">{{ chartError }}</el-alert>
      </div>
      <OwnerChart
        v-else-if="chartData.length > 0"
        :data="chartData"
        :owner="selectedOwner"
      />
      <el-empty v-else description="暂无数据" />
    </el-dialog>
  </PageShell>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, Refresh } from '@element-plus/icons-vue'
import { getOwnersSummary, getOwnerHourly, type OwnerSummaryItem, type OwnerHourlyItem } from '../api/owners'
import OwnerChart from '../components/OwnerChart.vue'
import PageShell from '../components/PageShell.vue'
import PageHeaderBar from '../components/PageHeaderBar.vue'

/** ROAS 高于该阈值用 success 标签，便于一眼区分表现（可按业务再调） */
const ROAS_GOOD_THRESHOLD = 3

// 筛选条件
const filters = ref({
  dateRange: [] as string[],
  sortBy: 'owner' as 'owner' | 'gmv' | 'orders' | 'visitors' | 'aov' | 'spend' | 'roas',
  sortOrder: 'asc' as 'asc' | 'desc'
})

// 数据
const data = ref<OwnerSummaryItem[]>([])
const loading = ref(false)
const error = ref<string>('')

// 图表弹窗
const chartDialogVisible = ref(false)
const selectedOwner = ref('')
const chartData = ref<OwnerHourlyItem[]>([])
const chartLoading = ref(false)
const chartError = ref<string>('')

// 设置快捷日期
const setQuickDate = (type: string) => {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  
  let start: Date, end: Date
  
  switch (type) {
    case 'today':
      start = new Date(today)
      end = new Date(today)
      break
    case 'yesterday':
      start = new Date(yesterday)
      end = new Date(yesterday)
      break
    case 'last7days':
      start = new Date(today)
      start.setDate(start.getDate() - 6)
      end = new Date(today)
      break
    case 'last30days':
      start = new Date(today)
      start.setDate(start.getDate() - 29)
      end = new Date(today)
      break
    default:
      return
  }
  
  const startStr = start.toISOString().split('T')[0] ?? ''
  const endStr = end.toISOString().split('T')[0] ?? ''
  filters.value.dateRange = [startStr, endStr]
  
  handleFiltersChange()
}

// 处理日期范围变化
const handleDateRangeChange = () => {
  if (filters.value.dateRange && filters.value.dateRange.length === 2) {
    handleFiltersChange()
  }
}

// 处理筛选条件变化
const handleFiltersChange = () => {
  if (!filters.value.dateRange || filters.value.dateRange.length !== 2) {
    return
  }
  
  fetchData()
}

// 获取数据
const fetchData = async () => {
  if (!filters.value.dateRange || filters.value.dateRange.length !== 2) {
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    const startDate = filters.value.dateRange[0] ?? ''
    const endDate = filters.value.dateRange[1] ?? ''
    const result = await getOwnersSummary({
      start_date: startDate,
      end_date: endDate,
      sort_by: filters.value.sortBy,
      sort_order: filters.value.sortOrder
    })
    
    data.value = result
  } catch (err: any) {
    error.value = err.message || '获取数据失败'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

// 显示负责人图表
const showOwnerChart = async (owner: string) => {
  if (!filters.value.dateRange || filters.value.dateRange.length !== 2) {
    ElMessage.warning('请先选择日期范围')
    return
  }
  
  selectedOwner.value = owner
  chartDialogVisible.value = true
  chartData.value = []
  chartError.value = ''
  chartLoading.value = true
  
  try {
    // 限制查询范围最多7天
    const range0 = filters.value.dateRange[0] ?? ''
    const range1 = filters.value.dateRange[1] ?? ''
    const start = new Date(range0)
    const end = new Date(range1)
    const daysDiff = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
    
    let queryStart = range0
    let queryEnd = range1
    
    if (daysDiff > 7) {
      // 如果超过7天，只查询最近7天
      const recentEnd = new Date(end)
      const recentStart = new Date(recentEnd)
      recentStart.setDate(recentStart.getDate() - 6)
      queryStart = recentStart.toISOString().split('T')[0] ?? queryStart
      queryEnd = recentEnd.toISOString().split('T')[0] ?? queryEnd
      ElMessage.info('查询范围超过7天，已自动调整为最近7天')
    }
    
    const result = await getOwnerHourly({
      owner,
      start_date: queryStart,
      end_date: queryEnd
    })
    
    chartData.value = result
  } catch (err: any) {
    chartError.value = err.message || '获取图表数据失败'
    ElMessage.error(chartError.value)
  } finally {
    chartLoading.value = false
  }
}

// 初始化：设置默认日期为今天
onMounted(() => {
  setQuickDate('today')
})
</script>

<style scoped>
.owners-date-picker {
  width: 100%;
  max-width: 280px;
}
@media (min-width: 640px) {
  .owners-date-picker {
    width: 260px;
  }
}
.owners-table :deep(.el-table__header th) {
  font-weight: 600;
  color: var(--el-text-color-secondary);
}
</style>
