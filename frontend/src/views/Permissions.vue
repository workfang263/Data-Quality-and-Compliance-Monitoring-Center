<template>
  <div class="permissions-page">
    <div class="permissions-container">
      <h2>权限管理</h2>
      
      <div class="permissions-content">
        <!-- 左侧：用户列表 -->
        <div class="users-section">
          <h3>用户列表</h3>
          <el-table
            :data="users"
            highlight-current-row
            @current-change="handleUserSelect"
            style="width: 100%"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="role" label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
                  {{ row.role === 'admin' ? '管理员' : '普通用户' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
        
        <!-- 右侧：负责人授权 -->
        <div class="owners-section">
          <h3>负责人授权</h3>
          <div v-if="!selectedUser" class="empty-state">
            <el-empty description="请先选择一个用户" />
          </div>
          <div v-else>
            <div class="selected-user-info">
              <el-tag type="info" size="large">
                当前用户：{{ selectedUser.username }}
                <span v-if="selectedUser.role === 'admin'" class="admin-tag">（管理员）</span>
              </el-tag>
            </div>
            
            <div v-if="selectedUser.role === 'admin'" class="admin-notice">
              <el-alert type="warning" :closable="false" show-icon>
                管理员拥有所有权限，无需授权
              </el-alert>
            </div>
            
            <div v-else class="owners-checkbox-list">
              <div class="permissions-section">
                <h4>负责人权限</h4>
                <el-checkbox-group v-model="selectedOwners" @change="handleOwnersChange">
                  <div class="checkbox-item" v-for="owner in allOwners" :key="owner">
                    <el-checkbox :label="owner">{{ owner }}</el-checkbox>
                  </div>
                </el-checkbox-group>
              </div>
              
              <div class="permissions-section">
                <h4>功能权限</h4>
                <div class="extended-permissions">
                  <el-checkbox v-model="canViewDashboard" @change="handleExtendedPermissionsChange">
                    允许查看看板总数据和折线图
                  </el-checkbox>
                  <el-checkbox v-model="canEditMappings" @change="handleExtendedPermissionsChange">
                    允许编辑映射
                  </el-checkbox>
                  <el-checkbox v-model="canViewStoreOps" @change="handleExtendedPermissionsChange">
                    允许查看店铺运营与员工归因
                  </el-checkbox>
                </div>
              </div>
              
              <div class="actions">
                <el-button
                  type="primary"
                  :loading="saving"
                  @click="handleSave"
                  :disabled="!hasChanges"
                >
                  保存权限
                </el-button>
                <el-button @click="handleReset">重置</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
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

const router = useRouter()

// 数据
const users = ref<PermissionUser[]>([])
const allOwners = ref<string[]>([])
const selectedUser = ref<PermissionUser | null>(null)
const selectedOwners = ref<string[]>([])
const originalOwners = ref<string[]>([]) // 原始权限列表，用于判断是否有变化
const canViewDashboard = ref(false)
const canEditMappings = ref(false)
const canViewStoreOps = ref(false)
const originalCanViewDashboard = ref(false)
const originalCanEditMappings = ref(false)
const originalCanViewStoreOps = ref(false)

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
  
  return ownersChanged || dashboardChanged || mappingsChanged || storeOpsChanged
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
    originalCanViewDashboard.value = extendedPermissions.can_view_dashboard
    originalCanEditMappings.value = extendedPermissions.can_edit_mappings
    originalCanViewStoreOps.value = extendedPermissions.can_view_store_ops ?? false
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
    canViewStoreOps.value = false
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
    originalCanViewDashboard.value = true
    originalCanEditMappings.value = true
    originalCanViewStoreOps.value = true
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
      can_view_store_ops: canViewStoreOps.value
    })
    
    // 更新原始权限列表
    originalOwners.value = [...selectedOwners.value]
    originalCanViewDashboard.value = canViewDashboard.value
    originalCanEditMappings.value = canEditMappings.value
    originalCanViewStoreOps.value = canViewStoreOps.value
    
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
  ElMessage.info('已重置为原始权限')
}

// 初始化
onMounted(async () => {
  await Promise.all([loadUsers(), loadOwners()])
})
</script>

<style scoped>
.permissions-page {
  min-height: 100vh;
  padding: 20px;
  background: #f5f5f5;
}

.permissions-container {
  max-width: 1600px;
  margin: 0 auto;
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.permissions-container h2 {
  margin-bottom: 20px;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.permissions-content {
  display: flex;
  gap: 20px;
}

.users-section {
  flex: 1;
  min-width: 300px;
}

.owners-section {
  flex: 1;
  min-width: 400px;
}

.users-section h3,
.owners-section h3 {
  margin-bottom: 15px;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.empty-state {
  padding: 40px 0;
}

.selected-user-info {
  margin-bottom: 20px;
}

.admin-tag {
  margin-left: 8px;
  color: #f56c6c;
}

.admin-notice {
  margin-top: 20px;
}

.owners-checkbox-list {
  margin-top: 20px;
}

.permissions-section {
  margin-bottom: 30px;
}

.permissions-section h4 {
  margin-bottom: 15px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.extended-permissions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.checkbox-item {
  margin-bottom: 12px;
}

.actions {
  margin-top: 30px;
  display: flex;
  gap: 10px;
}

@media (max-width: 1200px) {
  .permissions-content {
    flex-direction: column;
  }
}
</style>

