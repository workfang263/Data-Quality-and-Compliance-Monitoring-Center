<template>
  <div class="login-page">
    <div class="login-container">
      <h2>登录</h2>
      
      <el-form :model="loginForm" :rules="rules" ref="loginFormRef" label-width="0">
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="请输入用户名"
            size="large"
            prefix-icon="User"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        
        <el-form-item>
          <el-checkbox v-model="loginForm.rememberMe">记住我（7天内免登录）</el-checkbox>
        </el-form-item>
        
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            style="width: 100%"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="register-link">
        <el-link type="primary" @click="goToRegister">还没有账号？去注册</el-link>
      </div>
      
      <div v-if="error" class="error-message">
        <el-alert type="error" :closable="false" show-icon>
          {{ error }}
        </el-alert>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElForm } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { login, type LoginParams } from '../api/auth'

const router = useRouter()
const route = useRoute()
const loginFormRef = ref<InstanceType<typeof ElForm>>()

// 登录表单
const loginForm = ref({
  username: '',
  password: '',
  rememberMe: false
})

// 表单验证规则
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

// 状态
const loading = ref(false)
const error = ref('')

// 处理登录
const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  // 表单验证
  await loginFormRef.value.validate((valid) => {
    if (!valid) return
  })
  
  loading.value = true
  error.value = ''
  
  try {
    const params: LoginParams = {
      username: loginForm.value.username,
      password: loginForm.value.password,
      remember_me: loginForm.value.rememberMe
    }
    
    const result = await login(params)
    
    // 保存token和用户信息
    localStorage.setItem('token', result.token)
    localStorage.setItem('user', JSON.stringify(result.user))
    
    ElMessage.success('登录成功')
    
    // 跳转到原页面或默认页面
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (err: any) {
    error.value = err.message || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}

// 跳转到注册页面
const goToRegister = () => {
  router.push('/register')
}

// 如果已登录，自动跳转
onMounted(() => {
  const token = localStorage.getItem('token')
  if (token) {
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  }
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-container {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.login-container h2 {
  text-align: center;
  margin-bottom: 30px;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.register-link {
  text-align: center;
  margin-top: 20px;
}

.error-message {
  margin-top: 20px;
}
</style>
