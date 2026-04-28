<template>
  <PageShell>
    <PageHeaderBar
      title="店铺运营配置中心"
      subtitle="只读引用主系统候选店铺 / 广告账户；所有写操作仅落子系统配置表，并记录独立审计。"
    >
      <template #actions>
        <el-button @click="goBackToReport">返回报表</el-button>
        <el-button type="primary" :loading="refreshing" @click="refreshAll">
          刷新全部
        </el-button>
      </template>
    </PageHeaderBar>

    <div v-loading="booting" class="space-y-6">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="rounded-xl"
      >
        当前策略：广告系列命名不规范时，花费会进入未归属桶，不会丢失数据。建议运营后续统一按
        `slug-*` 或既定关键词命名。
      </el-alert>

      <!--
        卡片采用纵向铺开：每张卡片都占整行。
        原因：三卡并排时，表格列多，「操作」列容易被挤压换行导致 UI 错位；
        纵向铺开后每卡片都有足够横向空间展示全部列。
      -->
      <el-card shadow="never" class="rounded-2xl border border-slate-200">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="text-base font-semibold text-slate-900">店铺白名单</div>
              <div class="mt-1 text-xs text-slate-500">
                候选来自主系统「店铺映射」，与映射编辑页一致；支持加入 / 启停 / 软删除。
                当前 {{ shops.length }} 家在册，候选 {{ availableShops.length }} 家（其中已加入 {{ boundShopCount }}）。
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <el-button text @click="toggleSection('shops')">
                {{ sectionExpanded.shops ? '收起' : '展开' }}
              </el-button>
              <el-button type="primary" @click="openCreateShopDialog">加入店铺</el-button>
            </div>
          </div>
        </template>

        <div v-show="sectionExpanded.shops">
          <el-table :data="shops" stripe style="width: 100%">
            <el-table-column prop="shop_domain" label="店铺域名" min-width="260" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="row.is_enabled === 1 ? 'success' : 'info'">
                  {{ row.is_enabled === 1 ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  @click="toggleShopEnabled(row, row.is_enabled !== 1)"
                >
                  {{ row.is_enabled === 1 ? '停用' : '启用' }}
                </el-button>
                <el-button link type="danger" @click="removeShop(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty
            v-if="shops.length === 0"
            description="暂无店铺白名单"
            class="py-6"
          />
        </div>
      </el-card>

      <el-card shadow="never" class="rounded-2xl border border-slate-200">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="text-base font-semibold text-slate-900">广告账户白名单</div>
              <div class="mt-1 text-xs text-slate-500">
                候选来自主系统「广告账户映射（Facebook）」，与映射编辑页一致；每个账户全局只能绑定一家店。
                当前 {{ adAccounts.length }} 个在册，候选共 {{ availableAdAccounts.length }} 个（其中已绑定 {{ boundAdCount }}）。
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <el-button text @click="toggleSection('adAccounts')">
                {{ sectionExpanded.adAccounts ? '收起' : '展开' }}
              </el-button>
              <el-button type="primary" @click="openCreateAdDialog">绑定账户</el-button>
            </div>
          </div>
        </template>

        <div v-show="sectionExpanded.adAccounts">
          <el-table :data="adAccounts" stripe style="width: 100%">
            <el-table-column prop="ad_account_id" label="广告账户 ID" min-width="220" />
            <el-table-column prop="shop_domain" label="绑定店铺" min-width="220" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="row.is_enabled === 1 ? 'success' : 'info'">
                  {{ row.is_enabled === 1 ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEditAdDialog(row)">
                  编辑
                </el-button>
                <el-button
                  link
                  type="primary"
                  @click="toggleAdEnabled(row, row.is_enabled !== 1)"
                >
                  {{ row.is_enabled === 1 ? '停用' : '启用' }}
                </el-button>
                <el-button link type="danger" @click="removeAd(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty
            v-if="adAccounts.length === 0"
            description="暂无广告账户白名单"
            class="py-6"
          />
        </div>
      </el-card>

      <el-card shadow="never" class="rounded-2xl border border-slate-200">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="text-base font-semibold text-slate-900">运营人员配置</div>
              <div class="mt-1 text-xs text-slate-500">
                只需三项：`employee_slug` / `utm_keyword` / `campaign_keyword`。
                留空时 `utm_keyword` 自动 = slug，`campaign_keyword` 自动 = `__unset_{slug}`。
                不再维护显示名 / 排序 / 状态等字段；需要移除某人直接删除即可。
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <el-button text @click="toggleSection('operators')">
                {{ sectionExpanded.operators ? '收起' : '展开' }}
              </el-button>
              <el-button type="primary" @click="openCreateOperatorDialog">新增运营</el-button>
            </div>
          </div>
        </template>

        <div v-show="sectionExpanded.operators">
          <el-table :data="operators" stripe style="width: 100%">
            <el-table-column prop="employee_slug" label="employee_slug" min-width="160" />
            <el-table-column prop="utm_keyword" label="utm_keyword" min-width="180" />
            <el-table-column prop="campaign_keyword" label="campaign_keyword" min-width="220" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEditOperatorDialog(row)">
                  编辑
                </el-button>
                <el-button link type="danger" @click="removeOperator(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty
            v-if="operators.length === 0"
            description="暂无运营配置"
            class="py-6"
          />
        </div>
      </el-card>

      <el-card shadow="never" class="rounded-2xl border border-slate-200">
        <template #header>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div class="text-base font-semibold text-slate-900">最近操作审计</div>
              <div class="mt-1 text-xs text-slate-500">仅记录子系统配置写操作。这里展示最近 20 条，便于快速核对。</div>
            </div>
            <div class="flex flex-wrap gap-2">
              <el-button text @click="toggleSection('audit')">
                {{ sectionExpanded.audit ? '收起' : '展开' }}
              </el-button>
              <el-select
                v-model="auditFilterResourceType"
                clearable
                placeholder="全部资源"
                class="w-[180px]"
                @change="loadAudit"
              >
                <el-option label="店铺" value="shop" />
                <el-option label="广告账户" value="ad_whitelist" />
                <el-option label="运营" value="operator" />
              </el-select>
              <el-button :loading="auditLoading" @click="loadAudit">刷新审计</el-button>
            </div>
          </div>
        </template>

        <div v-show="sectionExpanded.audit">
          <el-table :data="audit.items" stripe style="width: 100%" v-loading="auditLoading">
            <el-table-column prop="created_at" label="时间" min-width="170" />
            <el-table-column prop="resource_type" label="资源类型" width="120" />
            <el-table-column prop="resource_key" label="资源键" min-width="160" />
            <el-table-column prop="action" label="动作" width="100" />
            <el-table-column prop="actor_username" label="操作人" width="110" />
            <el-table-column label="变更摘要" min-width="300">
              <template #default="{ row }">
                <span class="text-slate-600">{{ summarizeAuditChanges(row.request_payload) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>
    </div>

    <!-- 加入店铺对话框：候选展示主系统映射全量，已绑定的置灰不可选 -->
    <el-dialog
      v-model="shopDialogVisible"
      title="加入店铺白名单"
      width="520px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="候选店铺" required>
          <el-select
            v-model="shopForm.shop_domain"
            filterable
            placeholder="选择主系统「店铺映射」里的店铺"
            style="width: 100%"
          >
            <el-option
              v-for="item in availableShops"
              :key="item.shop_domain"
              :label="formatAvailableShopLabel(item)"
              :value="item.shop_domain"
              :disabled="item.already_bound === true"
            />
          </el-select>
          <div class="mt-2 text-xs text-slate-400">
            灰色 = 已加入白名单，不可重复加入。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shopDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingShop" @click="submitCreateShop">
          确认加入
        </el-button>
      </template>
    </el-dialog>

    <!-- 绑定广告账户：全量展示，已绑定的置灰显示已绑店铺 -->
    <el-dialog
      v-model="adDialogVisible"
      :title="adDialogMode === 'create' ? '绑定广告账户' : '编辑广告账户'"
      width="560px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="广告账户" required>
          <el-select
            v-if="adDialogMode === 'create'"
            v-model="adForm.ad_account_id"
            filterable
            placeholder="选择主系统「广告账户映射（Facebook）」"
            style="width: 100%"
          >
            <el-option
              v-for="item in availableAdAccounts"
              :key="item.ad_account_id"
              :label="formatAvailableAdAccountLabel(item)"
              :value="item.ad_account_id"
              :disabled="item.already_bound === true"
            />
          </el-select>
          <el-input v-else v-model="adForm.ad_account_id" disabled />
          <div v-if="adDialogMode === 'create'" class="mt-2 text-xs text-slate-400">
            灰色 = 已被其它店铺绑定，需先在该账户的现有绑定行里解绑/删除后才能重新绑定。
          </div>
        </el-form-item>
        <el-form-item label="绑定店铺" required>
          <el-select
            v-model="adForm.shop_domain"
            placeholder="请选择已启用店铺"
            style="width: 100%"
          >
            <el-option
              v-for="item in adDialogShopOptions"
              :key="item.shop_domain"
              :label="item.shop_domain"
              :value="item.shop_domain"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="adDialogMode === 'edit'" label="是否启用">
          <el-switch
            v-model="adForm.is_enabled"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingAd" @click="submitAdDialog">
          {{ adDialogMode === 'create' ? '确认绑定' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 运营对话框：按用户要求只保留三项 -->
    <el-dialog
      v-model="operatorDialogVisible"
      :title="operatorDialogMode === 'create' ? '新增运营' : '编辑运营'"
      width="520px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="employee_slug" required>
          <el-input
            v-model="operatorForm.employee_slug"
            :disabled="operatorDialogMode === 'edit'"
            placeholder="例如 xiaoyang（小写字母开头、只含 a-z 0-9 _）"
          />
        </el-form-item>
        <el-form-item label="utm_keyword">
          <el-input
            v-model="operatorForm.utm_keyword"
            placeholder="留空时自动回填 slug"
          />
        </el-form-item>
        <el-form-item label="campaign_keyword">
          <el-input
            v-model="operatorForm.campaign_keyword"
            placeholder="留空时自动回填 __unset_{slug}"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="operatorDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submittingOperator"
          @click="submitOperatorDialog"
        >
          {{ operatorDialogMode === 'create' ? '确认新增' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>
  </PageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageShell from '../components/PageShell.vue'
import PageHeaderBar from '../components/PageHeaderBar.vue'
import {
  createStoreOpsAdAccount,
  createStoreOpsOperator,
  createStoreOpsShop,
  deleteStoreOpsAdAccount,
  deleteStoreOpsOperator,
  deleteStoreOpsShop,
  fetchStoreOpsAvailableAdAccounts,
  fetchStoreOpsAvailableShops,
  fetchStoreOpsConfigAdAccounts,
  fetchStoreOpsConfigAudit,
  fetchStoreOpsConfigShops,
  fetchStoreOpsOperators,
  patchStoreOpsAdAccount,
  patchStoreOpsOperator,
  patchStoreOpsShop,
  type StoreOpsAdAccountItem,
  type StoreOpsAuditListData,
  type StoreOpsAuditPayload,
  type StoreOpsAuditResourceType,
  type StoreOpsAvailableAdAccountItem,
  type StoreOpsAvailableShopItem,
  type StoreOpsOperatorItem,
  type StoreOpsShopItem,
} from '../api/storeOpsConfig'

const router = useRouter()

const booting = ref(true)
const refreshing = ref(false)

const shops = ref<StoreOpsShopItem[]>([])
const availableShops = ref<StoreOpsAvailableShopItem[]>([])
const adAccounts = ref<StoreOpsAdAccountItem[]>([])
const availableAdAccounts = ref<StoreOpsAvailableAdAccountItem[]>([])
const operators = ref<StoreOpsOperatorItem[]>([])
const audit = ref<StoreOpsAuditListData>({
  total: 0,
  limit: 20,
  offset: 0,
  items: [],
})

const auditLoading = ref(false)
const auditFilterResourceType = ref<StoreOpsAuditResourceType | undefined>()
const sectionExpanded = reactive({
  shops: true,
  adAccounts: false,
  operators: true,
  audit: true,
})

const shopDialogVisible = ref(false)
const submittingShop = ref(false)
const shopForm = reactive({
  shop_domain: '',
})

const adDialogVisible = ref(false)
const adDialogMode = ref<'create' | 'edit'>('create')
const submittingAd = ref(false)
const adForm = reactive({
  id: 0,
  ad_account_id: '',
  shop_domain: '',
  is_enabled: true,
})

const operatorDialogVisible = ref(false)
const operatorDialogMode = ref<'create' | 'edit'>('create')
const submittingOperator = ref(false)
const operatorForm = reactive({
  id: 0,
  employee_slug: '',
  utm_keyword: '',
  campaign_keyword: '',
})

const enabledShops = computed(() =>
  shops.value.filter((item) => item.is_enabled === 1),
)

const boundShopCount = computed(
  () => availableShops.value.filter((item) => item.already_bound).length,
)
const boundAdCount = computed(
  () => availableAdAccounts.value.filter((item) => item.already_bound).length,
)

const adDialogShopOptions = computed(() => {
  const map = new Map<string, StoreOpsShopItem>()
  for (const item of enabledShops.value) {
    map.set(item.shop_domain, item)
  }
  // 编辑场景，若当前绑定的店铺已被停用，也要允许在下拉里看到，避免选不回来
  if (adDialogMode.value === 'edit' && adForm.shop_domain && !map.has(adForm.shop_domain)) {
    map.set(adForm.shop_domain, {
      id: -1,
      shop_domain: adForm.shop_domain,
      is_enabled: 0,
    })
  }
  return Array.from(map.values())
})

function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error) && error.response?.data) {
    const data = error.response.data as {
      detail?: unknown
      message?: string
    }
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item) =>
          typeof item === 'object' &&
          item !== null &&
          'msg' in item &&
          typeof item.msg === 'string'
            ? item.msg
            : '',
        )
        .filter(Boolean)
        .join('; ')
    }
    if (typeof data.message === 'string' && data.message) return data.message
  }
  if (error instanceof Error) return error.message
  return '请求失败'
}

function toggleSection(section: keyof typeof sectionExpanded) {
  sectionExpanded[section] = !sectionExpanded[section]
}

async function loadShops() {
  shops.value = await fetchStoreOpsConfigShops()
}

async function loadAvailableShops() {
  availableShops.value = await fetchStoreOpsAvailableShops()
}

async function loadAdAccounts() {
  adAccounts.value = await fetchStoreOpsConfigAdAccounts()
}

async function loadAvailableAdAccounts() {
  availableAdAccounts.value = await fetchStoreOpsAvailableAdAccounts()
}

async function loadOperators() {
  operators.value = await fetchStoreOpsOperators()
}

async function loadAudit() {
  auditLoading.value = true
  try {
    audit.value = await fetchStoreOpsConfigAudit({
      resource_type: auditFilterResourceType.value,
      limit: 20,
      offset: 0,
    })
  } catch (error: unknown) {
    ElMessage.error(apiErrorMessage(error))
  } finally {
    auditLoading.value = false
  }
}

async function refreshAll() {
  refreshing.value = true
  try {
    await Promise.all([
      loadShops(),
      loadAvailableShops(),
      loadAdAccounts(),
      loadAvailableAdAccounts(),
      loadOperators(),
      loadAudit(),
    ])
  } catch (error: unknown) {
    ElMessage.error(apiErrorMessage(error))
  } finally {
    refreshing.value = false
    booting.value = false
  }
}

function resetShopForm() {
  const firstAvailable = availableShops.value.find((item) => !item.already_bound)
  shopForm.shop_domain = firstAvailable?.shop_domain ?? ''
}

function openCreateShopDialog() {
  resetShopForm()
  shopDialogVisible.value = true
}

async function submitCreateShop() {
  if (!shopForm.shop_domain) {
    ElMessage.warning('请选择一个候选店铺')
    return
  }
  submittingShop.value = true
  try {
    await createStoreOpsShop(shopForm.shop_domain)
    ElMessage.success('店铺已加入白名单')
    shopDialogVisible.value = false
    await Promise.all([loadShops(), loadAvailableShops(), loadAudit()])
  } catch (error: unknown) {
    ElMessage.error(apiErrorMessage(error))
  } finally {
    submittingShop.value = false
  }
}

async function toggleShopEnabled(row: StoreOpsShopItem, nextEnabled: boolean) {
  const actionText = nextEnabled ? '启用' : '停用'
  try {
    await ElMessageBox.confirm(
      `确定要${actionText}店铺 ${row.shop_domain} 吗？`,
      `${actionText}确认`,
      {
        type: 'warning',
      },
    )
    await patchStoreOpsShop(row.id, { is_enabled: nextEnabled })
    ElMessage.success(`店铺已${actionText}`)
    await Promise.all([loadShops(), loadAdAccounts(), loadAudit()])
  } catch (error: unknown) {
    if (error !== 'cancel') {
      ElMessage.error(apiErrorMessage(error))
    }
  }
}

async function removeShop(row: StoreOpsShopItem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除店铺 ${row.shop_domain} 吗？该操作为软删除（is_enabled=0）。`,
      '删除确认',
      {
        type: 'warning',
      },
    )
    await deleteStoreOpsShop(row.id)
    ElMessage.success('店铺已删除')
    await Promise.all([loadShops(), loadAdAccounts(), loadAudit()])
  } catch (error: unknown) {
    if (error !== 'cancel') {
      ElMessage.error(apiErrorMessage(error))
    }
  }
}

function resetAdForm() {
  adForm.id = 0
  const firstAvailable = availableAdAccounts.value.find(
    (item) => !item.already_bound,
  )
  adForm.ad_account_id = firstAvailable?.ad_account_id ?? ''
  adForm.shop_domain = enabledShops.value[0]?.shop_domain ?? ''
  adForm.is_enabled = true
}

function openCreateAdDialog() {
  adDialogMode.value = 'create'
  resetAdForm()
  adDialogVisible.value = true
}

function openEditAdDialog(row: StoreOpsAdAccountItem) {
  adDialogMode.value = 'edit'
  adForm.id = row.id
  adForm.ad_account_id = row.ad_account_id
  adForm.shop_domain = row.shop_domain
  adForm.is_enabled = row.is_enabled === 1
  adDialogVisible.value = true
}

async function submitAdDialog() {
  if (!adForm.shop_domain) {
    ElMessage.warning('请选择一个已启用店铺')
    return
  }
  if (!adForm.ad_account_id) {
    ElMessage.warning('请选择一个广告账户')
    return
  }
  submittingAd.value = true
  try {
    if (adDialogMode.value === 'create') {
      await createStoreOpsAdAccount({
        shop_domain: adForm.shop_domain,
        ad_account_id: adForm.ad_account_id,
      })
      ElMessage.success('广告账户已绑定')
    } else {
      await patchStoreOpsAdAccount(adForm.id, {
        shop_domain: adForm.shop_domain,
        is_enabled: adForm.is_enabled,
      })
      ElMessage.success('广告账户已更新')
    }
    adDialogVisible.value = false
    await Promise.all([
      loadAdAccounts(),
      loadAvailableAdAccounts(),
      loadAudit(),
    ])
  } catch (error: unknown) {
    ElMessage.error(apiErrorMessage(error))
  } finally {
    submittingAd.value = false
  }
}

async function toggleAdEnabled(row: StoreOpsAdAccountItem, nextEnabled: boolean) {
  const actionText = nextEnabled ? '启用' : '停用'
  try {
    await ElMessageBox.confirm(
      `确定要${actionText}广告账户 ${row.ad_account_id} 吗？`,
      `${actionText}确认`,
      {
        type: 'warning',
      },
    )
    await patchStoreOpsAdAccount(row.id, { is_enabled: nextEnabled })
    ElMessage.success(`广告账户已${actionText}`)
    await Promise.all([
      loadAdAccounts(),
      loadAvailableAdAccounts(),
      loadAudit(),
    ])
  } catch (error: unknown) {
    if (error !== 'cancel') {
      ElMessage.error(apiErrorMessage(error))
    }
  }
}

async function removeAd(row: StoreOpsAdAccountItem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除广告账户 ${row.ad_account_id} 吗？该操作为软删除（is_enabled=0）。`,
      '删除确认',
      {
        type: 'warning',
      },
    )
    await deleteStoreOpsAdAccount(row.id)
    ElMessage.success('广告账户已删除')
    await Promise.all([
      loadAdAccounts(),
      loadAvailableAdAccounts(),
      loadAudit(),
    ])
  } catch (error: unknown) {
    if (error !== 'cancel') {
      ElMessage.error(apiErrorMessage(error))
    }
  }
}

function resetOperatorForm() {
  operatorForm.id = 0
  operatorForm.employee_slug = ''
  operatorForm.utm_keyword = ''
  operatorForm.campaign_keyword = ''
}

function openCreateOperatorDialog() {
  operatorDialogMode.value = 'create'
  resetOperatorForm()
  operatorDialogVisible.value = true
}

function openEditOperatorDialog(row: StoreOpsOperatorItem) {
  operatorDialogMode.value = 'edit'
  operatorForm.id = row.id
  operatorForm.employee_slug = row.employee_slug
  operatorForm.utm_keyword = row.utm_keyword
  operatorForm.campaign_keyword = row.campaign_keyword
  operatorDialogVisible.value = true
}

async function submitOperatorDialog() {
  if (operatorDialogMode.value === 'create' && !operatorForm.employee_slug.trim()) {
    ElMessage.warning('employee_slug 不能为空')
    return
  }
  submittingOperator.value = true
  try {
    if (operatorDialogMode.value === 'create') {
      // 后端已把 display_name 设为可选：留空则自动 = employee_slug
      await createStoreOpsOperator({
        employee_slug: operatorForm.employee_slug.trim().toLowerCase(),
        utm_keyword: operatorForm.utm_keyword.trim() || undefined,
        campaign_keyword: operatorForm.campaign_keyword.trim() || undefined,
      })
      ElMessage.success('运营已新增')
    } else {
      // 编辑只改 utm_keyword / campaign_keyword 两项
      await patchStoreOpsOperator(operatorForm.id, {
        utm_keyword: operatorForm.utm_keyword.trim(),
        campaign_keyword: operatorForm.campaign_keyword.trim(),
      })
      ElMessage.success('运营配置已更新')
    }
    operatorDialogVisible.value = false
    await Promise.all([loadOperators(), loadAudit()])
  } catch (error: unknown) {
    ElMessage.error(apiErrorMessage(error))
  } finally {
    submittingOperator.value = false
  }
}

async function removeOperator(row: StoreOpsOperatorItem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除运营 ${row.employee_slug} 吗？该操作为软删除，历史归因数据会保留。`,
      '删除确认',
      {
        type: 'warning',
      },
    )
    await deleteStoreOpsOperator(row.id)
    ElMessage.success('运营已删除')
    await Promise.all([loadOperators(), loadAudit()])
  } catch (error: unknown) {
    if (error !== 'cancel') {
      ElMessage.error(apiErrorMessage(error))
    }
  }
}

function summarizeAuditChanges(payload?: StoreOpsAuditPayload): string {
  if (!payload?.changes) return '无字段差异'
  const entries = Object.entries(payload.changes)
  if (entries.length === 0) return '无字段差异'
  return entries
    .map(([key, value]) => {
      if (Array.isArray(value) && value.length === 2) {
        return `${key}: ${String(value[0])} -> ${String(value[1])}`
      }
      return `${key}: ${String(value)}`
    })
    .join('；')
}

function formatAvailableShopLabel(item: StoreOpsAvailableShopItem): string {
  const parts: string[] = [item.shop_domain]
  if (item.owner) parts.push(`owner: ${item.owner}`)
  if (item.already_bound) parts.push('已加入')
  return item.owner || item.already_bound
    ? `${item.shop_domain}（${parts.slice(1).join('，')}）`
    : item.shop_domain
}

function formatAvailableAdAccountLabel(item: StoreOpsAvailableAdAccountItem): string {
  const extras: string[] = []
  if (item.owner) extras.push(`owner: ${item.owner}`)
  if (item.already_bound && item.bound_shop_domain) {
    extras.push(`已绑 ${item.bound_shop_domain}`)
  } else if (item.already_bound) {
    extras.push('已绑定')
  }
  return extras.length > 0
    ? `${item.ad_account_id}（${extras.join('，')}）`
    : item.ad_account_id
}

function goBackToReport() {
  void router.push('/store-ops')
}

onMounted(() => {
  void refreshAll()
})
</script>
