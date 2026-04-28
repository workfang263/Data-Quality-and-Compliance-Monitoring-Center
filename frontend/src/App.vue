<template>
  <div class="app-root">
    <!-- 导航栏（登录后显示） -->
    <AppHeader v-if="showHeader" />
    
    <!-- 路由视图：根据路由显示不同的页面 -->
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'

const route = useRoute()

// 认证页面不显示导航栏，保证登录/注册全屏沉浸体验
const showHeader = computed(() => {
  return !['/login', '/register'].includes(route.path)
})
</script>

<style>
/* 全局样式 */
.app-root {
  width: 100%;
  min-height: 100vh;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/*
 * 路由根节点：占满顶栏下方剩余高度并在此区域内滚动。
 * min-height: 0 避免 flex 子项默认 min-height:auto 撑开导致 body 与内部同时滚动（双滚动条）。
 */
.app-root > :last-child {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
</style>
