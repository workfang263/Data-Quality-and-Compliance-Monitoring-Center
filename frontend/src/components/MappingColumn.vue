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
  display_name: string | null
  editDisplayName: string
  editOwner: string
  owner: string
  is_active: boolean
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
  saveName: [row: MappingColumnStoreRow]
}>()

function resourceDisplay(row: MappingColumnRow): string {
  if (props.resourceKind === 'store') return (row as MappingColumnStoreRow).shop_domain
  return (row as MappingColumnAdRow).ad_account_id
}

function isStoreRow(row: MappingColumnRow): row is MappingColumnStoreRow {
  return props.resourceKind === 'store'
}

/** 判断店名是否已修改（兼容 display_name 为 null 的情况） */
function isNameChanged(row: MappingColumnStoreRow): boolean {
  const current = row.editDisplayName.trim()
  const original = (row.display_name ?? '').trim()
  return current !== original
}
</script>

<template>
  <el-card class="mapping-col-card rounded-xl border border-gray-100 shadow-sm" shadow="never">
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <span class="text-base font-semibold text-gray-900">{{ title }}</span>
        <el-button v-if="canEdit" type="primary" size="small" round @click="emit('add')">{{ addLabel }}</el-button>
      </div>
    </template>

    <div v-if="loading" class="py-8 text-center text-gray-500">
      <el-icon class="is-loading text-2xl"><Loading /></el-icon>
      <p class="mt-2 text-sm">加载中...</p>
    </div>
    <div v-else-if="error" class="py-4"><el-alert type="error" :closable="false">{{ error }}</el-alert></div>
    <div v-else-if="items.length === 0" class="py-6 text-center">
      <el-empty :description="emptyDescription">
        <el-button v-if="canEdit" type="primary" @click="emit('add')">{{ addLabel }}</el-button>
      </el-empty>
    </div>

    <div v-else class="space-y-4">
      <!-- 统一行：白底黑字 + 黑框分隔，信息紧凑 -->
      <div
        v-for="row in items"
        :key="row.id"
        class="map-row overflow-hidden rounded-lg border border-gray-300 bg-white shadow-sm ring-1 ring-gray-200 transition-shadow hover:shadow-md"
        :class="isStoreRow(row) ? 'border-l-4 border-l-blue-500' : 'border-l-4 border-l-orange-500'"
      >
        <template v-if="isStoreRow(row)">
          <!-- 顶部类型标签栏 -->
          <div class="bg-blue-50 px-3 py-1.5">
            <span class="inline-flex items-center rounded bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-700">
              店铺
            </span>
          </div>

          <!-- 资源标识 -->
          <div class="px-3 py-2">
            <div class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">资源标识</div>
            <p class="text-sm text-gray-900 break-all font-semibold leading-tight">{{ row.shop_domain }}</p>
          </div>

          <!-- 店名 -->
          <div class="border-t border-gray-200 px-3 py-2">
            <div class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">店名</div>
            <el-input
              v-if="canEdit"
              v-model="row.editDisplayName"
              placeholder="输入店铺具体名称（可为空）"
              size="default"
              class="store-name-inp"
              clearable
              @change="emit('rowChange', row)"
            />
            <span v-else class="text-sm text-gray-800 font-medium">{{ row.display_name || '（未设置）' }}</span>
            <!-- 店名保存按钮：与负责人保存按钮保持一致 -->
            <el-button
              v-if="canEdit && isNameChanged(row)"
              type="primary"
              size="small"
              class="mt-2 w-full"
              :loading="row.saving"
              @click="emit('saveName', row)"
            >
              保存
            </el-button>
          </div>

          <!-- 负责人 -->
          <div class="border-t border-gray-200 px-3 py-2">
            <div class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">负责人</div>
            <el-input
              v-model="row.editOwner"
              size="default"
              placeholder="请输入负责人名称"
              :disabled="!canEdit"
              class="owner-inp"
              @change="emit('rowChange', row)"
            />
            <el-button
              v-if="canEdit && row.editOwner !== row.owner"
              type="primary"
              size="small"
              class="mt-2 w-full"
              :loading="row.saving"
              @click="emit('save', row)"
            >
              保存
            </el-button>
          </div>
        </template>

        <!-- 广告账户行 -->
        <template v-else>
          <!-- 顶部类型标签栏 -->
          <div class="bg-orange-50 px-3 py-1.5">
            <span class="inline-flex items-center rounded bg-orange-100 px-2 py-0.5 text-xs font-bold text-orange-700">
              广告账户
            </span>
          </div>

          <!-- 资源标识 -->
          <div class="px-3 py-2">
            <div class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">资源标识</div>
            <p class="text-sm text-gray-900 break-all font-semibold leading-tight">{{ resourceDisplay(row) }}</p>
          </div>

          <!-- 负责人 -->
          <div class="border-t border-gray-200 px-3 py-2">
            <div class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">负责人</div>
            <el-input
              v-model="row.editOwner"
              size="default"
              placeholder="请输入负责人名称"
              :disabled="!canEdit"
              class="owner-inp"
              @change="emit('rowChange', row)"
            />
            <el-button
              v-if="canEdit && row.editOwner !== row.owner"
              type="primary"
              size="small"
              class="mt-2 w-full"
              :loading="row.saving"
              @click="emit('save', row)"
            >
              保存
            </el-button>
          </div>
        </template>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.mapping-col-card :deep(.el-card__header) { padding: 16px 20px; border-bottom: 1px solid var(--el-border-color-lighter); }
.mapping-col-card :deep(.el-card__body) { padding: 16px 20px; }

.map-row { transition: box-shadow .2s; }

/* 统一输入框样式：字号放大 + 高度一致，让行距紧凑相同 */
.owner-inp :deep(.el-input__wrapper),
.store-name-inp :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-border-color-lighter) inset;
  background: var(--el-fill-color-blank);
  font-size: 14px; /* 输入框文字 14px，比原先 small 更大 */
}
.owner-inp :deep(.el-input__wrapper:hover),
.store-name-inp :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--el-border-color) inset;
}
.owner-inp :deep(.el-input__wrapper.is-focus),
.store-name-inp :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset !important;
}
</style>