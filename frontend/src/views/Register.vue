<template>
  <AuthSplitLayout
    title="创建账号"
    subtitle="加入我们，开启专业化店铺运营之旅。"
    brand-title=""
    brand-subtitle=""
  >
    <template #brand-icon>
      <div class="auth-brand-icon-box flex h-16 w-16 -rotate-6 items-center justify-center rounded-2xl bg-white shadow-2xl">
        <el-icon class="text-3xl text-purple-600">
          <UserFilled />
        </el-icon>
      </div>
    </template>

    <el-form
      ref="registerFormRef"
      :model="registerForm"
      :rules="rules"
      label-position="top"
      class="auth-form auth-form-stack"
      size="large"
    >
      <el-form-item label="用户名" prop="username">
        <el-input
          v-model="registerForm.username"
          placeholder="请输入用户名（至少3个字符）"
          :prefix-icon="User"
          @keyup.enter="handleRegister"
        />
      </el-form-item>

      <el-form-item label="密码" prop="password">
        <el-input
          v-model="registerForm.password"
          type="password"
          placeholder="请输入密码（至少6个字符）"
          :prefix-icon="Lock"
          show-password
          @keyup.enter="handleRegister"
        />
      </el-form-item>

      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input
          v-model="registerForm.confirmPassword"
          type="password"
          placeholder="请再次输入密码"
          :prefix-icon="Lock"
          show-password
          @keyup.enter="handleRegister"
        />
      </el-form-item>

      <el-button
        type="primary"
        class="auth-submit-btn auth-submit-btn--purple"
        :loading="loading"
        @click="handleRegister"
      >
        创建账号
      </el-button>
    </el-form>

    <div v-if="error" class="mt-4">
      <el-alert :title="error" type="error" :closable="false" show-icon />
    </div>

    <div class="mt-6 text-center">
      <p class="text-sm text-slate-500">
        已有账号？
        <router-link to="/login" class="font-semibold text-purple-600 transition-colors hover:text-purple-500">
          去登录
        </router-link>
      </p>
    </div>
  </AuthSplitLayout>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Lock, User, UserFilled } from '@element-plus/icons-vue'
import { isAxiosError } from 'axios'
import AuthSplitLayout from '../components/auth/AuthSplitLayout.vue'
import { register, type RegisterParams } from '../api/auth'

const router = useRouter()
const registerFormRef = ref<FormInstance>()

interface RegisterFormModel {
  username: string
  password: string
  confirmPassword: string
}

const registerForm = reactive<RegisterFormModel>({
  username: '',
  password: '',
  confirmPassword: ''
})

type FormValidatorCallback = (error?: Error) => void

const validateConfirmPassword = (_rule: unknown, value: string, callback: FormValidatorCallback): void => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
    return
  }
  callback()
}

const rules: FormRules<RegisterFormModel> = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, message: '用户名长度至少3个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const loading = ref(false)
const error = ref('')

/**
 * 将 API 异常统一转为用户可读文案，避免直接暴露技术细节。
 */
const getErrorMessage = (err: unknown): string => {
  if (!isAxiosError(err)) {
    return '注册失败，请检查输入信息'
  }

  const detail = err.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  const message = err.response?.data?.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }

  return err.message || '注册失败，请检查输入信息'
}

const handleRegister = async () => {
  if (!registerFormRef.value) return

  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  error.value = ''

  try {
    const params: RegisterParams = {
      username: registerForm.username,
      password: registerForm.password,
      confirm_password: registerForm.confirmPassword
    }

    await register(params)

    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (err: unknown) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-submit-btn--purple {
  --auth-primary: var(--auth-register-primary);
  --auth-primary-hover: var(--auth-register-primary-hover);
}
</style>



