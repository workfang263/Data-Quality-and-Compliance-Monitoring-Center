<template>
  <div class="mappings-page">
    <!-- 页面标题 -->
    <h2>映射编辑</h2>
    
    <!-- 权限提示 -->
    <el-alert
      v-if="!canEditMappings"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 20px"
    >
      您没有权限编辑映射，请联系管理员授权
    </el-alert>
    
    <!-- 三个映射编辑区域 -->
    <el-row :gutter="20">
      <!-- 店铺映射 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>店铺 → 负责人映射</span>
            </div>
          </template>
          
          <div v-if="storeLoading" style="text-align: center; padding: 20px">
            <el-icon class="is-loading"><Loading /></el-icon>
            <p>加载中...</p>
          </div>
          
          <div v-else-if="storeError" style="text-align: center; padding: 20px">
            <el-alert type="error" :closable="false">{{ storeError }}</el-alert>
          </div>
          
          <div v-else-if="storeMappings.length === 0" style="text-align: center; padding: 20px">
            <el-empty description="暂无店铺映射数据" />
          </div>
          
          <div v-else>
            <div v-for="mapping in storeMappings" :key="mapping.id" class="mapping-item">
              <div class="mapping-label">店铺: {{ mapping.shop_domain }}</div>
              <el-input
                v-model="mapping.editOwner"
                placeholder="请输入负责人名称"
                :disabled="!canEditMappings"
                @change="handleStoreMappingChange(mapping)"
              />
              <el-button
                v-if="mapping.editOwner !== mapping.owner && canEditMappings"
                type="primary"
                size="small"
                :loading="mapping.saving"
                @click="saveStoreMapping(mapping)"
                style="margin-top: 8px; width: 100%"
              >
                保存
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <!-- Facebook映射 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>Facebook广告账户 → 负责人映射</span>
            </div>
          </template>
          
          <div v-if="facebookLoading" style="text-align: center; padding: 20px">
            <el-icon class="is-loading"><Loading /></el-icon>
            <p>加载中...</p>
          </div>
          
          <div v-else-if="facebookError" style="text-align: center; padding: 20px">
            <el-alert type="error" :closable="false">{{ facebookError }}</el-alert>
          </div>
          
          <div v-else-if="facebookMappings.length === 0" style="text-align: center; padding: 20px">
            <el-empty description="暂无Facebook映射数据" />
          </div>
          
          <div v-else>
            <div v-for="mapping in facebookMappings" :key="mapping.id" class="mapping-item">
              <div class="mapping-label">账户: {{ mapping.ad_account_id }}</div>
              <el-input
                v-model="mapping.editOwner"
                placeholder="请输入负责人名称"
                :disabled="!canEditMappings"
                @change="handleFacebookMappingChange(mapping)"
              />
              <el-button
                v-if="mapping.editOwner !== mapping.owner && canEditMappings"
                type="primary"
                size="small"
                :loading="mapping.saving"
                @click="saveFacebookMapping(mapping)"
                style="margin-top: 8px; width: 100%"
              >
                保存
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <!-- TikTok映射 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>TikTok广告账户 → 负责人映射</span>
            </div>
          </template>
          
          <div v-if="tiktokLoading" style="text-align: center; padding: 20px">
            <el-icon class="is-loading"><Loading /></el-icon>
            <p>加载中...</p>
          </div>
          
          <div v-else-if="tiktokError" style="text-align: center; padding: 20px">
            <el-alert type="error" :closable="false">{{ tiktokError }}</el-alert>
          </div>
          
          <div v-else-if="tiktokMappings.length === 0" style="text-align: center; padding: 20px">
            <el-empty description="暂无TikTok映射数据" />
          </div>
          
          <div v-else>
            <div v-for="mapping in tiktokMappings" :key="mapping.id" class="mapping-item">
              <div class="mapping-label">账户: {{ mapping.ad_account_id }}</div>
              <el-input
                v-model="mapping.editOwner"
                placeholder="请输入负责人名称"
                :disabled="!canEditMappings"
                @change="handleTikTokMappingChange(mapping)"
              />
              <el-button
                v-if="mapping.editOwner !== mapping.owner && canEditMappings"
                type="primary"
                size="small"
                :loading="mapping.saving"
                @click="saveTikTokMapping(mapping)"
                style="margin-top: 8px; width: 100%"
              >
                保存
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import {
  getStoreMappings,
  getFacebookMappings,
  getTikTokMappings,
  updateStoreMapping,
  updateFacebookMapping,
  updateTikTokMapping,
  type StoreMapping,
  type AdAccountMapping
} from '../api/mappings'
import { getCurrentUser } from '../api/auth'

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

// 处理店铺映射变化
const handleStoreMappingChange = (mapping: EditableStoreMapping) => {
  // 可以在这里添加验证逻辑
}

// 处理Facebook映射变化
const handleFacebookMappingChange = (mapping: EditableAdAccountMapping) => {
  // 可以在这里添加验证逻辑
}

// 处理TikTok映射变化
const handleTikTokMappingChange = (mapping: EditableAdAccountMapping) => {
  // 可以在这里添加验证逻辑
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
.mappings-page {
  padding: 20px;
  max-width: 1600px;
  margin: 0 auto;
}

.mappings-page h2 {
  margin-bottom: 20px;
  font-size: 24px;
  font-weight: 600;
}

.card-header {
  font-weight: 600;
  font-size: 16px;
}

.mapping-item {
  margin-bottom: 20px;
  padding: 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--el-border-radius-base);
}

.mapping-item:last-child {
  margin-bottom: 0;
}

.mapping-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
</style>

