<template>

  <div class="store-ops-page">

    <div class="store-ops-container">

      <h2>店铺运营 · 员工销售额归因</h2>

      <p class="hint">

        数据来自店匠同步；金额按北京时间业务日汇总。两店数据分开展示。

      </p>



      <div class="toolbar">

        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          :disabled-date="disabledFuture"
          @change="loadReport"
        />

        <el-button type="success" :loading="syncing" @click="handleSync">立即同步</el-button>

      </div>



      <div v-loading="loading" class="report-body">

        <template v-if="report">

          <el-card

            v-for="(shop, idx) in report.shops"

            :key="shop.shop_domain"

            class="shop-card"

            shadow="hover"

          >

            <template #header>

              <div class="shop-card-header">

                <span class="shop-index">店铺 {{ idx + 1 }}</span>

                <div class="shop-domain-wrap">

                  <span class="shop-domain-label">店铺域名</span>

                  <code class="shop-domain-value">{{ shop.shop_domain }}</code>

                </div>

              </div>

            </template>

            <p class="pool-summary">

              公共池：销售额 ${{ formatMoney(shop.public_pool_sales_total) }}，

              订单数 {{ shop.public_pool_order_count }}

            </p>

            <el-table :data="shop.employee_rows" border stripe style="width: 100%">

              <el-table-column prop="employee_slug" label="员工 slug" width="120" />

              <el-table-column label="直接销售额">

                <template #default="{ row }">${{ formatMoney(row.direct_sales) }}</template>

              </el-table-column>

              <el-table-column label="公共池分摊">

                <template #default="{ row }">${{ formatMoney(row.allocated_from_public_pool) }}</template>

              </el-table-column>

              <el-table-column label="合计销售额">

                <template #default="{ row }">${{ formatMoney(row.total_sales) }}</template>

              </el-table-column>

              <el-table-column prop="direct_order_count" label="直接订单数" width="110" />

            </el-table>

          </el-card>

        </template>

        <el-empty v-else-if="!loading" description="请选择日期范围" />

      </div>

    </div>

  </div>

</template>



<script setup lang="ts">

import { ref, onMounted } from 'vue'

import axios from 'axios'

import { ElMessage, ElNotification } from 'element-plus'

import { fetchStoreOpsReport, triggerStoreOpsSync, type StoreOpsReportData } from '../api/storeOps'



/** 从 Axios / FastAPI 响应里取出可读错误文案 */

function apiErrorMessage(e: unknown): string {

  if (axios.isAxiosError(e) && e.response?.data) {

    const d = e.response.data as { detail?: unknown; message?: string }

    if (typeof d.detail === 'string') return d.detail

    if (Array.isArray(d.detail)) {

      return d.detail

        .map((x: { msg?: string }) => x?.msg)

        .filter(Boolean)

        .join('; ')

    }

    if (d.message) return d.message

  }

  if (e instanceof Error) return e.message

  return '请求失败'

}



const loading = ref(false)

const syncing = ref(false)

const report = ref<StoreOpsReportData | null>(null)



const today = () => {

  const d = new Date()

  const z = (n: number) => String(n).padStart(2, '0')

  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`

}



const dateRange = ref<[string, string]>([today(), today()])



const disabledFuture = (d: Date) => d.getTime() > Date.now()



function formatMoney(n: number) {

  if (n === undefined || n === null) return '0.00'

  return Number(n).toFixed(2)

}



const loadReport = async () => {

  if (!dateRange.value || dateRange.value.length !== 2) {

    ElMessage.warning('请选择日期范围')

    return

  }

  const [start, end] = dateRange.value

  loading.value = true

  try {

    report.value = await fetchStoreOpsReport(start, end)

  } catch (e: unknown) {

    const msg = e instanceof Error ? e.message : '加载失败'

    ElMessage.error(msg)

    report.value = null

  } finally {

    loading.value = false

  }

}



const handleSync = async () => {

  syncing.value = true

  try {

    const data = await triggerStoreOpsSync()

    ElNotification({

      title: '同步任务已提交',

      message: `批次 ${data.sync_run_id}。后台执行中，报表将按当前日期范围自动更新；排障请查 store_ops_sync_runs 或后端日志。`,

      type: 'success',

      duration: 10000

    })

    void loadReport()

  } catch (e: unknown) {

    ElNotification({

      title: '同步请求失败',

      message: apiErrorMessage(e),

      type: 'error',

      duration: 10000

    })

  } finally {

    syncing.value = false

  }

}



onMounted(() => {

  loadReport()

})

</script>



<style scoped>

.store-ops-page {

  min-height: 100vh;

  padding: 20px;

  background: #f5f5f5;

}

.store-ops-container {

  max-width: 1200px;

  margin: 0 auto;

  background: #fff;

  border-radius: 8px;

  padding: 20px;

  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

}

.hint {

  color: #666;

  font-size: 14px;

  margin-bottom: 16px;

}

.toolbar {

  display: flex;

  flex-wrap: wrap;

  gap: 12px;

  align-items: center;

  margin-bottom: 24px;

}

.shop-card {

  margin-bottom: 24px;

}

.shop-card-header {

  display: flex;

  flex-wrap: wrap;

  align-items: center;

  gap: 12px 20px;

}

.shop-index {

  font-weight: 600;

  font-size: 15px;

  color: #303133;

}

.shop-domain-wrap {

  display: flex;

  flex-wrap: wrap;

  align-items: center;

  gap: 8px;

}

.shop-domain-label {

  color: #909399;

  font-size: 13px;

}

.shop-domain-value {

  font-size: 15px;

  font-weight: 600;

  color: #409eff;

  background: #ecf5ff;

  padding: 4px 10px;

  border-radius: 4px;

  word-break: break-all;

}

.pool-summary {

  color: #606266;

  margin-bottom: 12px;

  font-size: 14px;

}

</style>


