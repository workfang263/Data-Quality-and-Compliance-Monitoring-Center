<template>
  <AuthSplitLayout
    title="欢迎回来"
    subtitle="请输入您的详细信息以登录账户。"
    brand-title="内部数据分析系统"
    brand-subtitle=""
  >
    <template #brand-icon>
      <div class="auth-brand-icon-box flex h-20 w-20 items-center justify-center rounded-2xl bg-white/70">
        <div class="tech-hexagon relative flex items-center justify-center">
          <svg viewBox="0 0 56 56" class="h-12 w-12">
            <polygon
              points="28,4 50,16 50,40 28,52 6,40 6,16"
              fill="none"
              stroke="#06b6d4"
              stroke-width="1.8"
              class="hex-outer"
              style="filter: drop-shadow(0 0 6px rgba(6,182,212,0.5))"
            />
            <polygon
              points="28,12 42,20 42,36 28,44 14,36 14,20"
              fill="none"
              stroke="rgba(6,182,212,0.35)"
              stroke-width="1"
              class="hex-inner"
            />
            <circle cx="28" cy="28" r="6" fill="none" stroke="#8b5cf6" stroke-width="1.8" class="hex-core" style="filter: drop-shadow(0 0 5px rgba(139,92,246,0.5))" />
            <line x1="28" y1="4" x2="28" y2="22" stroke="rgba(6,182,212,0.3)" stroke-width="0.5" />
            <line x1="50" y1="16" x2="36" y2="24" stroke="rgba(6,182,212,0.25)" stroke-width="0.5" />
            <line x1="6" y1="16" x2="20" y2="24" stroke="rgba(6,182,212,0.25)" stroke-width="0.5" />
          </svg>
        </div>
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
      <el-form-item label="用户标识" prop="username">
        <el-input
          v-model="loginForm.username"
          placeholder="输入用户名"
          :prefix-icon="User"
          @keyup.enter="handleLogin"
        />
      </el-form-item>

      <el-form-item label="访问密钥" prop="password">
        <el-input
          v-model="loginForm.password"
          type="password"
          placeholder="输入密码"
          :prefix-icon="Lock"
          show-password
          @keyup.enter="handleLogin"
        />
      </el-form-item>

      <div class="mb-4 flex items-center justify-between">
        <el-checkbox v-model="loginForm.rememberMe">
          <span class="text-xs tracking-wide">保持会话（7天）</span>
        </el-checkbox>
      </div>

      <el-button
        type="primary"
        class="auth-submit-btn"
        :loading="loading"
        @click="handleLogin"
      >
        <span v-if="!loading" class="flex items-center gap-2">
          <span class="text-lg">⟫</span> 接入系统
        </span>
        <span v-else>验证中…</span>
      </el-button>
    </el-form>

    <div v-if="error" class="mt-4">
      <el-alert :title="error" type="error" :closable="false" show-icon />
    </div>

    <div class="mt-6 text-center">
      <p class="text-xs tracking-widest text-slate-400">
        <span class="inline-block h-px w-8 bg-slate-300 align-middle mr-3" />
        尚未注册
        <span class="inline-block h-px w-8 bg-slate-300 align-middle ml-3" />
      </p>
      <p class="mt-2">
        <router-link to="/register" class="text-sm font-semibold tracking-wide text-cyan-500 transition-all hover:text-violet-500" style="text-shadow: 0 0 12px rgba(6,182,212,0.3)">
          创建新账户 →
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
import { Lock, User } from '@element-plus/icons-vue'
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

    localStorage.setItem('token', result.token)
    localStorage.setItem('user', JSON.stringify(result.user))

    ElMessage.success('登录成功')

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
