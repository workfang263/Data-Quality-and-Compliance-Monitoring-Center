<template>
  <PageShell>
    <PageHeaderBar
      title="映射操作记录"
      subtitle="记录店铺 / Facebook / TikTok 映射的新增与负责人变更（敏感字段已脱敏）。"
    >
      <template #actions>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadPage">
          刷新
        </el-button>
      </template>
    </PageHeaderBar>

    <el-alert
      v-if="forbidden"
      type="warning"
      :closable="false"
      show-icon
      class="mb-6"
    >
      您没有权限查看映射操作记录（需管理员或「可编辑映射」权限）。
    </el-alert>

    <el-card v-else class="rounded-xl border border-gray-100 shadow-sm" shadow="never">
      <!-- 筛选器：后续对接 API 时可直接绑定 query 参数 -->
      <div class="flex flex-wrap items-center gap-2">
        <el-select
          v-model="filters.resource_type"
          placeholder="资源类型"
          clearable
          class="w-[140px]"
          @change="reloadFirstPage"
        >
          <el-option label="店铺" value="store" />
          <el-option label="Facebook" value="facebook" />
          <el-option label="TikTok" value="tiktok" />
        </el-select>
        <el-select
          v-model="filters.action"
          placeholder="动作"
          clearable
          class="w-[120px]"
          @change="reloadFirstPage"
        >
          <el-option label="新增" value="create" />
          <el-option label="更新" value="update" />
        </el-select>
        <el-select
          v-model="filters.result_status"
          placeholder="结果"
          clearable
          class="w-[130px]"
          @change="reloadFirstPage"
        >
          <el-option label="成功" value="success" />
          <el-option label="警告" value="warning" />
          <el-option label="失败" value="error" />
        </el-select>
      </div>

      <el-table
        v-loading="loading"
        class="mt-4 w-full"
        :data="items"
        stripe
        style="width: 100%"
        empty-text="暂无记录"
      >
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column prop="action" label="动作" width="100">
          <template #default="{ row }">
            <el-tag
              v-if="row.action === 'create'"
              type="success"
              size="small"
              effect="plain"
            >
              新增
            </el-tag>
            <el-tag
              v-else-if="row.action === 'update'"
              type="info"
              size="small"
              effect="plain"
            >
              更新
            </el-tag>
            <span v-else class="text-sm text-gray-600">{{ row.action }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="类型" width="100">
          <template #default="{ row }">
            {{ typeLabel(row.resource_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="resource_id" label="资源标识" min-width="160" show-overflow-tooltip />
        <el-table-column label="店名" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ extractDisplayName(row) }}
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="100" show-overflow-tooltip />
        <el-table-column prop="operator_username" label="操作人" width="100" show-overflow-tooltip />
        <el-table-column prop="result_status" label="状态" width="120">
          <!-- 状态点 + 文案：比单标签更轻，颜色由圆点承担 -->
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <span
                class="h-2 w-2 shrink-0 rounded-full"
                :class="statusDotClass(row.result_status)"
                aria-hidden="true"
              />
              <span class="text-sm text-gray-800">{{ statusText(row.result_status) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="result_message" label="说明" min-width="160" show-overflow-tooltip />
        <el-table-column label="请求快照" min-width="120">
          <template #default="{ row }">
            <el-popover
              v-if="row.request_payload"
              placement="left"
              :width="420"
              trigger="click"
            >
              <template #reference>
                <el-button link type="primary" size="small">查看</el-button>
              </template>
              <pre class="payload-pre">{{ row.request_payload }}</pre>
            </el-popover>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="mt-4 flex justify-end">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="reloadFirstPage"
          @current-change="loadPage"
        />
      </div>
    </el-card>
  </PageShell>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  getMappingResourceAudits,
  type MappingAuditItem
} from '../api/audit'
import PageShell from '../components/PageShell.vue'
import PageHeaderBar from '../components/PageHeaderBar.vue'

const loading = ref(false)
const forbidden = ref(false)
const items = ref<MappingAuditItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive<{
  resource_type: string | undefined
  action: string | undefined
  result_status: string | undefined
}>({
  resource_type: undefined,
  action: undefined,
  result_status: undefined
})

function typeLabel(t: string): string {
  if (t === 'store') return '店铺'
  if (t === 'facebook') return 'Facebook'
  if (t === 'tiktok') return 'TikTok'
  return t
}

/** 从 request_payload 中提取 display_name（仅店铺类型有） */
function extractDisplayName(row: MappingAuditItem): string {
  if (row.resource_type !== 'store') return '—'
  if (!row.request_payload) return '—'
  try {
    const payload = typeof row.request_payload === 'string'
      ? JSON.parse(row.request_payload)
      : row.request_payload
    const dn = payload?.display_name
    return dn || '（未设置）'
  } catch {
    return '—'
  }
}

/** 状态圆点颜色（Tailwind 背景类） */
function statusDotClass(s: string): string {
  if (s === 'success') return 'bg-emerald-500'
  if (s === 'warning') return 'bg-amber-500'
  if (s === 'error') return 'bg-red-500'
  return 'bg-gray-400'
}

/** 状态展示文案 */
function statusText(s: string): string {
  if (s === 'success') return '成功'
  if (s === 'warning') return '警告'
  if (s === 'error') return '失败'
  return s || '—'
}

async function loadPage() {
  loading.value = true
  forbidden.value = false
  try {
    const offset = (page.value - 1) * pageSize.value
    const data = await getMappingResourceAudits({
      limit: pageSize.value,
      offset,
      resource_type: filters.resource_type,
      action: filters.action,
      result_status: filters.result_status
    })
    items.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    const err = e as { response?: { status?: number }; message?: string }
    if (err.response?.status === 403) {
      forbidden.value = true
      items.value = []
      total.value = 0
    } else {
      ElMessage.error(err.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

function reloadFirstPage() {
  page.value = 1
  loadPage()
}

onMounted(() => {
  loadPage()
})
</script>

<style scoped>
.payload-pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 320px;
  overflow: auto;
}
.muted {
  color: var(--el-text-color-placeholder);
}
</style>
