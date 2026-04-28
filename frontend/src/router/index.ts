/**
 * 【新系统】Vue前端 - 路由配置
 * 配置Vue Router，管理页面路由
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { getCurrentUser, type UserInfo } from '../api/auth'

// 路由配置
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard' // 默认重定向到看板页面
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: {
      title: '登录',
      requiresAuth: false // 登录页不需要认证
    }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: {
      title: '注册',
      requiresAuth: false // 注册页不需要认证
    }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: {
      title: '看板',
      requiresAuth: true // 需要登录
    }
  },
  {
    path: '/owners',
    name: 'Owners',
    component: () => import('../views/Owners.vue'),
    meta: {
      title: '负责人汇总',
      requiresAuth: true
    }
  },
  {
    path: '/stores',
    name: 'Stores',
    component: () => import('../views/Stores.vue'),
    meta: {
      title: '店铺列表',
      requiresAuth: true
    }
  },
  {
    path: '/mappings',
    name: 'Mappings',
    component: () => import('../views/Mappings.vue'),
    meta: {
      title: '映射编辑',
      requiresAuth: true
    }
  },
  {
    path: '/mapping-audit',
    name: 'MappingAudit',
    component: () => import('../views/MappingAuditLog.vue'),
    meta: {
      title: '映射操作记录',
      requiresAuth: true,
      requiresMappingsAudit: true
    }
  },
  {
    path: '/permissions',
    name: 'Permissions',
    component: () => import('../views/Permissions.vue'),
    meta: {
      title: '权限管理',
      requiresAuth: true,
      requiresAdmin: true // 需要管理员权限
    }
  },
  {
    path: '/store-ops',
    name: 'StoreOps',
    component: () => import('../views/StoreOps.vue'),
    meta: {
      title: '店铺运营',
      requiresAuth: true,
      requiresStoreOps: true
    }
  },
  {
    path: '/store-ops/edit',
    name: 'StoreOpsEdit',
    component: () => import('../views/StoreOpsEdit.vue'),
    meta: {
      title: '店铺运营配置中心',
      requiresAuth: true,
      requiresStoreOpsConfigEdit: true,
    }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue'),
    meta: {
      title: '页面不存在'
    }
  }
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(), // 使用HTML5历史模式
  routes
})

async function getFreshCurrentUser(): Promise<UserInfo | null> {
  try {
    // 强制以服务端最新权限为准，并同步覆盖本地缓存
    const user = await getCurrentUser()
    localStorage.setItem('user', JSON.stringify(user))
    return user
  } catch (err) {
    return null
  }
}

// 路由守卫
router.beforeEach(async (to, from, next) => {
  void from
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - Shoplazza Dashboard`
  }
  
  // 检查是否需要登录
  if (to.meta.requiresAuth) {
    const token = localStorage.getItem('token')
    if (!token) {
      // 未登录，跳转到登录页，并保存原始路径
      next({
        path: '/login',
        query: { redirect: to.fullPath }
      })
      return
    }

    // 已登录路由统一刷新一次当前用户，确保权限判断不被旧缓存影响
    const currentUser = await getFreshCurrentUser()
    if (!currentUser) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      next({
        path: '/login',
        query: { redirect: to.fullPath }
      })
      return
    }

    // 检查是否需要管理员权限
    if (to.meta.requiresAdmin) {
      if (currentUser.role !== 'admin') {
        // 不是管理员，跳转到首页
        next('/dashboard')
        return
      }
    }

    // 店铺运营配置中心：管理员或 can_edit_store_ops_config
    if (to.meta.requiresStoreOpsConfigEdit) {
      if (
        currentUser.role === 'admin' ||
        currentUser.can_edit_store_ops_config === true
      ) {
        next()
        return
      }
      next('/store-ops')
      return
    }

    // 店铺运营：管理员或 can_view_store_ops
    if (to.meta.requiresStoreOps) {
      if (currentUser.role === 'admin' || currentUser.can_view_store_ops === true) {
        next()
        return
      }
      next('/dashboard')
      return
    }

    // 映射操作记录：管理员或可编辑映射的用户
    if (to.meta.requiresMappingsAudit) {
      if (currentUser.role === 'admin' || currentUser.can_edit_mappings === true) {
        next()
        return
      }
      next('/dashboard')
      return
    }
  }
  
  // 如果已登录且访问登录页或注册页，跳转到首页
  if (to.path === '/login' || to.path === '/register') {
    const token = localStorage.getItem('token')
    if (token) {
      next('/dashboard')
      return
    }
  }
  
  next()
})

export default router

