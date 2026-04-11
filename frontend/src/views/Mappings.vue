<template>
  <PageShell>
    <PageHeaderBar title="映射编辑">
      <template #actions>
        <router-link v-if="canEditMappings" to="/mapping-audit" class="inline-flex">
          <el-button type="primary">映射操作记录</el-button>
        </router-link>
      </template>
    </PageHeaderBar>

    <el-alert
      v-if="!canEditMappings"
      type="warning"
      :closable="false"
      show-icon
      class="mb-6"
    >
      您没有权限编辑映射，请联系管理员授权
    </el-alert>

    <!-- 三列栅格：与 MappingColumn 子组件组合，避免三套重复模板 -->
    <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <MappingColumn
        title="店铺 → 负责人映射"
        resource-kind="store"
        add-label="新增店铺"
        :can-edit="canEditMappings"
        :loading="storeLoading"
        :error="storeError"
        empty-description="暂无店铺映射数据"
        :items="storeMappings"
        @add="openStoreDialog"
        @row-change="onStoreRowChange"
        @save="onSaveStoreRow"
      />
      <MappingColumn
        title="Facebook广告账户 → 负责人映射"
        resource-kind="ad"
        add-label="新增账户"
        :can-edit="canEditMappings"
        :loading="facebookLoading"
        :error="facebookError"
        empty-description="暂无 Facebook 映射数据"
        :items="facebookMappings"
        @add="openFacebookDialog"
        @row-change="onFacebookRowChange"
        @save="onSaveFacebookRow"
      />
      <MappingColumn
        title="TikTok广告账户 → 负责人映射"
        resource-kind="ad"
        add-label="新增账户"
        :can-edit="canEditMappings"
        :loading="tiktokLoading"
        :error="tiktokError"
        empty-description="暂无 TikTok 映射数据"
        :items="tiktokMappings"
        @add="openTiktokDialog"
        @row-change="onTikTokRowChange"
        @save="onSaveTikTokRow"
      />
    </div>

    <!-- 新增店铺 -->
    <el-dialog
      v-model="storeDialogVisible"
      title="新增 / 更新店铺映射"
      width="520px"
      destroy-on-close
      @closed="resetStoreForm"
    >
      <el-alert type="info" :closable="false" show-icon class="dialog-tip">
        店铺侧无需配置时区：订单时间以店匠 API 为准，系统将按现有规则统一为北京时间入库。
      </el-alert>
      <el-form label-position="top" class="dialog-form">
        <el-form-item label="店铺域名" required>
          <el-input v-model="storeForm.shop_domain" placeholder="例如 store.example.myshoplazza.com" clearable />
        </el-form-item>
        <el-form-item label="负责人" required>
          <el-autocomplete
            v-model="storeForm.owner"
            :fetch-suggestions="fetchOwnerSuggestions"
            clearable
            style="width: 100%"
            placeholder="可选择已有负责人或输入新名称"
          />
        </el-form-item>
        <el-form-item label="Access Token" required>
          <el-input
            v-model="storeForm.access_token"
            type="textarea"
            :rows="3"
            placeholder="店匠 OpenAPI 访问令牌"
          />
        </el-form-item>
        <el-form-item label="启用同步">
          <el-switch v-model="storeForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="storeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="storeDialogSubmitting" @click="submitStoreForm">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 新增 Facebook -->
    <el-dialog
      v-model="facebookDialogVisible"
      title="新增 / 更新 Facebook 广告账户"
      width="520px"
      destroy-on-close
      @closed="resetFacebookForm"
    >
      <el-alert type="info" :closable="false" show-icon class="dialog-tip">
        无需填写时区：保存后系统将从 Meta 读取该广告账户的 timezone，并用于将花费换算为北京时间。
      </el-alert>
      <el-form label-position="top" class="dialog-form">
        <el-form-item label="广告账户 ID" required>
          <el-input
            v-model="facebookForm.ad_account_id"
            placeholder="纯数字或 act_ 前缀均可"
            clearable
          />
        </el-form-item>
        <el-form-item label="负责人" required>
          <el-autocomplete
            v-model="facebookForm.owner"
            :fetch-suggestions="fetchOwnerSuggestions"
            clearable
            style="width: 100%"
            placeholder="可选择已有负责人或输入新名称"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="facebookDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="facebookDialogSubmitting" @click="submitFacebookForm">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 新增 TikTok -->
    <el-dialog
      v-model="tiktokDialogVisible"
      title="新增 / 更新 TikTok 广告主"
      width="520px"
      destroy-on-close
      @closed="resetTiktokForm"
    >
      <el-alert type="info" :closable="false" show-icon class="dialog-tip">
        无需填写时区：保存后系统将从 TikTok 读取该广告主账户的时区并换算为北京时间；服务端按配置的 BC Token
        顺序尝试拉取。
      </el-alert>
      <el-form label-position="top" class="dialog-form">
        <el-form-item label="Advertiser ID（纯数字）" required>
          <el-input v-model="tiktokForm.ad_account_id" placeholder="TikTok 广告主 ID" clearable />
        </el-form-item>
        <el-form-item label="负责人" required>
          <el-autocomplete
            v-model="tiktokForm.owner"
            :fetch-suggestions="fetchOwnerSuggestions"
            clearable
            style="width: 100%"
            placeholder="可选择已有负责人或输入新名称"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tiktokDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="tiktokDialogSubmitting" @click="submitTiktokForm">
          保存
        </el-button>
      </template>
    </el-dialog>
  </PageShell>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getStoreMappings,
  getFacebookMappings,
  getTikTokMappings,
  updateStoreMapping,
  updateFacebookMapping,
  updateTikTokMapping,
  createStoreMapping,
  createFacebookMapping,
  createTikTokMapping,
  getOwnerSuggestions,
  type StoreMapping,
  type AdAccountMapping
} from '../api/mappings'
import { getCurrentUser } from '../api/auth'
import PageShell from '../components/PageShell.vue'
import PageHeaderBar from '../components/PageHeaderBar.vue'
import MappingColumn, {
  type MappingColumnRow
} from '../components/MappingColumn.vue'

// 扩展映射类型，添加编辑状态
interface EditableStoreMapping extends StoreMapping {
  editOwner: string
  saving: boolean
}

interface EditableAdAccountMapping extends AdAccountMapping {
  editOwner: string
  saving: boolean
}

// 店铺映射
const storeMappings = ref<EditableStoreMapping[]>([])
const storeLoading = ref(false)
const storeError = ref<string>('')

// Facebook映射
const facebookMappings = ref<EditableAdAccountMapping[]>([])
const facebookLoading = ref(false)
const facebookError = ref<string>('')

// TikTok映射
const tiktokMappings = ref<EditableAdAccountMapping[]>([])
const tiktokLoading = ref(false)
const tiktokError = ref<string>('')

// 权限检查
const canEditMappings = ref(false)

// ---------- 新增映射弹窗 ----------
const storeDialogVisible = ref(false)
const storeDialogSubmitting = ref(false)
const storeForm = ref({
  shop_domain: '',
  owner: '',
  access_token: '',
  is_active: true
})

const facebookDialogVisible = ref(false)
const facebookDialogSubmitting = ref(false)
const facebookForm = ref({
  ad_account_id: '',
  owner: ''
})

const tiktokDialogVisible = ref(false)
const tiktokDialogSubmitting = ref(false)
const tiktokForm = ref({
  ad_account_id: '',
  owner: ''
})

type OwnerSuggest = { value: string }

function collectOwnerCandidates(): string[] {
  const s = new Set<string>()
  storeMappings.value.forEach((m) => {
    if (m.owner) s.add(m.owner)
  })
  facebookMappings.value.forEach((m) => {
    if (m.owner) s.add(m.owner)
  })
  tiktokMappings.value.forEach((m) => {
    if (m.owner) s.add(m.owner)
  })
  return Array.from(s).sort()
}

async function fetchOwnerSuggestions(q: string, cb: (arg: OwnerSuggest[]) => void) {
  const qtrim = (q || '').trim()
  try {
    const owners = await getOwnerSuggestions(qtrim, 40)
    cb((owners || []).map((value) => ({ value })))
  } catch {
    const all = collectOwnerCandidates()
    const filtered = qtrim ? all.filter((o) => o.includes(qtrim)) : all
    cb(filtered.slice(0, 40).map((value) => ({ value })))
  }
}

function openStoreDialog() {
  resetStoreForm()
  storeDialogVisible.value = true
}

function resetStoreForm() {
  storeForm.value = {
    shop_domain: '',
    owner: '',
    access_token: '',
    is_active: true
  }
}

async function submitStoreForm() {
  const domain = storeForm.value.shop_domain.trim().toLowerCase()
  const owner = storeForm.value.owner.trim()
  const token = storeForm.value.access_token.trim()
  if (!domain || !owner || !token) {
    ElMessage.warning('请填写店铺域名、负责人和 Access Token')
    return
  }
  storeDialogSubmitting.value = true
  try {
    await createStoreMapping({
      shop_domain: domain,
      owner,
      access_token: token,
      is_active: storeForm.value.is_active
    })
    ElMessage.success('店铺映射已保存')
    storeDialogVisible.value = false
    await loadStoreMappings()
  } catch (err: unknown) {
    const e = err as { message?: string }
    ElMessage.error(e.message || '保存失败')
  } finally {
    storeDialogSubmitting.value = false
  }
}

function openFacebookDialog() {
  resetFacebookForm()
  facebookDialogVisible.value = true
}

function resetFacebookForm() {
  facebookForm.value = { ad_account_id: '', owner: '' }
}

async function submitFacebookForm() {
  const owner = facebookForm.value.owner.trim()
  const rawId = facebookForm.value.ad_account_id.trim()
  if (!owner || !rawId) {
    ElMessage.warning('请填写广告账户 ID 和负责人')
    return
  }
  facebookDialogSubmitting.value = true
  try {
    const res = await createFacebookMapping({
      ad_account_id: rawId,
      owner
    })
    if (res.timezone_sync?.ok) {
      ElMessage.success(
        `已保存 ${res.ad_account_id}，时区：${res.timezone_sync.timezone ?? '已写入'}`
      )
    } else {
      ElMessage.warning(
        `映射已保存，但时区未拉取成功：${res.timezone_sync?.message || '未知原因'}`
      )
    }
    facebookDialogVisible.value = false
    await loadFacebookMappings()
  } catch (err: unknown) {
    const e = err as { message?: string }
    ElMessage.error(e.message || '保存失败')
  } finally {
    facebookDialogSubmitting.value = false
  }
}

function openTiktokDialog() {
  resetTiktokForm()
  tiktokDialogVisible.value = true
}

function resetTiktokForm() {
  tiktokForm.value = { ad_account_id: '', owner: '' }
}

async function submitTiktokForm() {
  const owner = tiktokForm.value.owner.trim()
  const aid = tiktokForm.value.ad_account_id.trim()
  if (!owner || !aid) {
    ElMessage.warning('请填写 Advertiser ID 和负责人')
    return
  }
  if (!/^\d+$/.test(aid)) {
    ElMessage.warning('TikTok Advertiser ID 须为纯数字')
    return
  }
  tiktokDialogSubmitting.value = true
  try {
    const res = await createTikTokMapping({
      ad_account_id: aid,
      owner
    })
    if (res.timezone_sync?.ok) {
      ElMessage.success(
        `已保存 ${res.ad_account_id}，时区：${res.timezone_sync.timezone ?? '已写入'}`
      )
    } else {
      ElMessage.warning(
        `映射已保存，但时区未拉取成功：${res.timezone_sync?.message || '未知原因'}`
      )
    }
    tiktokDialogVisible.value = false
    await loadTikTokMappings()
  } catch (err: unknown) {
    const e = err as { message?: string }
    ElMessage.error(e.message || '保存失败')
  } finally {
    tiktokDialogSubmitting.value = false
  }
}

// 检查用户权限
const checkUserPermissions = async () => {
  try {
    const user = await getCurrentUser()
    // 管理员自动拥有所有权限
    if (user.role === 'admin') {
      canEditMappings.value = true
      return
    }
    
    // 普通用户需要检查扩展权限
    // 从localStorage获取用户信息（包含扩展权限）
    const userStr = localStorage.getItem('user')
    if (userStr) {
      try {
        const userInfo = JSON.parse(userStr)
        canEditMappings.value = userInfo.can_edit_mappings === true
      } catch (e) {
        canEditMappings.value = false
      }
    } else {
      canEditMappings.value = false
    }
  } catch (err) {
    // 获取用户信息失败，默认无权限
    canEditMappings.value = false
  }
}

// 加载店铺映射
const loadStoreMappings = async () => {
  storeLoading.value = true
  storeError.value = ''
  
  try {
    const data = await getStoreMappings()
    storeMappings.value = data.map(m => ({
      ...m,
      editOwner: m.owner,
      saving: false
    }))
  } catch (err: any) {
    storeError.value = err.message || '获取数据失败'
    ElMessage.error(storeError.value)
  } finally {
    storeLoading.value = false
  }
}

// 加载Facebook映射
const loadFacebookMappings = async () => {
  facebookLoading.value = true
  facebookError.value = ''
  
  try {
    const data = await getFacebookMappings()
    facebookMappings.value = data.map(m => ({
      ...m,
      editOwner: m.owner,
      saving: false
    }))
  } catch (err: any) {
    facebookError.value = err.message || '获取数据失败'
    ElMessage.error(facebookError.value)
  } finally {
    facebookLoading.value = false
  }
}

// 加载TikTok映射
const loadTikTokMappings = async () => {
  tiktokLoading.value = true
  tiktokError.value = ''
  
  try {
    const data = await getTikTokMappings()
    tiktokMappings.value = data.map(m => ({
      ...m,
      editOwner: m.owner,
      saving: false
    }))
  } catch (err: any) {
    tiktokError.value = err.message || '获取数据失败'
    ElMessage.error(tiktokError.value)
  } finally {
    tiktokLoading.value = false
  }
}

// 处理店铺映射变化（预留：后续可在此处做字段校验）
const handleStoreMappingChange = (_mapping: EditableStoreMapping) => {
  void _mapping
}

// 处理Facebook映射变化
const handleFacebookMappingChange = (_mapping: EditableAdAccountMapping) => {
  void _mapping
}

// 处理TikTok映射变化
const handleTikTokMappingChange = (_mapping: EditableAdAccountMapping) => {
  void _mapping
}

/** 子组件 emitted 的联合类型收窄回具体映射行，再交给原有 save/change 逻辑 */
function onStoreRowChange(row: MappingColumnRow) {
  handleStoreMappingChange(row as EditableStoreMapping)
}
function onFacebookRowChange(row: MappingColumnRow) {
  handleFacebookMappingChange(row as EditableAdAccountMapping)
}
function onTikTokRowChange(row: MappingColumnRow) {
  handleTikTokMappingChange(row as EditableAdAccountMapping)
}
function onSaveStoreRow(row: MappingColumnRow) {
  saveStoreMapping(row as EditableStoreMapping)
}
function onSaveFacebookRow(row: MappingColumnRow) {
  saveFacebookMapping(row as EditableAdAccountMapping)
}
function onSaveTikTokRow(row: MappingColumnRow) {
  saveTikTokMapping(row as EditableAdAccountMapping)
}

// 保存店铺映射
const saveStoreMapping = async (mapping: EditableStoreMapping) => {
  if (!mapping.editOwner.trim()) {
    ElMessage.warning('请输入负责人名称')
    return
  }
  
  mapping.saving = true
  
  try {
    const result = await updateStoreMapping(mapping.id, mapping.editOwner.trim())
    mapping.owner = result.owner
    ElMessage.success(`已更新: ${mapping.shop_domain} -> ${result.owner}，重新聚合了 ${result.affected_dates_count} 个日期的数据`)
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
    // 恢复原值
    mapping.editOwner = mapping.owner
  } finally {
    mapping.saving = false
  }
}

// 保存Facebook映射
const saveFacebookMapping = async (mapping: EditableAdAccountMapping) => {
  if (!mapping.editOwner.trim()) {
    ElMessage.warning('请输入负责人名称')
    return
  }
  
  mapping.saving = true
  
  try {
    const result = await updateFacebookMapping(mapping.id, mapping.editOwner.trim())
    mapping.owner = result.owner
    ElMessage.success(`已更新: ${mapping.ad_account_id} -> ${result.owner}，重新聚合了 ${result.affected_dates_count} 个日期的数据`)
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
    // 恢复原值
    mapping.editOwner = mapping.owner
  } finally {
    mapping.saving = false
  }
}

// 保存TikTok映射
const saveTikTokMapping = async (mapping: EditableAdAccountMapping) => {
  if (!mapping.editOwner.trim()) {
    ElMessage.warning('请输入负责人名称')
    return
  }
  
  mapping.saving = true
  
  try {
    const result = await updateTikTokMapping(mapping.id, mapping.editOwner.trim())
    mapping.owner = result.owner
    ElMessage.success(`已更新: ${mapping.ad_account_id} -> ${result.owner}，重新聚合了 ${result.affected_dates_count} 个日期的数据`)
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
    // 恢复原值
    mapping.editOwner = mapping.owner
  } finally {
    mapping.saving = false
  }
}

// 初始化
onMounted(async () => {
  // 先检查权限
  await checkUserPermissions()
  
  // 加载数据
  await Promise.all([
    loadStoreMappings(),
    loadFacebookMappings(),
    loadTikTokMappings()
  ])
})
</script>

<style scoped>
.dialog-tip {
  margin-bottom: 16px;
}

.dialog-form {
  margin-top: 8px;
}
</style>

