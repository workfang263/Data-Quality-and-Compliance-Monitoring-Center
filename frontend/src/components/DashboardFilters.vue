<template>
  <div class="dashboard-filters">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>筛选条件</span>
        </div>
      </template>
      
      <el-form :model="filters" label-width="80px" size="default">
        <!-- 日期范围 -->
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="handleDateRangeChange"
          />
        </el-form-item>
        
        <!-- 快捷选择 -->
        <el-form-item label="快捷选择">
          <el-button-group>
            <el-button @click="setQuickDate('today')">今天</el-button>
            <el-button @click="setQuickDate('yesterday')">昨天</el-button>
            <el-button @click="setQuickDate('last7days')">最近7天</el-button>
            <el-button @click="setQuickDate('last30days')">最近30天</el-button>
            <el-button @click="setQuickDate('last90days')">最近3个月</el-button>
          </el-button-group>
        </el-form-item>
        
        <!-- 日内时段 -->
        <el-form-item label="日内时段">
          <el-select v-model="filters.timeRange" @change="handleTimeRangeChange" style="width: 200px">
            <el-option label="全天" value="all" />
            <el-option label="上午 (00:00-12:00)" value="morning" />
            <el-option label="下午 (12:00-18:00)" value="afternoon" />
            <el-option label="晚上 (18:00-24:00)" value="evening" />
            <el-option label="自定义" value="custom" />
          </el-select>
          
          <template v-if="filters.timeRange === 'custom'">
            <el-input-number
              v-model="filters.startHour"
              :min="0"
              :max="23"
              :precision="0"
              controls-position="right"
              style="width: 120px; margin-left: 10px"
            />
            <span style="margin: 0 8px">至</span>
            <el-input-number
              v-model="filters.endHour"
              :min="0"
              :max="23"
              :precision="0"
              controls-position="right"
              style="width: 120px"
            />
          </template>
        </el-form-item>
        
        <!-- 数据颗粒度 -->
        <el-form-item label="数据颗粒度">
          <el-radio-group v-model="filters.granularity" @change="handleGranularityChange">
            <el-radio-button label="hour">小时</el-radio-button>
            <el-radio-button label="day">天</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElCard, ElForm, ElFormItem, ElDatePicker, ElButtonGroup, ElButton, ElSelect, ElOption, ElInputNumber, ElRadioGroup, ElRadioButton } from 'element-plus'

// 定义筛选条件类型
export interface DashboardFilters {
  startDate: string
  endDate: string
  granularity: 'hour' | 'day'
  timeRange: 'all' | 'morning' | 'afternoon' | 'evening' | 'custom'
  startHour?: number
  endHour?: number
}

// Props
const props = defineProps<{
  modelValue: DashboardFilters
}>()

// Emits
const emit = defineEmits<{
  'update:modelValue': [value: DashboardFilters]
  'change': [value: DashboardFilters]
}>()

// 日期范围（用于日期选择器）
const dateRange = ref<[string, string] | null>(null)

// 筛选条件
const filters = ref<DashboardFilters>({ ...props.modelValue })

// 初始化日期范围
if (filters.value.startDate && filters.value.endDate) {
  dateRange.value = [filters.value.startDate, filters.value.endDate]
}

// 监听props变化
watch(() => props.modelValue, (newVal) => {
  filters.value = { ...newVal }
  if (newVal.startDate && newVal.endDate) {
    dateRange.value = [newVal.startDate, newVal.endDate]
  }
}, { deep: true })

// 日期范围变化
const handleDateRangeChange = (value: [string, string] | null) => {
  if (value && value.length === 2) {
    filters.value.startDate = value[0]
    filters.value.endDate = value[1]
    emitChange()
  }
}

// 快捷日期选择
const setQuickDate = (type: string) => {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  
  let startDate: Date
  let endDate: Date
  
  switch (type) {
    case 'today':
      startDate = today
      endDate = today
      break
    case 'yesterday':
      startDate = yesterday
      endDate = yesterday
      break
    case 'last7days':
      startDate = new Date(yesterday)
      startDate.setDate(startDate.getDate() - 6)
      endDate = yesterday
      break
    case 'last30days':
      startDate = new Date(yesterday)
      startDate.setDate(startDate.getDate() - 29)
      endDate = yesterday
      break
    case 'last90days':
      startDate = new Date(yesterday)
      startDate.setDate(startDate.getDate() - 89)
      endDate = yesterday
      break
    default:
      return
  }
  
  const formatDate = (date: Date) => {
    return date.toISOString().split('T')[0]
  }
  
  filters.value.startDate = formatDate(startDate)
  filters.value.endDate = formatDate(endDate)
  dateRange.value = [filters.value.startDate, filters.value.endDate]
  emitChange()
}

// 时段变化
const handleTimeRangeChange = (value: string) => {
  switch (value) {
    case 'all':
      filters.value.startHour = undefined
      filters.value.endHour = undefined
      break
    case 'morning':
      filters.value.startHour = 0
      filters.value.endHour = 12
      break
    case 'afternoon':
      filters.value.startHour = 12
      filters.value.endHour = 18
      break
    case 'evening':
      filters.value.startHour = 18
      filters.value.endHour = 24
      break
    case 'custom':
      // 保持当前值或设置默认值
      if (filters.value.startHour === undefined) {
        filters.value.startHour = 0
      }
      if (filters.value.endHour === undefined) {
        filters.value.endHour = 23
      }
      break
  }
  emitChange()
}

// 颗粒度变化
const handleGranularityChange = (value: 'hour' | 'day') => {
  filters.value.granularity = value
  emitChange()
}

// 监听自定义时段变化
watch([() => filters.value.startHour, () => filters.value.endHour], () => {
  if (filters.value.timeRange === 'custom') {
    emitChange()
  }
})

// 发送变化事件
const emitChange = () => {
  emit('update:modelValue', { ...filters.value })
  emit('change', { ...filters.value })
}
</script>

<style scoped>
.dashboard-filters {
  margin-bottom: 20px;
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

:deep(.el-form-item__label) {
  text-align: left;
}

:deep(.el-card) {
  width: 100%;
}
</style>

