<template>
  <div class="dashboard-compare">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>对比模式</span>
          <el-switch v-model="enabled" @change="handleEnabledChange" />
        </div>
      </template>
      
      <div v-if="enabled">
        <!-- 基础对比快捷按钮 -->
        <el-form-item label="快捷对比">
          <el-button-group>
            <el-button @click="setQuickCompare('yesterday_vs_daybefore')">昨天 vs 前天</el-button>
            <el-button @click="setQuickCompare('lastweek_vs_thisweek')">上周 vs 本周</el-button>
            <el-button @click="setQuickCompare('lastmonth_vs_thismonth')">上月 vs 本月</el-button>
          </el-button-group>
        </el-form-item>
        
        <!-- 自由对比 -->
        <el-form-item label="自由对比">
          <el-button @click="addCompareRange" :disabled="compareRanges.length >= 4">添加对比段</el-button>
          <el-button v-if="compareRanges.length > 0" @click="clearCompareRanges" type="danger" plain>清除所有</el-button>
        </el-form-item>
        
        <!-- 对比段列表 -->
        <div v-for="(range, index) in compareRanges" :key="index" class="compare-range-item">
          <el-card shadow="hover" style="margin-bottom: 10px">
            <template #header>
              <div style="display: flex; justify-content: space-between; align-items: center">
                <span>对比段 {{ index + 1 }}</span>
                <el-button @click="removeCompareRange(index)" type="danger" text size="small">删除</el-button>
              </div>
            </template>
            
            <el-form :model="range" label-width="100px" size="small">
              <el-form-item label="日期范围">
                <el-date-picker
                  v-model="range.dateRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  format="YYYY-MM-DD"
                  value-format="YYYY-MM-DD"
                  @change="handleCompareRangeChange(index)"
                />
              </el-form-item>
              
              <el-form-item label="日内时段">
                <el-select v-model="range.timeRange" @change="handleCompareRangeChange(index)" style="width: 200px">
                  <el-option label="全天" value="all" />
                  <el-option label="上午 (00:00-12:00)" value="morning" />
                  <el-option label="下午 (12:00-18:00)" value="afternoon" />
                  <el-option label="晚上 (18:00-24:00)" value="evening" />
                  <el-option label="自定义" value="custom" />
                </el-select>
                
                <template v-if="range.timeRange === 'custom'">
                  <el-input-number
                    v-model="range.startHour"
                    :min="0"
                    :max="23"
                    :precision="0"
                    controls-position="right"
                    style="width: 100px; margin-left: 10px"
                    @change="handleCompareRangeChange(index)"
                  />
                  <span style="margin: 0 8px">至</span>
                  <el-input-number
                    v-model="range.endHour"
                    :min="0"
                    :max="23"
                    :precision="0"
                    controls-position="right"
                    style="width: 100px"
                    @change="handleCompareRangeChange(index)"
                  />
                </template>
              </el-form-item>
            </el-form>
          </el-card>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElCard, ElForm, ElFormItem, ElDatePicker, ElButtonGroup, ElButton, ElSelect, ElOption, ElInputNumber, ElSwitch } from 'element-plus'

// 对比段类型
export interface CompareRange {
  startDate: string
  endDate: string
  timeRange: 'all' | 'morning' | 'afternoon' | 'evening' | 'custom'
  startHour?: number
  endHour?: number
  dateRange: [string, string] | null
}

// Props
const props = defineProps<{
  modelValue: {
    enabled: boolean
    ranges: CompareRange[]
  }
}>()

// Emits
const emit = defineEmits<{
  'update:modelValue': [value: { enabled: boolean; ranges: CompareRange[] }]
  'change': [value: { enabled: boolean; ranges: CompareRange[] }]
}>()

// 启用状态
const enabled = ref(props.modelValue.enabled)

// 对比段列表
const compareRanges = ref<CompareRange[]>(props.modelValue.ranges.map(r => ({
  ...r,
  dateRange: r.startDate && r.endDate ? [r.startDate, r.endDate] : null
})))

// 初始化对比段
if (compareRanges.value.length === 0 && enabled.value) {
  addCompareRange()
}

// 启用状态变化
const handleEnabledChange = (value: boolean) => {
  if (!value) {
    compareRanges.value = []
  } else if (compareRanges.value.length === 0) {
    addCompareRange()
  }
  emitChange()
}

// 添加对比段
const addCompareRange = () => {
  if (compareRanges.value.length >= 4) return
  
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const yesterdayStr = yesterday.toISOString().split('T')[0]
  
  compareRanges.value.push({
    startDate: yesterdayStr,
    endDate: yesterdayStr,
    timeRange: 'all',
    dateRange: [yesterdayStr, yesterdayStr]
  })
  emitChange()
}

// 删除对比段
const removeCompareRange = (index: number) => {
  compareRanges.value.splice(index, 1)
  emitChange()
}

// 清除所有对比段
const clearCompareRanges = () => {
  compareRanges.value = []
  emitChange()
}

// 快捷对比
const setQuickCompare = (type: string) => {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  
  compareRanges.value = []
  
  if (type === 'yesterday_vs_daybefore') {
    // 昨天 vs 前天
    const dayBeforeYesterday = new Date(yesterday)
    dayBeforeYesterday.setDate(dayBeforeYesterday.getDate() - 1)
    const dayBeforeYesterdayStr = dayBeforeYesterday.toISOString().split('T')[0]
    const yesterdayStr = yesterday.toISOString().split('T')[0]
    
    compareRanges.value.push({
      startDate: dayBeforeYesterdayStr,
      endDate: dayBeforeYesterdayStr,
      timeRange: 'all',
      dateRange: [dayBeforeYesterdayStr, dayBeforeYesterdayStr]
    })
  } else if (type === 'lastweek_vs_thisweek') {
    // 上周 vs 本周
    const todayWeekday = yesterday.getDay() === 0 ? 7 : yesterday.getDay() // 转换为周一到周日：1-7
    const thisWeekMonday = new Date(yesterday)
    thisWeekMonday.setDate(yesterday.getDate() - (todayWeekday - 1))
    const lastWeekMonday = new Date(thisWeekMonday)
    lastWeekMonday.setDate(lastWeekMonday.getDate() - 7)
    const lastWeekSunday = new Date(thisWeekMonday)
    lastWeekSunday.setDate(lastWeekSunday.getDate() - 1)
    
    compareRanges.value.push({
      startDate: lastWeekMonday.toISOString().split('T')[0],
      endDate: lastWeekSunday.toISOString().split('T')[0],
      timeRange: 'all',
      dateRange: [
        lastWeekMonday.toISOString().split('T')[0],
        lastWeekSunday.toISOString().split('T')[0]
      ]
    })
  } else if (type === 'lastmonth_vs_thismonth') {
    // 上月 vs 本月
    const thisMonthFirst = new Date(yesterday.getFullYear(), yesterday.getMonth(), 1)
    const lastMonthFirst = new Date(thisMonthFirst)
    lastMonthFirst.setMonth(lastMonthFirst.getMonth() - 1)
    const lastMonthLast = new Date(thisMonthFirst)
    lastMonthLast.setDate(lastMonthLast.getDate() - 1)
    
    compareRanges.value.push({
      startDate: lastMonthFirst.toISOString().split('T')[0],
      endDate: lastMonthLast.toISOString().split('T')[0],
      timeRange: 'all',
      dateRange: [
        lastMonthFirst.toISOString().split('T')[0],
        lastMonthLast.toISOString().split('T')[0]
      ]
    })
  }
  
  enabled.value = true
  emitChange()
}

// 对比段变化
const handleCompareRangeChange = (index: number) => {
  const range = compareRanges.value[index]
  
  // 更新日期范围
  if (range.dateRange && range.dateRange.length === 2) {
    range.startDate = range.dateRange[0]
    range.endDate = range.dateRange[1]
  }
  
  // 更新时段
  switch (range.timeRange) {
    case 'all':
      range.startHour = undefined
      range.endHour = undefined
      break
    case 'morning':
      range.startHour = 0
      range.endHour = 12
      break
    case 'afternoon':
      range.startHour = 12
      range.endHour = 18
      break
    case 'evening':
      range.startHour = 18
      range.endHour = 24
      break
    case 'custom':
      if (range.startHour === undefined) range.startHour = 0
      if (range.endHour === undefined) range.endHour = 23
      break
  }
  
  emitChange()
}

// 发送变化事件
const emitChange = () => {
  const ranges = compareRanges.value.map(r => ({
    startDate: r.startDate,
    endDate: r.endDate,
    timeRange: r.timeRange,
    startHour: r.startHour,
    endHour: r.endHour
  }))
  
  emit('update:modelValue', { enabled: enabled.value, ranges })
  emit('change', { enabled: enabled.value, ranges })
}

// 监听props变化
watch(() => props.modelValue, (newVal) => {
  enabled.value = newVal.enabled
  compareRanges.value = newVal.ranges.map(r => ({
    ...r,
    dateRange: r.startDate && r.endDate ? [r.startDate, r.endDate] : null
  }))
}, { deep: true })
</script>

<style scoped>
.dashboard-compare {
  margin-bottom: 20px;
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}

.compare-range-item {
  margin-top: 10px;
}

:deep(.el-form-item) {
  margin-bottom: 15px;
}

:deep(.el-card) {
  width: 100%;
}
</style>



