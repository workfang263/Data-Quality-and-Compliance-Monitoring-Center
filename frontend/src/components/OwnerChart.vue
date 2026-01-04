<template>
  <div class="owner-chart">
    <div v-if="!data || data.length === 0" style="text-align: center; padding: 40px">
      <el-empty description="暂无数据" />
    </div>
    <v-chart v-else :option="chartOption" :loading="loading" style="height: 500px" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
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
import { ElEmpty } from 'element-plus'
import type { OwnerHourlyItem } from '../api/owners'

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

const props = defineProps<{
  data: OwnerHourlyItem[]
  owner: string
  loading?: boolean
}>()

// 指标配置
const metricConfig = {
  gmv: { label: '销售额', color: '#5470c6' },
  orders: { label: '订单数', color: '#91cc75' },
  visitors: { label: '访客数', color: '#fac858' },
  aov: { label: '客单价', color: '#ee6666' },
  spend: { label: 'Facebook广告花费', color: '#73c0de' },
  ttSpend: { label: 'TikTok广告花费', color: '#3ba272' },
  totalSpend: { label: '总广告花费', color: '#fc8452' },
  roas: { label: 'ROAS', color: '#9a60b4' },
  conversionRate: { label: '转化率', color: '#ea7ccc' }
}

// 图表配置
const chartOption = computed(() => {
  if (!props.data || props.data.length === 0) {
    return {}
  }

  // 按时间排序
  const sortedData = [...props.data].sort((a, b) => 
    new Date(a.time_hour).getTime() - new Date(b.time_hour).getTime()
  )

  // 时间轴数据
  const timeData = sortedData.map(item => {
    const date = new Date(item.time_hour)
    return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`
  })

  // 系列数据
  const series = [
    {
      name: metricConfig.gmv.label,
      type: 'line',
      data: sortedData.map(item => item.total_gmv),
      smooth: true,
      lineStyle: { color: metricConfig.gmv.color },
      itemStyle: { color: metricConfig.gmv.color },
      yAxisIndex: 0
    },
    {
      name: metricConfig.orders.label,
      type: 'line',
      data: sortedData.map(item => item.total_orders),
      smooth: true,
      lineStyle: { color: metricConfig.orders.color },
      itemStyle: { color: metricConfig.orders.color },
      yAxisIndex: 1
    },
    {
      name: metricConfig.visitors.label,
      type: 'line',
      data: sortedData.map(item => item.total_visitors),
      smooth: true,
      lineStyle: { color: metricConfig.visitors.color },
      itemStyle: { color: metricConfig.visitors.color },
      yAxisIndex: 1
    },
    {
      name: metricConfig.aov.label,
      type: 'line',
      data: sortedData.map(item => item.avg_order_value),
      smooth: true,
      lineStyle: { color: metricConfig.aov.color },
      itemStyle: { color: metricConfig.aov.color },
      yAxisIndex: 0
    },
    {
      name: metricConfig.spend.label,
      type: 'line',
      data: sortedData.map(item => item.total_spend),
      smooth: true,
      lineStyle: { color: metricConfig.spend.color },
      itemStyle: { color: metricConfig.spend.color },
      yAxisIndex: 0
    },
    {
      name: metricConfig.ttSpend.label,
      type: 'line',
      data: sortedData.map(item => item.tt_total_spend),
      smooth: true,
      lineStyle: { color: metricConfig.ttSpend.color },
      itemStyle: { color: metricConfig.ttSpend.color },
      yAxisIndex: 0
    },
    {
      name: metricConfig.totalSpend.label,
      type: 'line',
      data: sortedData.map(item => item.total_spend_all),
      smooth: true,
      lineStyle: { color: metricConfig.totalSpend.color },
      itemStyle: { color: metricConfig.totalSpend.color },
      yAxisIndex: 0
    },
    {
      name: metricConfig.roas.label,
      type: 'line',
      data: sortedData.map(item => item.roas !== null ? item.roas : null),
      smooth: true,
      lineStyle: { color: metricConfig.roas.color },
      itemStyle: { color: metricConfig.roas.color },
      yAxisIndex: 1
    },
    {
      name: metricConfig.conversionRate.label,
      type: 'line',
      data: sortedData.map(item => item.conversion_rate),
      smooth: true,
      lineStyle: { color: metricConfig.conversionRate.color },
      itemStyle: { color: metricConfig.conversionRate.color },
      yAxisIndex: 1
    }
  ]

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      formatter: (params: any) => {
        let result = `<div style="margin-bottom: 8px"><strong>${params[0].axisValue}</strong></div>`
        params.forEach((param: any) => {
          if (param.value !== null && param.value !== undefined) {
            let formattedValue = param.value
            if (typeof param.value === 'number' && param.value !== null) {
              // 判断是否是金额字段（销售额、客单价、广告花费）
              const isCurrency = ['销售额', '客单价', 'Facebook广告花费', 'TikTok广告花费', '总广告花费'].some(name => param.seriesName.includes(name))
              formattedValue = isCurrency ? '$' + param.value.toFixed(2) : param.value.toFixed(2)
            }
            result += `<div style="margin: 4px 0">
              <span style="display:inline-block;width:10px;height:10px;background-color:${param.color};margin-right:5px"></span>
              ${param.seriesName}: ${formattedValue}
            </div>`
          }
        })
        return result
      }
    },
    legend: {
      data: series.map(s => s.name),
      type: 'scroll',
      orient: 'horizontal',
      bottom: 0,
      selected: {
        [metricConfig.gmv.label]: true,
        [metricConfig.orders.label]: true,
        [metricConfig.visitors.label]: false,
        [metricConfig.aov.label]: false,
        [metricConfig.spend.label]: true,
        [metricConfig.ttSpend.label]: false,
        [metricConfig.totalSpend.label]: false,
        [metricConfig.roas.label]: true,
        [metricConfig.conversionRate.label]: false
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true
    },
    toolbox: {
      feature: {
        dataZoom: {
          yAxisIndex: 'none'
        },
        restore: {},
        saveAsImage: {}
      }
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
        end: 100
      }
    ],
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: timeData
    },
    yAxis: [
      {
        type: 'value',
        name: '金额/花费',
        position: 'left',
        axisLabel: {
          formatter: (value: number) => {
            return '$' + value.toFixed(0)
          }
        }
      },
      {
        type: 'value',
        name: '数量/比率',
        position: 'right',
        axisLabel: {
          formatter: (value: number) => {
            if (value >= 1000) {
              return (value / 1000).toFixed(1) + 'k'
            }
            return value.toFixed(0)
          }
        }
      }
    ],
    series
  }
})
</script>

<style scoped>
.owner-chart {
  width: 100%;
}
</style>

