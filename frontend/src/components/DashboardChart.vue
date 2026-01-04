<template>
  <div class="dashboard-chart">
    <el-card shadow="never">
      <template #header>
        <div class="chart-header">
          <span>数据趋势</span>
          <div class="chart-controls">
            <el-checkbox-group v-model="selectedMetrics" @change="handleMetricsChange">
              <el-checkbox label="gmv">销售额</el-checkbox>
              <el-checkbox label="orders">订单数</el-checkbox>
              <el-checkbox label="visitors">访客数</el-checkbox>
              <el-checkbox label="aov">客单价</el-checkbox>
              <el-checkbox label="spend">广告花费</el-checkbox>
              <el-checkbox label="roas">ROAS</el-checkbox>
              <el-checkbox label="conversion">转化率</el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
      </template>
      
      <v-chart
        :option="chartOption"
        :loading="loading"
        style="height: 500px; width: 100%"
        autoresize
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElCard, ElCheckbox, ElCheckboxGroup } from 'element-plus'
import type { DashboardDataItem } from '../api/dashboard'

// 注册ECharts组件
use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent
])

// Props
const props = defineProps<{
  data: DashboardDataItem[]
  compareData?: DashboardDataItem[][]  // 对比数据数组，每个元素是一个对比段的数据
  loading?: boolean
}>()

// 选中的指标
const selectedMetrics = ref(['gmv', 'orders', 'visitors'])

// 指标配置
const metricConfig = {
  gmv: { name: '销售额', color: '#5470c6', unit: '$', formatter: (val: number) => '$' + val.toFixed(2) },
  orders: { name: '订单数', color: '#91cc75', unit: '单', formatter: (val: number) => val.toFixed(0) },
  visitors: { name: '访客数', color: '#fac858', unit: '人', formatter: (val: number) => val.toFixed(0) },
  aov: { name: '客单价', color: '#ee6666', unit: '$', formatter: (val: number) => '$' + val.toFixed(2) },
  spend: { name: '广告花费', color: '#73c0de', unit: '$', formatter: (val: number) => '$' + val.toFixed(2) },
  roas: { name: 'ROAS', color: '#3ba272', unit: '', formatter: (val: number) => val.toFixed(2) },
  conversion: { name: '转化率', color: '#fc8452', unit: '%', formatter: (val: number) => val.toFixed(2) }
}

// 计算ROAS
const calculateROAS = (gmv: number, spend: number): number => {
  return spend > 0 ? gmv / spend : 0
}

// 计算转化率
const calculateConversionRate = (orders: number, visitors: number): number => {
  return visitors > 0 ? (orders / visitors) * 100 : 0
}

// 图表配置
const chartOption = computed(() => {
  if (!props.data || props.data.length === 0) {
    return {}
  }

  // 收集所有时间点（使用时间戳作为key）
  const allTimestamps = new Set<number>()
  props.data.forEach(item => {
    allTimestamps.add(new Date(item.time_hour).getTime())
  })
  
  if (props.compareData) {
    props.compareData.forEach(compareData => {
      compareData.forEach(item => {
        allTimestamps.add(new Date(item.time_hour).getTime())
      })
    })
  }
  
  // 排序时间戳
  const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b)
  
  // 转换为显示格式
  const timeData = sortedTimestamps.map(timestamp => {
    const date = new Date(timestamp)
    return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`
  })

  // 创建时间戳到数据的映射
  const createTimeMap = (data: DashboardDataItem[]) => {
    const map = new Map<number, DashboardDataItem>()
    data.forEach(item => {
      const timestamp = new Date(item.time_hour).getTime()
      map.set(timestamp, item)
    })
    return map
  }

  const mainTimeMap = createTimeMap(props.data)
  const compareTimeMaps = props.compareData ? props.compareData.map(data => createTimeMap(data)) : []

  // 系列数据
  const series: any[] = []

  // 主时间段的系列
  const addMainSeries = (metricKey: string, metricName: string, getValue: (item: DashboardDataItem) => number) => {
    if (selectedMetrics.value.includes(metricKey)) {
      series.push({
        name: metricName,
        type: 'line',
        data: sortedTimestamps.map(timestamp => {
          const item = mainTimeMap.get(timestamp)
          return item ? getValue(item) : null
        }),
        smooth: true,
        lineStyle: { color: metricConfig[metricKey as keyof typeof metricConfig].color },
        itemStyle: { color: metricConfig[metricKey as keyof typeof metricConfig].color },
        yAxisIndex: 0
      })
    }
  }

  // 对比时间段的系列
  const addCompareSeries = (metricKey: string, metricName: string, getValue: (item: DashboardDataItem) => number, compareIndex: number) => {
    if (selectedMetrics.value.includes(metricKey)) {
      const compareTimeMap = compareTimeMaps[compareIndex]
      series.push({
        name: `${metricName}(对比${compareIndex + 1})`,
        type: 'line',
        data: sortedTimestamps.map(timestamp => {
          const item = compareTimeMap.get(timestamp)
          return item ? getValue(item) : null
        }),
        smooth: true,
        lineStyle: { 
          color: metricConfig[metricKey as keyof typeof metricConfig].color,
          type: 'dashed' // 对比数据使用虚线
        },
        itemStyle: { color: metricConfig[metricKey as keyof typeof metricConfig].color },
        yAxisIndex: 0
      })
    }
  }

  // 主时间段：销售额
  addMainSeries('gmv', '销售额', item => item.total_gmv)
  
  // 主时间段：订单数
  addMainSeries('orders', '订单数', item => item.total_orders)
  
  // 主时间段：访客数
  addMainSeries('visitors', '访客数', item => item.total_visitors)
  
  // 主时间段：客单价
  addMainSeries('aov', '客单价', item => item.avg_order_value)
  
  // 主时间段：广告花费
  addMainSeries('spend', '广告花费', item => item.total_spend)
  
  // 主时间段：ROAS
  addMainSeries('roas', 'ROAS', item => calculateROAS(item.total_gmv, item.total_spend))
  
  // 主时间段：转化率
  addMainSeries('conversion', '转化率', item => calculateConversionRate(item.total_orders, item.total_visitors))

  // 对比时间段
  if (props.compareData && props.compareData.length > 0) {
    props.compareData.forEach((compareData, index) => {
      addCompareSeries('gmv', '销售额', item => item.total_gmv, index)
      addCompareSeries('orders', '订单数', item => item.total_orders, index)
      addCompareSeries('visitors', '访客数', item => item.total_visitors, index)
      addCompareSeries('aov', '客单价', item => item.avg_order_value, index)
      addCompareSeries('spend', '广告花费', item => item.total_spend, index)
      addCompareSeries('roas', 'ROAS', item => calculateROAS(item.total_gmv, item.total_spend), index)
      addCompareSeries('conversion', '转化率', item => calculateConversionRate(item.total_orders, item.total_visitors), index)
    })
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        
        const timeValue = params[0].axisValue
        const dataIndex = params[0].dataIndex
        
        // 通过dataIndex找到对应的数据项
        if (dataIndex < 0 || dataIndex >= sortedTimestamps.length) {
          return `<div><strong>${timeValue}</strong></div>`
        }
        
        const timestamp = sortedTimestamps[dataIndex]
        const mainItem = mainTimeMap.get(timestamp)
        
        if (!mainItem) return `<div><strong>${timeValue}</strong></div>`
        
        // 只显示已勾选的指标
        let result = `<div style="margin-bottom: 8px; font-size: 14px; font-weight: 600; border-bottom: 1px solid #eee; padding-bottom: 4px;">${timeValue}</div>`
        
        // 根据selectedMetrics判断是否显示某个指标
        if (selectedMetrics.value.includes('gmv')) {
          const gmvConfig = metricConfig.gmv
          result += `<div style="margin: 4px 0;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${gmvConfig.color};margin-right:5px;"></span>
            ${gmvConfig.name}: <strong>${gmvConfig.formatter(mainItem.total_gmv)}</strong>
          </div>`
        }
        
        if (selectedMetrics.value.includes('orders')) {
          const ordersConfig = metricConfig.orders
          result += `<div style="margin: 4px 0;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${ordersConfig.color};margin-right:5px;"></span>
            ${ordersConfig.name}: <strong>${ordersConfig.formatter(mainItem.total_orders)}${ordersConfig.unit}</strong>
          </div>`
        }
        
        if (selectedMetrics.value.includes('visitors')) {
          const visitorsConfig = metricConfig.visitors
          result += `<div style="margin: 4px 0;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${visitorsConfig.color};margin-right:5px;"></span>
            ${visitorsConfig.name}: <strong>${visitorsConfig.formatter(mainItem.total_visitors)}${visitorsConfig.unit}</strong>
          </div>`
        }
        
        if (selectedMetrics.value.includes('aov')) {
          const aovConfig = metricConfig.aov
          result += `<div style="margin: 4px 0;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${aovConfig.color};margin-right:5px;"></span>
            ${aovConfig.name}: <strong>${aovConfig.formatter(mainItem.avg_order_value)}</strong>
          </div>`
        }
        
        if (selectedMetrics.value.includes('spend')) {
          const spendConfig = metricConfig.spend
          result += `<div style="margin: 4px 0;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${spendConfig.color};margin-right:5px;"></span>
            ${spendConfig.name}: <strong>${spendConfig.formatter(mainItem.total_spend)}</strong>
          </div>`
        }
        
        if (selectedMetrics.value.includes('roas')) {
          const roasValue = calculateROAS(mainItem.total_gmv, mainItem.total_spend)
          const roasConfig = metricConfig.roas
          result += `<div style="margin: 4px 0;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${roasConfig.color};margin-right:5px;"></span>
            ${roasConfig.name}: <strong>${roasConfig.formatter(roasValue)}</strong>
          </div>`
        }
        
        if (selectedMetrics.value.includes('conversion')) {
          const conversionValue = calculateConversionRate(mainItem.total_orders, mainItem.total_visitors)
          const conversionConfig = metricConfig.conversion
          result += `<div style="margin: 4px 0;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${conversionConfig.color};margin-right:5px;"></span>
            ${conversionConfig.name}: <strong>${conversionConfig.formatter(conversionValue)}${conversionConfig.unit}</strong>
          </div>`
        }
        
        return result
      }
    },
    legend: {
      data: series.map(s => s.name),
      bottom: 0,
      type: 'scroll'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '10%',
      containLabel: true
    },
    toolbox: {
      feature: {
        dataZoom: {
          yAxisIndex: 'none'
        },
        restore: {},
        saveAsImage: {}
      },
      right: 10
    },
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100
      },
      {
        type: 'slider',
        start: 0,
        end: 100,
        height: 20,
        bottom: 40
      }
    ],
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: timeData,
      axisLabel: {
        rotate: 45,
        interval: 'auto'
      }
    },
    yAxis: {
      type: 'value',
      scale: false,
      axisLabel: {
        formatter: (value: number) => {
          return '$' + value.toFixed(0)
        }
      }
    },
    series
  }
})

// 指标变化处理
const handleMetricsChange = () => {
  // 图表会自动更新（通过computed）
}

// 监听数据变化，确保至少有一个指标被选中
watch(() => props.data, () => {
  if (selectedMetrics.value.length === 0) {
    selectedMetrics.value = ['gmv']
  }
}, { immediate: true })
</script>

<style scoped>
.dashboard-chart {
  margin-bottom: 20px;
  width: 100%;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}

.chart-controls {
  display: flex;
  gap: 10px;
}

:deep(.el-checkbox-group) {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
}

:deep(.el-card__header) {
  padding: 15px 20px;
}

:deep(.el-card__body) {
  padding: 20px;
}
</style>

