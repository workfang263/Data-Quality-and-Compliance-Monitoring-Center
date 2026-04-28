<template>
  <!-- 与其它后台页统一外壳；主从布局用 grid，小屏上下堆叠 -->
  <PageShell>
    <PageHeaderBar title="权限管理" />

    <div v-loading="loading">
      <div class="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <!-- 左侧 Master：用户表（可搜索，仍为同一套 handleUserSelect 数据） -->
        <el-card
          class="rounded-xl border border-gray-100 shadow-sm xl:col-span-4"
          shadow="never"
        >
          <div
            class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <h3 class="text-lg font-semibold text-gray-900">用户列表</h3>
            <el-input
              v-model="userSearch"
              placeholder="搜索用户名"
              clearable
              class="max-w-full sm:max-w-[200px]"
            />
          </div>
          <el-table
            :data="filteredUsers"
            highlight-current-row
            class="w-full"
            @current-change="handleUserSelect"
            style="width: 100%"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="role" label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
                  {{ row.role === 'admin' ? '管理员' : '普通用户' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 右侧 Detail：负责人卡片勾选 + 功能开关（提交 payload 与原先 checkbox 完全一致） -->
        <el-card
          class="rounded-xl border border-gray-100 shadow-sm xl:col-span-8"
          shadow="never"
        >
          <h3 class="mb-4 text-lg font-semibold text-gray-900">权限配置</h3>
          <div v-if="!selectedUser" class="py-12 text-center">
            <el-empty description="请先选择一个用户" />
          </div>
          <div v-else>
            <div class="mb-6">
              <el-tag type="success" size="large" effect="plain">
                当前用户：{{ selectedUser.username }}
                <span v-if="selectedUser.role === 'admin'" class="ml-1 text-amber-600">
                  （管理员）
                </span>
              </el-tag>
            </div>

            <div v-if="selectedUser.role === 'admin'">
              <el-alert type="warning" :closable="false" show-icon>
                管理员拥有所有权限，无需授权
              </el-alert>
            </div>

            <div v-else class="space-y-8">
              <section>
                <h4 class="mb-3 text-base font-semibold text-gray-800">负责人授权</h4>
                <el-checkbox-group
                  v-model="selectedOwners"
                  class="w-full"
                  @change="handleOwnersChange"
                >
                  <div class="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
                    <div
                      v-for="owner in allOwners"
                      :key="owner"
                      :class="[
                        'rounded-lg border p-3 transition-all',
                        selectedOwners.includes(owner)
                          ? 'border-[var(--el-color-primary)] bg-[var(--el-color-primary-light-9)]'
                          : 'border-gray-200 bg-white hover:border-gray-300'
                      ]"
                    >
                      <el-checkbox :label="owner" class="owner-grid-checkbox w-full">
                        <span class="text-sm font-medium text-gray-800">{{ owner }}</span>
                      </el-checkbox>
                    </div>
                  </div>
                </el-checkbox-group>
              </section>

              <section>
                <h4 class="mb-3 text-base font-semibold text-gray-800">功能权限</h4>
                <div class="divide-y divide-gray-100 rounded-lg border border-gray-100 bg-white">
                  <div class="flex items-start justify-between gap-4 px-4 py-4">
                    <div class="min-w-0">
                      <div class="font-medium text-gray-900">允许查看看板总数据和折线图</div>
                      <p class="mt-1 text-sm text-gray-500">
                        控制仪表盘汇总数据与折线图的可见性
                      </p>
                    </div>
                    <el-switch
                      v-model="canViewDashboard"
                      @change="handleExtendedPermissionsChange"
                    />
                  </div>
                  <div class="flex items-start justify-between gap-4 px-4 py-4">
                    <div class="min-w-0">
                      <div class="font-medium text-gray-900">允许编辑映射</div>
                      <p class="mt-1 text-sm text-gray-500">店铺与广告账户负责人映射的编辑入口</p>
                    </div>
                    <el-switch
                      v-model="canEditMappings"
                      @change="handleExtendedPermissionsChange"
                    />
                  </div>
                  <div class="flex items-start justify-between gap-4 px-4 py-4">
                    <div class="min-w-0">
                      <div class="font-medium text-gray-900">允许查看店铺运营与员工归因</div>
                      <p class="mt-1 text-sm text-gray-500">店铺运营页及相关归因数据</p>
                    </div>
                    <el-switch
                      v-model="canViewStoreOps"
                      @change="handleExtendedPermissionsChange"
                    />
                  </div>
                  <div class="flex items-start justify-between gap-4 px-4 py-4">
                    <div class="min-w-0">
                      <div class="font-medium text-gray-900">允许编辑店铺运营配置中心</div>
                      <p class="mt-1 text-sm text-gray-500">
                        控制店铺白名单、广告账户白名单、运营关键词配置与审计入口
                      </p>
                    </div>
                    <el-switch
                      v-model="canEditStoreOpsConfig"
                      @change="handleExtendedPermissionsChange"
                    />
                  </div>
                </div>
              </section>

              <div class="flex flex-wrap gap-3 pt-2">
                <el-button
                  type="primary"
                  :loading="saving"
                  :disabled="!hasChanges"
                  @click="handleSave"
                >
                  保存权限
                </el-button>
                <el-button @click="handleReset">重置</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </PageShell>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getUsers,
  getOwners,
  getUserPermissions,
  getUserExtendedPermissions,
  updateUserPermissions,
  type PermissionUser
} from '../api/permissions'
import PageShell from '../components/PageShell.vue'
import PageHeaderBar from '../components/PageHeaderBar.vue'

const router = useRouter()

// 数据
const users = ref<PermissionUser[]>([])
const userSearch = ref('')

const filteredUsers = computed(() => {
  const q = userSearch.value.trim().toLowerCase()
  if (!q) return users.value
  return users.value.filter(
    (u) => u.username.toLowerCase().includes(q) || String(u.id).includes(q)
  )
})
const allOwners = ref<string[]>([])
const selectedUser = ref<PermissionUser | null>(null)
const selectedOwners = ref<string[]>([])
const originalOwners = ref<string[]>([]) // 原始权限列表，用于判断是否有变化
const canViewDashboard = ref(false)
const canEditMappings = ref(false)
const canViewStoreOps = ref(false)
const canEditStoreOpsConfig = ref(false)
const originalCanViewDashboard = ref(false)
const originalCanEditMappings = ref(false)
const originalCanViewStoreOps = ref(false)
const originalCanEditStoreOpsConfig = ref(false)

// 状态
const loading = ref(false)
const saving = ref(false)

// 计算属性：是否有变化
const hasChanges = computed(() => {
  if (!selectedUser.value) return false
  if (selectedUser.value.role === 'admin') return false
  
  const ownersChanged = [...selectedOwners.value].sort().join(',') !== [...originalOwners.value].sort().join(',')
  const dashboardChanged = canViewDashboard.value !== originalCanViewDashboard.value
  const mappingsChanged = canEditMappings.value !== originalCanEditMappings.value
  const storeOpsChanged = canViewStoreOps.value !== originalCanViewStoreOps.value
  const storeOpsConfigChanged =
    canEditStoreOpsConfig.value !== originalCanEditStoreOpsConfig.value
  
  return (
    ownersChanged ||
    dashboardChanged ||
    mappingsChanged ||
    storeOpsChanged ||
    storeOpsConfigChanged
  )
})

// 加载用户列表
const loadUsers = async () => {
  try {
    loading.value = true
    users.value = await getUsers()
  } catch (err: any) {
    ElMessage.error(err.message || '加载用户列表失败')
    // 如果是403错误，说明不是管理员，跳转到首页
    if (err.response?.status === 403) {
      router.push('/dashboard')
    }
  } finally {
    loading.value = false
  }
}

// 加载负责人列表
const loadOwners = async () => {
  try {
    allOwners.value = await getOwners()
  } catch (err: any) {
    ElMessage.error(err.message || '加载负责人列表失败')
  }
}

// 加载用户权限
const loadUserPermissions = async (userId: number) => {
  try {
    // 加载负责人权限
    const owners = await getUserPermissions(userId)
    selectedOwners.value = [...owners]
    originalOwners.value = [...owners]
    
    // 加载扩展权限
    const extendedPermissions = await getUserExtendedPermissions(userId)
    canViewDashboard.value = extendedPermissions.can_view_dashboard
    canEditMappings.value = extendedPermissions.can_edit_mappings
    canViewStoreOps.value = extendedPermissions.can_view_store_ops ?? false
    canEditStoreOpsConfig.value =
      extendedPermissions.can_edit_store_ops_config ?? false
    originalCanViewDashboard.value = extendedPermissions.can_view_dashboard
    originalCanEditMappings.value = extendedPermissions.can_edit_mappings
    originalCanViewStoreOps.value = extendedPermissions.can_view_store_ops ?? false
    originalCanEditStoreOpsConfig.value =
      extendedPermissions.can_edit_store_ops_config ?? false
  } catch (err: any) {
    ElMessage.error(err.message || '加载用户权限失败')
  }
}

// 处理用户选择
const handleUserSelect = async (user: PermissionUser | null) => {
  if (!user) {
    selectedUser.value = null
    selectedOwners.value = []
    originalOwners.value = []
    canViewDashboard.value = false
    canEditMappings.value = false
    canViewStoreOps.value = false
    canEditStoreOpsConfig.value = false
    originalCanViewDashboard.value = false
    originalCanEditMappings.value = false
    originalCanViewStoreOps.value = false
    originalCanEditStoreOpsConfig.value = false
    return
  }
  
  selectedUser.value = user
  
  if (user.role === 'admin') {
    // 管理员不需要授权
    selectedOwners.value = []
    originalOwners.value = []
    canViewDashboard.value = true
    canEditMappings.value = true
    canViewStoreOps.value = true
    canEditStoreOpsConfig.value = true
    originalCanViewDashboard.value = true
    originalCanEditMappings.value = true
    originalCanViewStoreOps.value = true
    originalCanEditStoreOpsConfig.value = true
  } else {
    // 加载该用户的权限
    await loadUserPermissions(user.id)
  }
}

// 处理负责人选择变化
const handleOwnersChange = () => {
  // 变化已通过hasChanges计算属性判断
}

// 处理扩展权限变化
const handleExtendedPermissionsChange = () => {
  // 变化已通过hasChanges计算属性判断
}

// 保存权限
const handleSave = async () => {
  if (!selectedUser.value || selectedUser.value.role === 'admin') return
  
  try {
    await ElMessageBox.confirm(
      `确定要更新用户 "${selectedUser.value.username}" 的权限吗？`,
      '确认保存',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    saving.value = true
    await updateUserPermissions(selectedUser.value.id, {
      owners: selectedOwners.value,
      can_view_dashboard: canViewDashboard.value,
      can_edit_mappings: canEditMappings.value,
      can_view_store_ops: canViewStoreOps.value,
      can_edit_store_ops_config: canEditStoreOpsConfig.value,
    })
    
    // 更新原始权限列表
    originalOwners.value = [...selectedOwners.value]
    originalCanViewDashboard.value = canViewDashboard.value
    originalCanEditMappings.value = canEditMappings.value
    originalCanViewStoreOps.value = canViewStoreOps.value
    originalCanEditStoreOpsConfig.value = canEditStoreOpsConfig.value
    
    ElMessage.success('权限更新成功')
  } catch (err: any) {
    if (err !== 'cancel') {
      ElMessage.error(err.message || '保存权限失败')
    }
  } finally {
    saving.value = false
  }
}

// 重置权限
const handleReset = () => {
  if (!selectedUser.value) return
  
  selectedOwners.value = [...originalOwners.value]
  canViewDashboard.value = originalCanViewDashboard.value
  canEditMappings.value = originalCanEditMappings.value
  canViewStoreOps.value = originalCanViewStoreOps.value
  canEditStoreOpsConfig.value = originalCanEditStoreOpsConfig.value
  ElMessage.info('已重置为原始权限')
}

// 初始化
onMounted(async () => {
  await Promise.all([loadUsers(), loadOwners()])
})
</script>

<style scoped>
.owner-grid-checkbox :deep(.el-checkbox__label) {
  width: 100%;
  white-space: normal;
  line-height: 1.35;
}
</style>

