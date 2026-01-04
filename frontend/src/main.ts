/**
 * 【新系统】Vue前端 - 应用入口
 * 初始化Vue应用，配置路由、UI组件库等
 */
import { createApp } from 'vue'
import './style.css'
import App from './App.vue'

// 导入Vue Router
import router from './router'

// 导入Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs' // 中文语言包

// 创建Vue应用实例
const app = createApp(App)

// 使用Vue Router
app.use(router)

// 使用Element Plus（配置中文语言包）
app.use(ElementPlus, {
  locale: zhCn
})

// 挂载应用
app.mount('#app')
