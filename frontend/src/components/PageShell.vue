<template>
  <!--
    页面外壳：统一整页背景色与水平留白。
    使用 Element 的页面背景变量，避免与 Element Plus 主题不一致。
  -->
  <div class="min-h-full bg-[var(--el-bg-color-page)] text-[var(--el-text-color-primary)]">
    <div class="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6">
      <slot />
    </div>
  </div>
</template>
