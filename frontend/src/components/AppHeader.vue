<template>
  <el-header class="app-header">
    <div class="header-left">
      <h1 class="logo">Shoplazza Dashboard</h1>
      <el-menu
        :default-active="activeMenu"
        mode="horizontal"
        @select="handleMenuSelect"
        class="header-menu"
      >
        <el-menu-item index="/dashboard">看板</el-menu-item>
        <el-menu-item index="/owners">负责人汇总</el-menu-item>
        <el-menu-item index="/mappings">映射编辑</el-menu-item>
        <el-menu-item v-if="canStoreOps" index="/store-ops">店铺运营</el-menu-item>
        <el-menu-item v-if="isAdmin" index="/permissions">权限管理</el-menu-item>
      </el-menu>
    </div>
    <div class="header-right">
      <el-dropdown @command="handleCommand">
        <span class="user-info">
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
import { User, CaretBottom } from '@element-plus/icons-vue'
import { logout } from '../api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()

const username = ref('')
const userRole = ref('')
const canViewStoreOps = ref(false)

// 当前激活的菜单项
const activeMenu = computed(() => {
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

// 加载用户信息
const loadUserInfo = () => {
  const userStr = localStorage.getItem('user')
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
      username.value = user.username || '用户'
      userRole.value = user.role || 'user'
      canViewStoreOps.value = user.can_view_store_ops === true
    } catch (e) {
      username.value = '用户'
      userRole.value = 'user'
    }
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
  loadUserInfo()
})
</script>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
  height: 60px;
  line-height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 30px;
}

.logo {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-color-primary);
}

.header-menu {
  border-bottom: none;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 0 12px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: var(--el-bg-color-page);
}

.user-info span {
  font-size: 14px;
  color: var(--el-text-color-primary);
}
</style>

