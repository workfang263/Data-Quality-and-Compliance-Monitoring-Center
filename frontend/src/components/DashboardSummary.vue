<template>
  <div class="dashboard-summary">
    <div class="summary-grid">
      <el-card v-for="metric in metrics" :key="metric.key" shadow="hover" class="summary-card">
        <div class="summary-content">
          <div class="summary-label">{{ metric.label }}</div>
          <div v-if="!metric.cmpValue" class="summary-main">{{ metric.mainValue }}</div>
          <template v-else>
            <div class="summary-cols">
              <div class="summary-col">
                <div class="summary-tag">{{ leftLabel }}</div>
                <div class="summary-main">{{ metric.mainValue }}</div>
              </div>
              <div class="summary-col">
                <div class="summary-tag">{{ rightLabel }}</div>
                <div class="summary-cmp">{{ metric.cmpValue }}</div>
              </div>
            </div>
          </template>
          <div v-if="metric.delta !== undefined" class="summary-delta" :class="metric.deltaClass">
            {{ metric.delta }}
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElCard } from 'element-plus'
import type { DashboardDataItem } from '../api/dashboard'

const props = defineProps<{
  data: DashboardDataItem[]
  granularity?: 'hour' | 'day'
  compareData?: DashboardDataItem[]
  compareLabel?: string  // "今天 / 昨天"
}>()

// 拆分 compareLabel 为左右标签
const leftLabel = computed(() => props.compareLabel?.split(' / ')[0] ?? '当前')
const rightLabel = computed(() => props.compareLabel?.split(' / ')[1] ?? '对比')

const calcVisitors = (d: DashboardDataItem[]): number => {
  if (d.length === 0) return 0
  const isHourly = props.granularity === 'hour' ||
    (props.granularity === undefined && (() => {
      const dateMap = new Map<string, number>()
      d.forEach(item => {
        const ds: string = typeof item.time_hour === 'string'
          ? (item.time_hour.split('T')[0] ?? '')
          : (new Date(item.time_hour).toISOString().split('T')[0] ?? '')
        dateMap.set(ds, (dateMap.get(ds) || 0) + 1)
      })
      return dateMap.size < d.length
    })())
  if (isHourly) {
    const dateMap = new Map<string, number>()
    d.forEach(item => {
      const timeHourStr = item.time_hour
      let ds: string
      if (typeof timeHourStr === 'string') { ds = timeHourStr.split('T')[0] ?? '' }
      else {
        const dt = new Date(timeHourStr)
        ds = `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-${String(dt.getDate()).padStart(2,'0')}`
      }
      dateMap.set(ds, Math.max(dateMap.get(ds) || 0, item.total_visitors))
    })
    return Array.from(dateMap.values()).reduce((s, v) => s + v, 0)
  }
  return d.reduce((s, item) => s + item.total_visitors, 0)
}

const metrics = computed(() => {
  const emptyMetric = (key: string, label: string, v = '$0.00') => ({ key, label, mainValue: v })

  if (!props.data || props.data.length === 0) {
    return [
      emptyMetric('gmv', '总销售额'), emptyMetric('orders', '总订单数', '0单'),
      emptyMetric('visitors', '总访客数', '0人'), emptyMetric('spend', '总广告花费'),
      emptyMetric('aov', '平均客单价'), emptyMetric('roas', '总ROAS', '0.00'),
      emptyMetric('conversion', '转化率', '0.00%')
    ]
  }

  const totalGmv = props.data.reduce((s, item) => s + item.total_gmv, 0)
  const totalOrders = props.data.reduce((s, item) => s + item.total_orders, 0)
  const totalVisitors = calcVisitors(props.data)
  const totalSpend = props.data.reduce((s, item) => s + item.total_spend, 0)
  const avgOrderValue = totalOrders > 0 ? totalGmv / totalOrders : 0
  const roas = totalSpend > 0 ? totalGmv / totalSpend : 0
  const convRate = totalVisitors > 0 ? (totalOrders / totalVisitors) * 100 : 0

  const hasCompare = props.compareData && props.compareData.length > 0
  let cmpGmv = 0, cmpOrders = 0, cmpVisitors = 0, cmpSpend = 0, cmpAov = 0, cmpRoas = 0, cmpConv = 0
  if (hasCompare) {
    cmpGmv = props.compareData!.reduce((s, item) => s + item.total_gmv, 0)
    cmpOrders = props.compareData!.reduce((s, item) => s + item.total_orders, 0)
    cmpVisitors = calcVisitors(props.compareData!)
    cmpSpend = props.compareData!.reduce((s, item) => s + item.total_spend, 0)
    cmpAov = cmpOrders > 0 ? cmpGmv / cmpOrders : 0
    cmpRoas = cmpSpend > 0 ? cmpGmv / cmpSpend : 0
    cmpConv = cmpVisitors > 0 ? (cmpOrders / cmpVisitors) * 100 : 0
  }

  const deltaText = (cur: number, prev: number, isOrder: boolean): { text: string; cls: string } | undefined => {
    if (!hasCompare || prev === 0 && cur === 0) return undefined
    if (isOrder) {
      const diff = cur - prev
      if (diff > 0) return { text: `+${diff}单`, cls: 'up' }
      if (diff < 0) return { text: `${diff}单`, cls: 'down' }
      return { text: '持平', cls: 'flat' }
    }
    if (prev === 0) return cur > 0 ? { text: '新增', cls: 'up' } : { text: '—', cls: 'flat' }
    const pct = ((cur - prev) / prev) * 100
    if (pct > 0) return { text: `+${pct.toFixed(1)}%`, cls: 'up' }
    if (pct < 0) return { text: `${pct.toFixed(1)}%`, cls: 'down' }
    return { text: '持平', cls: 'flat' }
  }

  const build = (key: string, label: string, cur: number, cmp: number, fmtCur: string, fmtCmp: string, isOrder: boolean) => {
    const d = deltaText(cur, cmp, isOrder)
    return { key, label, mainValue: fmtCur, cmpValue: hasCompare ? fmtCmp : undefined, delta: d?.text, deltaClass: d?.cls }
  }

  return [
    build('gmv', '总销售额', totalGmv, cmpGmv, formatCurrency(totalGmv), formatCurrency(cmpGmv), false),
    build('orders', '总订单数', totalOrders, cmpOrders, formatNumber(totalOrders, 0, '单'), formatNumber(cmpOrders, 0, '单'), true),
    build('visitors', '总访客数', totalVisitors, cmpVisitors, formatNumber(totalVisitors, 0, '人'), formatNumber(cmpVisitors, 0, '人'), false),
    build('spend', '总广告花费', totalSpend, cmpSpend, formatCurrency(totalSpend), formatCurrency(cmpSpend), false),
    build('aov', '平均客单价', avgOrderValue, cmpAov, formatCurrency(avgOrderValue), formatCurrency(cmpAov), false),
    build('roas', '总ROAS', roas, cmpRoas, formatNumber(roas, 2, ''), formatNumber(cmpRoas, 2, ''), false),
    build('conversion', '转化率', convRate, cmpConv, formatNumber(convRate, 2, '%'), formatNumber(cmpConv, 2, '%'), false)
  ]
})

const formatCurrency = (num: number): string => '$' + num.toFixed(2)
const formatNumber = (num: number, decimals: number, unit: string): string => num.toFixed(decimals) + unit
</script>

<style scoped>
.dashboard-summary { margin-bottom: 20px; }
.summary-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
@media (min-width: 640px) { .summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (min-width: 1024px) { .summary-grid { grid-template-columns: repeat(7, minmax(0, 1fr)); } }
.summary-card {
  text-align: center; transition: all 0.3s; min-height: 145px;
  display: flex; align-items: center; justify-content: center;
}
.summary-card:hover { transform: translateY(-2px); }
.summary-content { padding: 10px 6px; width: 100%; box-sizing: border-box; overflow: hidden; }
.summary-label { font-size: 13px; color: var(--el-text-color-regular); margin-bottom: 6px; }

.summary-cols { display: flex; justify-content: center; gap: 12px; margin-bottom: 4px; }
.summary-col { text-align: center; min-width: 0; }
.summary-tag { font-size: 10px; color: var(--el-text-color-placeholder); margin-bottom: 2px; white-space: nowrap; }

.summary-main { font-size: 17px; font-weight: 600; color: var(--el-text-color-primary); white-space: nowrap; }
.summary-cmp { font-size: 14px; font-weight: 500; color: var(--el-text-color-secondary); white-space: nowrap; }

.summary-delta { font-size: 17px; font-weight: 600; margin-top: 2px; white-space: nowrap; }
.summary-delta.up { color: #e53935; }
.summary-delta.down { color: #43a047; }
.summary-delta.flat { color: #9e9e9e; }
</style>

