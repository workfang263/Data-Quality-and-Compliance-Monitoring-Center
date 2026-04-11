<script setup lang="ts">
/**
 * 映射列：店铺或广告账户 → 负责人。
 * 三种数据源结构一致（资源 ID + 负责人可编辑），抽成子组件避免重复模板。
 */
import { Loading } from '@element-plus/icons-vue'

/** 店铺行：展示店铺域名 */
export type MappingColumnStoreRow = {
  id: number
  shop_domain: string
  editOwner: string
  owner: string
  saving: boolean
}

/** 广告账户行：展示账户 ID */
export type MappingColumnAdRow = {
  id: number
  ad_account_id: string
  editOwner: string
  owner: string
  saving: boolean
}

export type MappingColumnRow = MappingColumnStoreRow | MappingColumnAdRow

const props = defineProps<{
  /** 列标题，如「店铺 → 负责人映射」 */
  title: string
  /** store：标签为「店铺」；ad：标签为「账户」 */
  resourceKind: 'store' | 'ad'
  /** 头部/空状态的「新增」按钮文案 */
  addLabel: string
  canEdit: boolean
  loading: boolean
  error: string
  emptyDescription: string
  items: MappingColumnRow[]
}>()

const emit = defineEmits<{
  add: []
  /** 输入框 change（预留校验钩子） */
  rowChange: [row: MappingColumnRow]
  save: [row: MappingColumnRow]
}>()

function resourceDisplay(row: MappingColumnRow): string {
  if (props.resourceKind === 'store') {
    return (row as MappingColumnStoreRow).shop_domain
  }
  return (row as MappingColumnAdRow).ad_account_id
}
</script>

<template>
  <el-card class="mapping-column-card rounded-xl border border-gray-100 shadow-sm" shadow="never">
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <span class="text-base font-semibold text-gray-900">{{ title }}</span>
        <el-button
          v-if="canEdit"
          type="primary"
          size="small"
          round
          @click="emit('add')"
        >
          {{ addLabel }}
        </el-button>
      </div>
    </template>

    <div v-if="loading" class="py-8 text-center text-gray-500">
      <el-icon class="is-loading text-2xl"><Loading /></el-icon>
      <p class="mt-2 text-sm">加载中...</p>
    </div>

    <div v-else-if="error" class="py-4">
      <el-alert type="error" :closable="false">{{ error }}</el-alert>
    </div>

    <div v-else-if="items.length === 0" class="py-6 text-center">
      <el-empty :description="emptyDescription">
        <el-button v-if="canEdit" type="primary" @click="emit('add')">
          {{ addLabel }}
        </el-button>
      </el-empty>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="row in items"
        :key="row.id"
        class="rounded-lg border border-gray-200 bg-white p-4 transition-shadow hover:shadow-sm"
      >
        <div class="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
          资源标识
        </div>
        <div class="mb-3 break-all text-sm font-medium text-gray-900">
          {{ resourceDisplay(row) }}
        </div>
        <div class="mb-1 text-xs text-gray-500">负责人</div>
        <el-input
          v-model="row.editOwner"
          placeholder="请输入负责人名称"
          :disabled="!canEdit"
          class="mapping-owner-input"
          @change="emit('rowChange', row)"
        />
        <el-button
          v-if="canEdit && row.editOwner !== row.owner"
          type="primary"
          size="small"
          class="mt-3 w-full"
          :loading="row.saving"
          @click="emit('save', row)"
        >
          保存
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.mapping-column-card :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.mapping-column-card :deep(.el-card__body) {
  padding: 16px 20px;
}

/* 轻量输入：默认边框弱化，聚焦时清晰（保留可见 focus 环） */
.mapping-owner-input :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-border-color-lighter) inset;
  background-color: var(--el-fill-color-blank);
}

.mapping-owner-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--el-border-color) inset;
}

.mapping-owner-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset !important;
}
</style>
