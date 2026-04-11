<template>
  <!--
    页面外壳：全站统一 max-w-[1600px]、浅灰底 slate-50、左右留白。
    所在路由根节点与会话的滚动关系见 App.vue（flex + min-h-0）。
  -->
  <div class="min-h-full bg-slate-50 font-sans text-slate-900 antialiased">
    <div class="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6">
      <slot />
    </div>
  </div>
</template>
