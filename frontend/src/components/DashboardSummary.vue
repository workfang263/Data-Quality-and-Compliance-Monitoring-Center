<template>
  <div class="dashboard-summary">
    <!--
      用 CSS Grid 替代 el-row/el-col：
      1) 大屏固定 7 等分，7 张指标卡刚好铺满，不会在右侧留 1 格空白
      2) 小屏自动降列，避免卡片过窄
    -->
    <div class="summary-grid">
      <el-card v-for="metric in metrics" :key="metric.key" shadow="hover" class="summary-card">
        <div class="summary-content">
          <div class="summary-label">{{ metric.label }}</div>
          <div class="summary-value">{{ metric.value }}</div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElCard } from 'element-plus'
import type { DashboardDataItem } from '../api/dashboard'

// Props
const props = defineProps<{
  data: DashboardDataItem[]
  granularity?: 'hour' | 'day' // 数据粒度，用于准确计算访客数
}>()

// 计算汇总指标
const metrics = computed(() => {
  if (!props.data || props.data.length === 0) {
    return [
      { key: 'gmv', label: '总销售额', value: '0.00' },
      { key: 'orders', label: '总订单数', value: '0' },
      { key: 'visitors', label: '总访客数', value: '0' },
      { key: 'spend', label: '总广告花费', value: '0.00' },
      { key: 'aov', label: '平均客单价', value: '0.00' },
      { key: 'roas', label: '总ROAS', value: '0.00' },
      { key: 'conversion', label: '转化率', value: '0.00%' }
    ]
  }

  // 计算总销售额
  const totalGmv = props.data.reduce((sum, item) => sum + item.total_gmv, 0)
  
  // 计算总订单数
  const totalOrders = props.data.reduce((sum, item) => sum + item.total_orders, 0)
  
  // 计算总访客数
  // ⚠️ 访客数是累计值，同一天内不同小时是递增的（00:00 ≤ 01:00 ≤ ... ≤ 23:00）
  // - 小时粒度：按天分组取最大值（即当天的总访客数），然后累加所有天的最大值（不同天的访客是不同的，应该累加）
  // - 天粒度：直接累加（每天的数据已经是当天的总访客数）
  let totalVisitors = 0
  if (props.data.length > 0) {
    // 判断数据粒度：优先使用传入的 granularity，否则通过数据特征判断
    const isHourlyData = props.granularity === 'hour' || 
      (props.granularity === undefined && (() => {
        // 通过数据特征判断：如果同一天有多条记录，说明是小时粒度
        const dateMap = new Map<string, number>()
        props.data.forEach(item => {
          // ⚠️ 修复时区问题：直接提取ISO字符串的日期部分
          const timeHourStr = item.time_hour
          const dateStr: string = typeof timeHourStr === 'string'
            ? (timeHourStr.split('T')[0] ?? '')
            : (new Date(timeHourStr).toISOString().split('T')[0] ?? '')
          dateMap.set(dateStr, (dateMap.get(dateStr) || 0) + 1)
        })
        return dateMap.size < props.data.length
      })())
    
    if (isHourlyData) {
      // 小时粒度：按天分组取最大值（同一天内，最大值就是23:00的累计值，即当天的总访客数）
      const dateMap = new Map<string, number>()
      props.data.forEach(item => {
        // ⚠️ 修复时区问题：直接解析ISO字符串的日期部分，避免时区转换
        // time_hour 格式：2025-12-18T07:00:00，直接提取日期部分
        const timeHourStr = item.time_hour
        let dateStr: string
        if (typeof timeHourStr === 'string') {
          // 直接提取日期部分（YYYY-MM-DD），不进行时区转换
          dateStr = timeHourStr.split('T')[0] ?? ''
        } else {
          // 如果是Date对象，使用本地时区的日期
          const date = new Date(timeHourStr)
          dateStr = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
        }
        const currentMax = dateMap.get(dateStr) || 0
        dateMap.set(dateStr, Math.max(currentMax, item.total_visitors))
      })
      // 累加所有天的最大值（不同天的访客是不同的，应该累加）
      const dailyMaxValues = Array.from(dateMap.entries())
      // 调试信息：打印每天的最大值
      console.log('访客数计算 - 按天分组后的最大值：', dailyMaxValues.map(([date, max]) => ({ date, max })))
      totalVisitors = dailyMaxValues.reduce((sum, [, val]) => sum + val, 0)
      console.log('访客数计算 - 总访客数：', totalVisitors)
    } else {
      // 天粒度：直接累加（每天的数据已经是当天的总访客数）
      totalVisitors = props.data.reduce((sum, item) => sum + item.total_visitors, 0)
    }
  }
  
  // 计算总广告花费
  const totalSpend = props.data.reduce((sum, item) => sum + item.total_spend, 0)
  
  // 计算平均客单价（总销售额 / 总订单数）
  const avgOrderValue = totalOrders > 0 ? totalGmv / totalOrders : 0
  
  // 计算总ROAS（总销售额 / 总广告花费）
  const roas = totalSpend > 0 ? totalGmv / totalSpend : 0
  
  // 计算转化率（总订单数 / 总访客数 * 100）
  const conversionRate = totalVisitors > 0 ? (totalOrders / totalVisitors) * 100 : 0

  return [
    { 
      key: 'gmv', 
      label: '总销售额', 
      value: formatCurrency(totalGmv)
    },
    { 
      key: 'orders', 
      label: '总订单数', 
      value: formatNumber(totalOrders, 0, '单')
    },
    { 
      key: 'visitors', 
      label: '总访客数', 
      value: formatNumber(totalVisitors, 0, '人')
    },
    { 
      key: 'spend', 
      label: '总广告花费', 
      value: formatCurrency(totalSpend)
    },
    { 
      key: 'aov', 
      label: '平均客单价', 
      value: formatCurrency(avgOrderValue)
    },
    { 
      key: 'roas', 
      label: '总ROAS', 
      value: formatNumber(roas, 2, '')
    },
    { 
      key: 'conversion', 
      label: '转化率', 
      value: formatNumber(conversionRate, 2, '%')
    }
  ]
})

// 格式化货币（美元）
const formatCurrency = (num: number): string => {
  return '$' + num.toFixed(2)
}

// 格式化数字（非货币）
const formatNumber = (num: number, decimals: number, unit: string): string => {
  return num.toFixed(decimals) + unit
}
</script>

<style scoped>
.dashboard-summary {
  margin-bottom: 20px;
}

.summary-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (min-width: 640px) {
  .summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (min-width: 1024px) {
  .summary-grid {
    grid-template-columns: repeat(7, minmax(0, 1fr));
  }
}

.summary-card {
  text-align: center;
  transition: all 0.3s;
  min-height: 108px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.summary-card:hover {
  transform: translateY(-2px);
}

.summary-content {
  padding: 12px 8px;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.summary-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}

.summary-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
  line-height: 1.2;
}
</style>

