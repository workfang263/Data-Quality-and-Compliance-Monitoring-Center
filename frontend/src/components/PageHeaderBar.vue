<script setup lang="ts">
/**
 * 页头：左侧标题 + 可选副标题，右侧 #actions 插槽放按钮（刷新、导出等）。
 */
defineProps<{
  title: string
  subtitle?: string
}>()
</script>

<template>
  <header
    class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"
  >
    <div class="min-w-0">
      <h1 class="text-2xl font-semibold tracking-tight text-slate-900">
        {{ title }}
      </h1>
      <p v-if="subtitle" class="mt-1 max-w-3xl text-sm leading-relaxed text-slate-500">
        {{ subtitle }}
      </p>
    </div>
    <div class="flex flex-shrink-0 flex-wrap items-center gap-2">
      <slot name="actions" />
    </div>
  </header>
</template>
