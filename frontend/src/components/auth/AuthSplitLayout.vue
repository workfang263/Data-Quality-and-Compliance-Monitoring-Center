<template>
  <div class="auth-page-shell min-h-screen flex bg-white">
    <!-- 左侧品牌区：桌面端展示，移动端折叠，避免挤压表单可用空间 -->
    <section class="auth-brand-panel relative hidden overflow-hidden lg:flex lg:w-1/2 items-center justify-center p-12">
      <div class="auth-brand-overlay absolute inset-0"></div>

      <div class="relative z-10 max-w-md text-center text-slate-800">
        <div class="mb-8 flex items-center justify-center">
          <slot name="brand-icon">
            <div class="auth-brand-icon-box flex h-16 w-16 items-center justify-center rounded-2xl bg-white shadow-2xl">
              <span class="text-2xl font-semibold text-blue-600">S</span>
            </div>
          </slot>
        </div>

        <h1 v-if="brandTitle" class="mb-6 text-5xl font-bold tracking-tight">{{ brandTitle }}</h1>
        <p v-if="brandSubtitle" class="auth-brand-subtitle text-xl">{{ brandSubtitle }}</p>
      </div>

      <p class="auth-brand-version auth-version-text absolute bottom-4 left-6 text-xs text-slate-400">{{ versionText }}</p>
    </section>

    <!-- 右侧表单区：始终可见，承载具体登录/注册交互 -->
    <section class="auth-form-panel flex w-full items-center justify-center p-8 sm:p-12 lg:w-1/2 lg:p-24">
      <div class="w-full max-w-md">
        <header class="auth-form-header mb-8 text-center lg:text-left">
          <h2 class="auth-form-title text-3xl font-extrabold tracking-tight text-slate-900">{{ title }}</h2>
          <p class="auth-form-subtitle mt-2 text-sm text-slate-500">{{ subtitle }}</p>
        </header>
        <slot />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
interface AuthSplitLayoutProps {
  title: string
  subtitle: string
  brandTitle?: string
  brandSubtitle?: string
  versionText?: string
}

withDefaults(defineProps<AuthSplitLayoutProps>(), {
  brandTitle: 'Shoplazza',
  brandSubtitle: '',
  versionText: 'v2.4.0 // SYSTEM_READY'
})
</script>
