<template>
  <div class="register-page">
    <div class="register-container">
      <h2>注册</h2>
      
      <el-form :model="registerForm" :rules="rules" ref="registerFormRef" label-width="0">
        <el-form-item prop="username">
          <el-input
            v-model="registerForm.username"
            placeholder="请输入用户名（至少3个字符）"
            size="large"
            prefix-icon="User"
            @keyup.enter="handleRegister"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="请输入密码（至少6个字符）"
            size="large"
            prefix-icon="Lock"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>
        
        <el-form-item prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="请确认密码"
            size="large"
            prefix-icon="Lock"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleRegister"
            style="width: 100%"
          >
            注册
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-link">
        <el-link type="primary" @click="goToLogin">已有账号？去登录</el-link>
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
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElForm } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { register, type RegisterParams } from '../api/auth'

const router = useRouter()
const registerFormRef = ref<InstanceType<typeof ElForm>>()

// 注册表单
const registerForm = ref({
  username: '',
  password: '',
  confirmPassword: ''
})

// 自定义验证规则：确认密码
const validateConfirmPassword = (rule: any, value: any, callback: any) => {
  if (value !== registerForm.value.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

// 表单验证规则
const rules = {
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

// 状态
const loading = ref(false)
const error = ref('')

// 处理注册
const handleRegister = async () => {
  if (!registerFormRef.value) return
  
  // 表单验证
  await registerFormRef.value.validate((valid) => {
    if (!valid) return
  })
  
  loading.value = true
  error.value = ''
  
  try {
    const params: RegisterParams = {
      username: registerForm.value.username,
      password: registerForm.value.password,
      confirm_password: registerForm.value.confirmPassword
    }
    
    await register(params)
    
    ElMessage.success('注册成功，请登录')
    
    // 跳转到登录页
    router.push('/login')
  } catch (err: any) {
    error.value = err.message || '注册失败，请检查输入信息'
  } finally {
    loading.value = false
  }
}

// 跳转到登录页
const goToLogin = () => {
  router.push('/login')
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.register-container {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.register-container h2 {
  text-align: center;
  margin-bottom: 30px;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.login-link {
  text-align: center;
  margin-top: 20px;
}

.error-message {
  margin-top: 20px;
}
</style>



