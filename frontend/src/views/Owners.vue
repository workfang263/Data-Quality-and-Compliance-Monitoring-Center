<template>
  <div class="owners-page">
    <!-- 页面标题 -->
    <h2>负责人汇总</h2>
    
    <!-- 筛选条件 -->
    <el-card shadow="never" style="margin-bottom: 20px">
      <el-form :inline="true" :model="filters">
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="handleDateRangeChange"
          />
        </el-form-item>
        
        <el-form-item label="快捷选择">
          <el-button-group>
            <el-button @click="setQuickDate('today')">今天</el-button>
            <el-button @click="setQuickDate('yesterday')">昨天</el-button>
            <el-button @click="setQuickDate('last7days')">最近7天</el-button>
            <el-button @click="setQuickDate('last30days')">最近30天</el-button>
          </el-button-group>
        </el-form-item>
        
        <el-form-item label="排序">
          <el-select v-model="filters.sortBy" @change="handleFiltersChange" style="width: 150px">
            <el-option label="负责人名称" value="owner" />
            <el-option label="销售额" value="gmv" />
            <el-option label="订单数" value="orders" />
            <el-option label="访客数" value="visitors" />
            <el-option label="客单价" value="aov" />
            <el-option label="广告花费" value="spend" />
            <el-option label="ROAS" value="roas" />
          </el-select>
          
          <el-select v-model="filters.sortOrder" @change="handleFiltersChange" style="width: 120px; margin-left: 10px">
            <el-option label="升序" value="asc" />
            <el-option label="降序" value="desc" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- 加载状态 -->
    <el-skeleton v-if="loading" :rows="10" animated />
    
    <!-- 错误提示 -->
    <el-alert v-if="error" type="error" :closable="false" show-icon style="margin-bottom: 20px">
      {{ error }}
    </el-alert>
    
    <!-- 数据表格 -->
    <el-card v-if="!loading && !error" shadow="never">
      <el-table :data="data" border style="width: 100%" v-loading="loading">
        <el-table-column prop="owner" label="负责人" width="150">
          <template #default="{ row }">
            <el-button type="primary" link @click="showOwnerChart(row.owner)">
              {{ row.owner }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="total_gmv" label="总销售额" width="120" sortable>
          <template #default="{ row }">
            ${{ row.total_gmv.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_orders" label="总订单数" width="100" sortable />
        <el-table-column prop="total_visitors" label="总访客数" width="100" sortable />
        <el-table-column prop="avg_order_value" label="平均客单价" width="120" sortable>
          <template #default="{ row }">
            ${{ row.avg_order_value.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_spend" label="Facebook广告花费" width="150" sortable>
          <template #default="{ row }">
            ${{ row.total_spend.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="tt_total_spend" label="TikTok广告花费" width="150" sortable>
          <template #default="{ row }">
            ${{ row.tt_total_spend.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_spend_all" label="总广告花费" width="120" sortable>
          <template #default="{ row }">
            ${{ row.total_spend_all.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="roas" label="ROAS" width="100" sortable>
          <template #default="{ row }">
            {{ row.roas !== null ? row.roas.toFixed(2) : 'N/A' }}
          </template>
        </el-table-column>
        <el-table-column prop="conversion_rate" label="转化率" width="100" sortable>
          <template #default="{ row }">
            {{ row.conversion_rate.toFixed(2) }}%
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { getOwnersSummary, getOwnerHourly, type OwnerSummaryItem, type OwnerHourlyItem } from '../api/owners'
import OwnerChart from '../components/OwnerChart.vue'

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
  
  filters.value.dateRange = [
    start.toISOString().split('T')[0],
    end.toISOString().split('T')[0]
  ]
  
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
    const result = await getOwnersSummary({
      start_date: filters.value.dateRange[0],
      end_date: filters.value.dateRange[1],
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
    const start = new Date(filters.value.dateRange[0])
    const end = new Date(filters.value.dateRange[1])
    const daysDiff = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
    
    let queryStart = filters.value.dateRange[0]
    let queryEnd = filters.value.dateRange[1]
    
    if (daysDiff > 7) {
      // 如果超过7天，只查询最近7天
      const recentEnd = new Date(end)
      const recentStart = new Date(recentEnd)
      recentStart.setDate(recentStart.getDate() - 6)
      queryStart = recentStart.toISOString().split('T')[0]
      queryEnd = recentEnd.toISOString().split('T')[0]
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
.owners-page {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.owners-page h2 {
  margin-bottom: 20px;
  font-size: 24px;
  font-weight: 600;
}
</style>
