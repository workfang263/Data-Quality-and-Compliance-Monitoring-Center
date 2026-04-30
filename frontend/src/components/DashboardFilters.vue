<template>
  <div class="dashboard-filters">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>筛选条件</span>
          <el-switch v-model="filters.enableComparison" active-text="对比模式" @change="handleComparisonToggle" />
        </div>
      </template>

      <el-form :model="filters" label-width="100px" size="default">
        <!-- 日期范围 - 双列 VS 布局 -->
        <el-form-item label="日期范围">
          <div class="dual-range">
            <div class="range-group">
              <div class="range-label">主时段</div>
              <el-date-picker
                v-model="mainDateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width: 260px"
                @change="handleMainDateChange"
              />
            </div>
            <span class="vs-separator" v-if="filters.enableComparison">VS</span>
            <div class="range-group" v-if="filters.enableComparison">
              <div class="range-label">对比时段</div>
              <el-date-picker
                v-model="cmpDateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width: 260px"
                @change="handleCmpDateChange"
              />
            </div>
          </div>
        </el-form-item>

        <!-- 日内时段 -->
        <el-form-item label="日内时段" v-if="filters.granularity === 'hour'">
          <div class="hour-controls">
            <div class="hour-row">
              <div class="range-label">主时段</div>
              <el-select v-model="timeRangeActive" @change="handleTimeRangeQuick" style="width: 180px">
                <el-option label="全天（不过滤）" value="all" />
                <el-option label="上午 (00:00-11:00)" value="morning" />
                <el-option label="下午 (12:00-17:00)" value="afternoon" />
                <el-option label="晚上 (18:00-23:00)" value="evening" />
                <el-option label="自定义" value="custom" />
              </el-select>
              <template v-if="timeRangeActive !== 'all'">
                <el-input-number
                  v-model="filters.startHour"
                  :min="0"
                  :max="maxMainStartHour"
                  :precision="0"
                  controls-position="right"
                  style="width: 100px"
                  @change="onMainHourChange"
                />
                <span style="margin: 0 8px; color: #909399;">时 至</span>
                <el-input-number
                  v-model="filters.endHour"
                  :min="minMainEndHour"
                  :max="maxMainEndHour"
                  :precision="0"
                  controls-position="right"
                  style="width: 100px"
                  @change="onMainHourChange"
                />
                <span style="margin-left: 4px; color: #909399;">时</span>
              </template>
            </div>

            <div v-if="filters.enableComparison" class="hour-symmetry-toggle">
              <el-switch
                v-model="filters.hourSymmetric"
                size="small"
                active-text="对称"
                inactive-text="不对称"
                @change="onHourSymmetricChange"
              />
            </div>

            <div v-if="filters.enableComparison && !filters.hourSymmetric" class="hour-row">
              <div class="range-label">对比时段</div>
              <el-select v-model="cmpTimeRangeActive" @change="handleCmpTimeRangeQuick" style="width: 180px">
                <el-option label="全天（不过滤）" value="all" />
                <el-option label="上午 (00:00-11:00)" value="morning" />
                <el-option label="下午 (12:00-17:00)" value="afternoon" />
                <el-option label="晚上 (18:00-23:00)" value="evening" />
                <el-option label="自定义" value="custom" />
              </el-select>
              <template v-if="cmpTimeRangeActive !== 'all'">
                <el-input-number
                  v-model="filters.cmpStartHour"
                  :min="0"
                  :max="maxCmpStartHour"
                  :precision="0"
                  controls-position="right"
                  style="width: 100px"
                  @change="onCmpHourChange"
                />
                <span style="margin: 0 8px; color: #909399;">时 至</span>
                <el-input-number
                  v-model="filters.cmpEndHour"
                  :min="minCmpEndHour"
                  :max="maxCmpEndHour"
                  :precision="0"
                  controls-position="right"
                  style="width: 100px"
                  @change="onCmpHourChange"
                />
                <span style="margin-left: 4px; color: #909399;">时</span>
              </template>
            </div>

            <div v-if="filters.enableComparison && filters.hourSymmetric" class="hour-row" style="color: #909399; font-size: 12px; padding-left: 56px;">
              <span>对比时段与主时段相同</span>
            </div>
          </div>
        </el-form-item>

        <!-- 快捷选择 -->
        <el-form-item label="快捷选择">
          <el-button-group>
            <el-button @click="setQuick('today')" :type="quickActive === 'today' ? 'primary' : 'default'">今天 vs 昨天</el-button>
            <el-button @click="setQuick('yesterday')" :type="quickActive === 'yesterday' ? 'primary' : 'default'">昨天 vs 前天</el-button>
            <el-button @click="setQuick('last7days')" :type="quickActive === 'last7days' ? 'primary' : 'default'">近7天 vs 上7天</el-button>
            <el-button @click="setQuick('last30days')" :type="quickActive === 'last30days' ? 'primary' : 'default'">近30天 vs 上30天</el-button>
            <el-button @click="setQuick('last90days')" :type="quickActive === 'last90days' ? 'primary' : 'default'">近3月 vs 前3月</el-button>
          </el-button-group>
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
import { ref, watch, computed } from 'vue'
import { ElCard, ElForm, ElFormItem, ElDatePicker, ElButtonGroup, ElButton, ElInputNumber, ElRadioGroup, ElRadioButton, ElSwitch, ElSelect, ElOption } from 'element-plus'

export interface DashboardFilters {
  startDate: string
  endDate: string
  cmpStartDate?: string
  cmpEndDate?: string
  granularity: 'hour' | 'day'
  startHour?: number
  endHour?: number
  cmpStartHour?: number
  cmpEndHour?: number
  hourSymmetric: boolean
  enableComparison: boolean
}

const props = defineProps<{ modelValue: DashboardFilters }>()

const emit = defineEmits<{
  'update:modelValue': [value: DashboardFilters]
  'change': [value: DashboardFilters]
}>()

const filters = ref<DashboardFilters>({ ...props.modelValue })

// 日期选择器绑定
const mainDateRange = ref<[string, string] | null>(
  filters.value.startDate && filters.value.endDate
    ? [filters.value.startDate, filters.value.endDate]
    : null
)
const cmpDateRange = ref<[string, string] | null>(
  filters.value.cmpStartDate && filters.value.cmpEndDate
    ? [filters.value.cmpStartDate, filters.value.cmpEndDate]
    : null
)

// 当前激活的快捷选择
const quickActive = ref<string>('')

// 日内时段快捷选择（UI 控件，不存到 filter model）
const timeRangeActive = ref<string>('custom')
const cmpTimeRangeActive = ref<string>('custom')

const toDateStr = (d: Date): string => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const todayDateStr = computed(() => toDateStr(new Date()))
const ceiledHour = computed(() => {
  const now = new Date()
  const h = now.getHours()
  const m = now.getMinutes()
  return m > 0 ? Math.min(h + 1, 23) : h
})

const maxMainEndHour = computed(() => {
  if (filters.value.endDate === todayDateStr.value) return ceiledHour.value
  return 23
})

const maxMainStartHour = computed(() => {
  if (filters.value.endHour == null) return 23
  return Math.max((filters.value.endHour as number) - 1, 0)
})

const minMainEndHour = computed(() => {
  if (filters.value.startHour == null) return 0
  return Math.min((filters.value.startHour as number) + 1, 23)
})

const maxCmpEndHour = computed(() => {
  if (filters.value.cmpEndDate === todayDateStr.value) return ceiledHour.value
  return 23
})

const maxCmpStartHour = computed(() => {
  if (filters.value.cmpEndHour == null) return 23
  return Math.max((filters.value.cmpEndHour as number) - 1, 0)
})

const minCmpEndHour = computed(() => {
  if (filters.value.cmpStartHour == null) return 0
  return Math.min((filters.value.cmpStartHour as number) + 1, 23)
})

// 监听props变化
watch(() => props.modelValue, (newVal) => {
  filters.value = { ...newVal }
  if (newVal.startDate && newVal.endDate) {
    mainDateRange.value = [newVal.startDate, newVal.endDate]
  }
  if (newVal.cmpStartDate && newVal.cmpEndDate) {
    cmpDateRange.value = [newVal.cmpStartDate, newVal.cmpEndDate]
  } else {
    cmpDateRange.value = null
  }
  if (newVal.hourSymmetric === undefined) {
    filters.value.hourSymmetric = true
  }
}, { deep: true })

// 主日期变化
const handleMainDateChange = (value: [string, string] | null) => {
  if (value && value.length === 2) {
    filters.value.startDate = value[0]
    filters.value.endDate = value[1]
  }
  quickActive.value = ''
  emitChange()
}

// 对比日期变化
const handleCmpDateChange = (value: [string, string] | null) => {
  if (value && value.length === 2) {
    filters.value.cmpStartDate = value[0]
    filters.value.cmpEndDate = value[1]
  } else {
    filters.value.cmpStartDate = undefined
    filters.value.cmpEndDate = undefined
  }
  quickActive.value = ''
  emitChange()
}

// 主时段小时变化（对称时自动同步到对比时段）
const onMainHourChange = () => {
  quickActive.value = ''
  timeRangeActive.value = 'custom'
  if (filters.value.endDate === todayDateStr.value && (filters.value.endHour == null)) {
    filters.value.endHour = ceiledHour.value
  }
  if (filters.value.hourSymmetric) {
    filters.value.cmpStartHour = filters.value.startHour
    filters.value.cmpEndHour = filters.value.endHour
  }
  emitChange()
}

// 对比时段小时变化（不对称模式下）
const onCmpHourChange = () => {
  quickActive.value = ''
  cmpTimeRangeActive.value = 'custom'
  if (filters.value.cmpEndDate === todayDateStr.value && (filters.value.cmpEndHour == null)) {
    filters.value.cmpEndHour = ceiledHour.value
  }
  emitChange()
}

// 对比时段快捷选择
const handleCmpTimeRangeQuick = (value: string) => {
  switch (value) {
    case 'all':
      filters.value.cmpStartHour = undefined
      filters.value.cmpEndHour = undefined
      break
    case 'morning':
      filters.value.cmpStartHour = 0
      filters.value.cmpEndHour = 11
      break
    case 'afternoon':
      filters.value.cmpStartHour = 12
      filters.value.cmpEndHour = 17
      break
    case 'evening':
      filters.value.cmpStartHour = 18
      filters.value.cmpEndHour = 23
      break
    case 'custom':
      if (filters.value.cmpStartHour === undefined) filters.value.cmpStartHour = 0
      if (filters.value.cmpEndHour === undefined) filters.value.cmpEndHour = 23
      break
  }
  emitChange()
}

// 对称切换：开启对称时把对比时段小时同步为主时段
const onHourSymmetricChange = () => {
  if (filters.value.hourSymmetric) {
    filters.value.cmpStartHour = filters.value.startHour
    filters.value.cmpEndHour = filters.value.endHour
  }
  emitChange()
}

// 日内时段快捷选择
const handleTimeRangeQuick = (value: string) => {
  switch (value) {
    case 'all':
      filters.value.startHour = undefined
      filters.value.endHour = undefined
      break
    case 'morning':
      filters.value.startHour = 0
      filters.value.endHour = 11
      break
    case 'afternoon':
      filters.value.startHour = 12
      filters.value.endHour = 17
      break
    case 'evening':
      filters.value.startHour = 18
      filters.value.endHour = 23
      break
    case 'custom':
      if (filters.value.startHour === undefined) filters.value.startHour = 0
      if (filters.value.endHour === undefined) filters.value.endHour = 23
      break
  }
  emitChange()
}

// 快捷选择
const setQuick = (type: string) => {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  let mainStart: Date, mainEnd: Date
  let cmpStart: Date, cmpEnd: Date

  switch (type) {
    case 'today':
      mainStart = today; mainEnd = today
      cmpStart = yesterday; cmpEnd = yesterday
      break
    case 'yesterday':
      mainStart = yesterday; mainEnd = yesterday
      cmpStart = new Date(yesterday); cmpStart.setDate(cmpStart.getDate() - 1)
      cmpEnd = new Date(yesterday); cmpEnd.setDate(cmpEnd.getDate() - 1)
      break
    case 'last7days':
      mainEnd = yesterday
      mainStart = new Date(yesterday); mainStart.setDate(mainStart.getDate() - 6)
      cmpEnd = new Date(mainStart); cmpEnd.setDate(cmpEnd.getDate() - 1)
      cmpStart = new Date(cmpEnd); cmpStart.setDate(cmpStart.getDate() - 6)
      break
    case 'last30days':
      mainEnd = yesterday
      mainStart = new Date(yesterday); mainStart.setDate(mainStart.getDate() - 29)
      cmpEnd = new Date(mainStart); cmpEnd.setDate(cmpEnd.getDate() - 1)
      cmpStart = new Date(cmpEnd); cmpStart.setDate(cmpStart.getDate() - 29)
      break
    case 'last90days':
      mainEnd = yesterday
      mainStart = new Date(yesterday); mainStart.setDate(mainStart.getDate() - 89)
      cmpEnd = new Date(mainStart); cmpEnd.setDate(cmpEnd.getDate() - 1)
      cmpStart = new Date(cmpEnd); cmpStart.setDate(cmpStart.getDate() - 89)
      break
    default:
      return
  }

  filters.value.startDate = toDateStr(mainStart)
  filters.value.endDate = toDateStr(mainEnd)
  filters.value.cmpStartDate = toDateStr(cmpStart)
  filters.value.cmpEndDate = toDateStr(cmpEnd)

  mainDateRange.value = [filters.value.startDate, filters.value.endDate]
  cmpDateRange.value = [filters.value.cmpStartDate!, filters.value.cmpEndDate!]
  quickActive.value = type

  // 今天 vs 昨天：自动将 endHour 封顶到当前小时（向下取整）
  if (type === 'today') {
    const now = new Date()
    const ch = now.getMinutes() > 0 ? Math.min(now.getHours() + 1, 23) : now.getHours()
    if (filters.value.granularity === 'hour') {
      filters.value.startHour = 0
      filters.value.endHour = ch
      filters.value.cmpStartHour = 0
      filters.value.cmpEndHour = ch
      timeRangeActive.value = 'custom'
      cmpTimeRangeActive.value = 'custom'
    }
  }

  if (!filters.value.enableComparison) {
    filters.value.enableComparison = true
  }

  emitChange()
}

// 对比模式切换
const handleComparisonToggle = (enabled: boolean) => {
  if (enabled) {
    // 开启对比：自动计算对比日期（与主时段相同天数）
    if (!filters.value.cmpStartDate || !filters.value.cmpEndDate) {
      const ms = new Date(filters.value.startDate)
      const me = new Date(filters.value.endDate)
      const days = Math.round((me.getTime() - ms.getTime()) / 86400000) + 1
      const ce = new Date(ms)
      ce.setDate(ce.getDate() - 1)
      const cs = new Date(ce)
      cs.setDate(cs.getDate() - days + 1)
      filters.value.cmpStartDate = toDateStr(cs)
      filters.value.cmpEndDate = toDateStr(ce)
      cmpDateRange.value = [filters.value.cmpStartDate, filters.value.cmpEndDate]
    }
  } else {
    // 关闭对比：清除对比日期
    filters.value.cmpStartDate = undefined
    filters.value.cmpEndDate = undefined
    cmpDateRange.value = null
  }
  emitChange()
}

// 颗粒度变化
const handleGranularityChange = () => {
  emitChange()
}

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

.dual-range {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.range-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  width: 56px;
}

.hour-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hour-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hour-symmetry-toggle {
  display: flex;
  align-items: center;
  padding-left: 56px;
}

.vs-separator {
  font-size: 16px;
  font-weight: 700;
  color: var(--el-color-primary);
  padding: 0 8px;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

:deep(.el-form-item__label) {
  text-align: left;
  white-space: nowrap;
}

:deep(.el-card) {
  width: 100%;
}

:deep(.el-button-group .el-button) {
  padding: 8px 12px;
  font-size: 13px;
}
</style>
