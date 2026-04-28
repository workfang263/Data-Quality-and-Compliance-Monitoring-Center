<template>
  <AuthSplitLayout
    title="欢迎回来"
    subtitle="请输入您的详细信息以登录账户。"
    brand-title="内部数据分析系统"
    brand-subtitle=""
  >
    <template #brand-icon>
      <div class="auth-brand-icon-box flex h-16 w-16 -rotate-6 items-center justify-center rounded-2xl bg-white shadow-2xl">
        <el-icon class="text-3xl text-blue-600">
          <ShoppingBag />
        </el-icon>
      </div>
    </template>

    <el-form
      ref="loginFormRef"
      :model="loginForm"
      :rules="rules"
      label-position="top"
      class="auth-form auth-form-stack"
      size="large"
    >
      <el-form-item label="用户名" prop="username">
        <el-input
          v-model="loginForm.username"
          :prefix-icon="User"
          @keyup.enter="handleLogin"
        />
      </el-form-item>

      <el-form-item label="密码" prop="password">
        <el-input
          v-model="loginForm.password"
          type="password"
          :prefix-icon="Lock"
          show-password
          @keyup.enter="handleLogin"
        />
      </el-form-item>

      <div class="mb-4 flex items-center justify-between">
        <el-checkbox v-model="loginForm.rememberMe">记住我（7天内免登录）</el-checkbox>
      </div>

      <el-button
        type="primary"
        class="auth-submit-btn"
        :loading="loading"
        @click="handleLogin"
      >
        登录
      </el-button>
    </el-form>

    <div v-if="error" class="mt-4">
      <el-alert :title="error" type="error" :closable="false" show-icon />
    </div>

    <div class="mt-6 text-center">
      <p class="text-sm text-slate-500">
        还没有账号？
        <router-link to="/register" class="font-semibold text-blue-600 transition-colors hover:text-blue-500">
          去注册
        </router-link>
      </p>
    </div>
  </AuthSplitLayout>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Lock, ShoppingBag, User } from '@element-plus/icons-vue'
import { isAxiosError } from 'axios'
import AuthSplitLayout from '../components/auth/AuthSplitLayout.vue'
import { login, type LoginParams } from '../api/auth'

const router = useRouter()
const route = useRoute()
const loginFormRef = ref<FormInstance>()

interface LoginFormModel {
  username: string
  password: string
  rememberMe: boolean
}

const loginForm = reactive<LoginFormModel>({
  username: '',
  password: '',
  rememberMe: false
})

const rules: FormRules<LoginFormModel> = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

const loading = ref(false)
const error = ref('')

/**
 * 统一提取后端错误文案：
 * 1) 优先读 FastAPI detail
 * 2) 其次读 message
 * 3) 最后兜底通用错误，避免页面出现 undefined
 */
const getErrorMessage = (err: unknown): string => {
  if (!isAxiosError(err)) {
    return '登录失败，请检查用户名和密码'
  }

  const detail = err.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  const message = err.response?.data?.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }

  return err.message || '登录失败，请检查用户名和密码'
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  // 先验表单再发请求，避免无效请求打到后端
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  error.value = ''

  try {
    const params: LoginParams = {
      username: loginForm.username,
      password: loginForm.password,
      remember_me: loginForm.rememberMe
    }

    const result = await login(params)

    // 与后端契约保持一致：token 位于 data.token（拦截器已解包 data）
    localStorage.setItem('token', result.token)
    localStorage.setItem('user', JSON.stringify(result.user))

    ElMessage.success('登录成功')

    // 保留原有 redirect 体验：未登录访问受限页，登录后可回跳
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (err: unknown) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const token = localStorage.getItem('token')
  if (token) {
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  }
})
</script>
