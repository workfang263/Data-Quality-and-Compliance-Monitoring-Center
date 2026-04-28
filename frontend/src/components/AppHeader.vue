<template>
  <!-- 顶栏：品牌区 + 横向菜单 + 用户区；业务逻辑（权限菜单）不变 -->
  <el-header
    class="sticky top-0 z-50 flex h-[60px] items-center justify-between border-b border-gray-100 bg-white px-4 shadow-sm sm:px-6"
  >
    <div class="flex min-w-0 flex-1 items-center gap-6">
      <div class="flex shrink-0 items-center gap-2">
        <el-icon class="text-2xl text-[var(--el-color-primary)]" aria-hidden="true">
          <Monitor />
        </el-icon>
        <h1 class="truncate text-lg font-semibold text-[var(--el-color-primary)] sm:text-xl">
          Shoplazza Dashboard
        </h1>
      </div>
      <el-menu
        :default-active="activeMenu"
        mode="horizontal"
        ellipsis
        class="header-menu min-w-0 flex-1 border-none"
        @select="handleMenuSelect"
      >
        <el-menu-item index="/dashboard">看板</el-menu-item>
        <el-menu-item index="/owners">负责人汇总</el-menu-item>
        <el-menu-item index="/mappings">映射编辑</el-menu-item>
        <el-menu-item v-if="canMappingsAudit" index="/mapping-audit">映射操作记录</el-menu-item>
        <el-menu-item v-if="canStoreOps" index="/store-ops">店铺运营</el-menu-item>
        <el-menu-item v-if="isAdmin" index="/permissions">权限管理</el-menu-item>
      </el-menu>
    </div>
    <div class="flex shrink-0 items-center pl-2">
      <el-dropdown @command="handleCommand">
        <span
          class="flex cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-sm text-gray-800 transition-colors hover:bg-gray-100"
        >
          <el-icon><User /></el-icon>
          <span>{{ username }}</span>
          <el-icon class="el-icon--right"><CaretBottom /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </el-header>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, CaretBottom, Monitor } from '@element-plus/icons-vue'
import { logout, getCurrentUser } from '../api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()

const username = ref('')
const userRole = ref('')
const canViewStoreOps = ref(false)
const canEditMappings = ref(false)

// 当前激活的菜单项
const activeMenu = computed(() => {
  if (route.path.startsWith('/store-ops')) {
    return '/store-ops'
  }
  return route.path
})

// 是否为管理员
const isAdmin = computed(() => {
  return userRole.value === 'admin'
})

// 店铺运营菜单：管理员或显式授权
const canStoreOps = computed(() => {
  return userRole.value === 'admin' || canViewStoreOps.value === true
})

// 与后端审计接口一致：管理员或可编辑映射
const canMappingsAudit = computed(() => {
  return userRole.value === 'admin' || canEditMappings.value === true
})

// 加载用户信息
const applyUserInfo = (user: {
  username?: string
  role?: string
  can_view_store_ops?: boolean
  can_edit_mappings?: boolean
}) => {
  username.value = user.username || '用户'
  userRole.value = user.role || 'user'
  canViewStoreOps.value = user.can_view_store_ops === true
  canEditMappings.value = user.can_edit_mappings === true
}

const loadUserInfo = async () => {
  // 优先以服务端实时用户信息为准，避免展示被旧缓存卡住
  try {
    const user = await getCurrentUser()
    applyUserInfo(user)
    localStorage.setItem('user', JSON.stringify(user))
    return
  } catch (err) {
    // 忽略并回退到本地缓存
  }

  const userStr = localStorage.getItem('user')
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
      applyUserInfo(user)
    } catch (e) {
      username.value = '用户'
      userRole.value = 'user'
      canViewStoreOps.value = false
      canEditMappings.value = false
    }
  } else {
    username.value = '用户'
    userRole.value = 'user'
    canViewStoreOps.value = false
    canEditMappings.value = false
  }
}

// 处理菜单选择
const handleMenuSelect = (index: string) => {
  router.push(index)
}

// 处理下拉菜单命令
const handleCommand = async (command: string) => {
  if (command === 'logout') {
    try {
      await logout()
    } catch (err) {
      // 即使登出API失败，也清除本地token
      console.error('登出失败:', err)
    }
    
    // 清除本地存储
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    
    ElMessage.success('已退出登录')
    
    // 跳转到登录页
    router.push('/login')
  }
}

onMounted(() => {
  void loadUserInfo()
})
</script>

<style scoped>
/* 横向菜单与顶栏高度对齐，去掉 Element 默认底边框以配合自定义顶栏 */
.header-menu {
  border-bottom: none !important;
  --el-menu-horizontal-height: 60px;
}
.header-menu :deep(.el-menu-item) {
  border-bottom: none !important;
}
</style>

