---
name: 审计默认展开
overview: 为 `StoreOpsEdit.vue` 引入统一的前端卡片折叠状态管理，并将“最近操作审计”设置为默认展开。方案保持后端零改动、现有审计加载逻辑不变，只在前端增加可维护的交互壳层，为后续店铺/广告账户/运营区块折叠预留统一模式。
todos:
  - id: inspect-audit-card
    content: 确认 StoreOpsEdit 审计卡片的 header/body 结构与现有数据流边界
    status: completed
  - id: add-section-expanded
    content: 设计统一的 sectionExpanded 状态对象，并将 audit 默认值设为 true
    status: completed
  - id: wrap-audit-body
    content: 将审计表格改为固定 header + 可折叠 body，并保留现有筛选/刷新入口
    status: completed
  - id: verify-audit-collapse
    content: 验证默认展开、手动收起再展开、筛选与刷新操作均不受影响
    status: completed
isProject: false
---

# 最近操作审计默认展开方案

## 目标

在 [d:\projects\line chart\frontend\src\views\StoreOpsEdit.vue](d:\projects\line chart\frontend\src\views\StoreOpsEdit.vue) 中，为配置中心卡片引入统一的“可折叠 body + 固定 header”交互，并将“最近操作审计”设置为默认展开。

## 现状依据

当前 `StoreOpsEdit.vue` 中，“最近操作审计”是一个普通 `el-card`，header 里只有筛选和刷新按钮，body 直接渲染审计表格，没有任何折叠状态：

```162:198:frontend/src/views/StoreOpsEdit.vue
<el-card shadow="never" class="rounded-2xl border border-slate-200">
  <template #header>
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div class="text-base font-semibold text-slate-900">最近操作审计</div>
        <div class="mt-1 text-xs text-slate-500">仅记录子系统配置写操作。这里展示最近 20 条，便于快速核对。</div>
      </div>
      <div class="flex flex-wrap gap-2">
        <el-select ... @change="loadAudit">
        <el-button :loading="auditLoading" @click="loadAudit">刷新审计</el-button>
      </div>
    </div>
  </template>

  <el-table :data="audit.items" stripe style="width: 100%" v-loading="auditLoading">
```

同时，审计数据的读取已经集中在 `loadAudit()` 和 `refreshAll()` 中，说明折叠能力只需要改 UI 展示层，不需要改接口和数据流：

```491:515:frontend/src/views/StoreOpsEdit.vue
async function loadAudit() {
  auditLoading.value = true
  try {
    audit.value = await fetchStoreOpsConfigAudit({
      resource_type: auditFilterResourceType.value,
      limit: 20,
      offset: 0,
    })
  } finally {
    auditLoading.value = false
  }
}

async function refreshAll() {
  await Promise.all([
    loadShops(),
    loadAvailableShops(),
    loadAdAccounts(),
    loadAvailableAdAccounts(),
    loadOperators(),
    loadAudit(),
  ])
}
```

## 方案设计

### 1. 引入统一的区块展开状态对象

在 `StoreOpsEdit.vue` 的 `<script setup>` 中新增集中式状态，例如：

- `shops`
- `adAccounts`
- `operators`
- `audit`

其中：

- `audit: true`，表示“最近操作审计”默认展开
- 其余区块可以暂时保持 `true`，或按后续需求再调整默认值

这样设计的理由：

- 避免为每块卡片散落定义多个 `xxxExpanded` 布尔值
- 未来如果你要给店铺、广告账户、运营都加折叠，可以直接复用同一模式
- 后续若要接 `localStorage` 记忆用户习惯，也只需要围绕一个状态对象扩展

### 2. 保持 header 常驻，只折叠 body

对“最近操作审计”卡片采用：

- header 永远显示
- 在 header 增加“展开 / 收起”按钮或图标按钮
- 审计表格区域放在可折叠 body 中

理由：

- 这样不会影响现有的 `资源筛选` 和 `刷新审计` 操作入口
- 比整卡塞进 `el-collapse` 更符合当前页面的卡片式配置中心风格
- 与你后续想做的“店铺/广告账户/运营也能折叠，但主操作不受影响”完全同一套交互模型

### 3. 优先使用 `v-show`，不建议先用 `v-if`

审计 body 的显隐建议优先用 `v-show`：

- `v-show` 只是控制 `display`，不会销毁表格实例
- 展开/收起不会重建 DOM，减少抖动
- 不影响已经加载好的 `audit.items`

不建议首版就用 `v-if` 的原因：

- 你当前 `refreshAll()` 已经会主动加载审计数据
- 折叠只是视觉收起，不是“懒加载到展开时再请求”
- 如果用 `v-if`，每次展开都要考虑子树重建、表格状态重置等额外问题

### 4. 审计默认展开的具体落点

默认展开的行为应体现在两个层面：

- 状态默认值：`audit = true`
- 页面初次进入时，用户无需点击即可看到审计表格

这样既满足“默认展开”的业务要求，也保留后续用户手动收起的能力。

## 实施步骤

1. 在 [d:\projects\line chart\frontend\src\views\StoreOpsEdit.vue](d:\projects\line chart\frontend\src\views\StoreOpsEdit.vue) 新增统一的 `sectionExpanded` 状态对象。
2. 在“最近操作审计”卡片 header 右侧操作区增加一个折叠开关（文本按钮或图标按钮）。
3. 将审计表格包裹到可折叠 body 中，并使用 `v-show="sectionExpanded.audit"` 控制显示。
4. 保持 `loadAudit()`、`refreshAll()`、筛选器、刷新按钮逻辑不变，避免影响数据流。
5. 自测以下场景：

   - 首次进入页面，审计默认展开
   - 点击收起后，header 仍保留筛选与刷新
   - 再次展开，审计列表仍正常显示
   - 切换资源筛选、点击刷新按钮行为不变

## 验收标准

- “最近操作审计”首次进入页面时默认可见
- 用户可以手动收起/展开该卡片 body
- 折叠不影响 `loadAudit()` 的数据展示结果
- 折叠不影响 header 中现有的筛选和刷新操作
- 不修改后端 API、不改动数据库、不影响其它三张配置卡片的现有功能

## 后续可扩展性

这次如果按统一状态对象实现，下一步给“店铺白名单”“广告账户白名单”“运营人员配置”加折叠时，只需要复制同一模式：

- header 常驻
- 主操作按钮常驻
- body 用 `v-show` 控制
- 默认展开/收起由 `sectionExpanded` 默认值统一管理

这样能避免后续出现三套风格不同、维护成本高的折叠实现。