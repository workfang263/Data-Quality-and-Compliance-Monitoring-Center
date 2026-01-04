# API接口规范设计

## 📋 说明

本文档定义了新系统的所有API接口规范，包括：
- 接口路径
- 请求方法
- 请求参数
- 返回数据结构
- 错误处理

**设计原则**：
1. RESTful风格
2. 统一的返回格式
3. 清晰的错误码
4. 完整的参数验证

---

## 🔐 认证相关

### POST /api/auth/login
**功能**：用户登录

**请求体**：
```json
{
  "username": "string",
  "password": "string",
  "remember_me": false
}
```

**返回**：
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "jwt_token_string",
    "username": "string",
    "expires_at": "2025-12-18T16:00:00"
  }
}
```

**错误码**：
- 401: 用户名或密码错误
- 400: 参数错误

---

## 📊 看板数据

### GET /api/dashboard/data
**功能**：获取看板数据（折线图数据）

**查询参数**：
- `shop_domain` (string, optional): 店铺域名，不传或传"ALL_STORES"表示总店铺
- `start_date` (string, required): 开始日期，格式：YYYY-MM-DD
- `end_date` (string, required): 结束日期，格式：YYYY-MM-DD
- `granularity` (string, optional): 粒度，可选值：`hour`（小时）、`day`（天），默认：`hour`
- `start_hour` (integer, optional): 开始小时（0-23），用于日内时段筛选
- `end_hour` (integer, optional): 结束小时（0-23），用于日内时段筛选

**示例请求**：
```
GET /api/dashboard/data?shop_domain=ALL_STORES&start_date=2025-12-01&end_date=2025-12-18&granularity=hour&start_hour=8&end_hour=18
```

**返回**：
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "time_hour": "2025-12-01T00:00:00",
      "total_gmv": 1234.56,
      "total_orders": 10,
      "total_visitors": 100,
      "total_spend": 50.0,
      "avg_order_value": 123.456
    },
    {
      "time_hour": "2025-12-01T01:00:00",
      "total_gmv": 2345.67,
      "total_orders": 20,
      "total_visitors": 150,
      "total_spend": 60.0,
      "avg_order_value": 117.2835
    }
  ]
}
```

**字段说明**：
- `time_hour`: 时间点（ISO 8601格式）
- `total_gmv`: 总销售额（美元）
- `total_orders`: 总订单数
- `total_visitors`: 总访客数
- `total_spend`: 总广告花费（Facebook + TikTok）
- `avg_order_value`: 平均客单价（total_gmv / total_orders）

**错误码**：
- 400: 参数错误（日期格式错误、参数缺失等）
- 500: 服务器错误

---

### GET /api/dashboard/date-range
**功能**：获取数据的日期范围（最早和最晚的日期）

**查询参数**：
- `shop_domain` (string, optional): 店铺域名，不传表示总店铺

**返回**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "earliest_date": "2025-01-01",
    "latest_date": "2025-12-18"
  }
}
```

---

### GET /api/dashboard/stores
**功能**：获取店铺列表（用于下拉选择）

**返回**：
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "shop_domain": "ALL_STORES",
      "display_name": "总店铺",
      "is_total": true
    },
    {
      "shop_domain": "hipkastl.myshoplaza.com",
      "display_name": "hipkastl",
      "is_total": false
    }
  ]
}
```

---

## 👤 负责人汇总

### GET /api/owners/summary
**功能**：获取负责人汇总数据（表格数据）

**查询参数**：
- `start_date` (string, required): 开始日期，格式：YYYY-MM-DD
- `end_date` (string, required): 结束日期，格式：YYYY-MM-DD
- `sort_by` (string, optional): 排序字段，可选值：`owner`、`gmv`、`orders`、`visitors`、`aov`、`spend`、`roas`，默认：`owner`
- `sort_order` (string, optional): 排序方向，可选值：`asc`、`desc`，默认：`asc`

**示例请求**：
```
GET /api/owners/summary?start_date=2025-12-01&end_date=2025-12-18&sort_by=gmv&sort_order=desc
```

**返回**：
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "owner": "张三",
      "total_gmv": 12345.67,
      "total_orders": 100,
      "total_visitors": 1000,
      "avg_order_value": 123.4567,
      "total_spend": 500.0,
      "tt_total_spend": 300.0,
      "total_spend_all": 800.0,
      "roas": 15.432,
      "conversion_rate": 10.0
    }
  ]
}
```

**字段说明**：
- `owner`: 负责人名称
- `total_gmv`: 总销售额
- `total_orders`: 总订单数
- `total_visitors`: 总访客数
- `avg_order_value`: 平均客单价
- `total_spend`: Facebook广告花费
- `tt_total_spend`: TikTok广告花费
- `total_spend_all`: 总广告花费（Facebook + TikTok）
- `roas`: 投资回报率（total_gmv / total_spend_all）
- `conversion_rate`: 转化率（total_orders / total_visitors * 100）

---

### GET /api/owners/{owner}/hourly
**功能**：获取负责人的小时趋势数据（用于弹窗图表）

**路径参数**：
- `owner` (string, required): 负责人名称

**查询参数**：
- `start_date` (string, required): 开始日期，格式：YYYY-MM-DD
- `end_date` (string, required): 结束日期，格式：YYYY-MM-DD

**示例请求**：
```
GET /api/owners/张三/hourly?start_date=2025-12-01&end_date=2025-12-18
```

**返回**：
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "time_hour": "2025-12-01T00:00:00",
      "total_gmv": 123.45,
      "total_orders": 1,
      "total_visitors": 10,
      "total_spend": 5.0,
      "tt_total_spend": 3.0,
      "total_spend_all": 8.0,
      "avg_order_value": 123.45,
      "roas": 15.43125,
      "conversion_rate": 10.0
    }
  ]
}
```

---

## 🏪 店铺列表

### GET /api/stores/summary
**功能**：获取所有店铺的汇总数据（表格数据）

**查询参数**：
- `start_date` (string, required): 开始日期，格式：YYYY-MM-DD
- `end_date` (string, required): 结束日期，格式：YYYY-MM-DD
- `sort_by` (string, optional): 排序字段，可选值：`store_name`、`total_gmv`、`total_orders`、`total_visitors`、`avg_order_value`，默认：`store_name`
- `sort_order` (string, optional): 排序方向，可选值：`asc`、`desc`，默认：`asc`

**示例请求**：
```
GET /api/stores/summary?start_date=2025-12-01&end_date=2025-12-18&sort_by=total_gmv&sort_order=desc
```

**返回**：
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "store_id": 1,
      "shop_domain": "hipkastl.myshoplaza.com",
      "store_name": "hipkastl",
      "total_gmv": 12345.67,
      "total_orders": 100,
      "total_visitors": 1000,
      "avg_order_value": 123.4567
    }
  ]
}
```

---

## 📝 统一返回格式

### 成功响应
```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

### 错误响应
```json
{
  "code": 400,
  "message": "错误描述",
  "data": null,
  "error": {
    "type": "ValidationError",
    "detail": "详细错误信息"
  }
}
```

### HTTP状态码
- `200`: 成功
- `400`: 请求参数错误
- `401`: 未授权（需要登录）
- `404`: 资源不存在
- `500`: 服务器内部错误

---

## 🔄 数据对比功能

**说明**：数据对比功能在前端实现，通过多次调用 `/api/dashboard/data` 接口获取不同时间段的数据，然后在前端进行对比展示。

**实现方式**：
1. 前端调用多次API获取不同时间段的数据
2. 在前端合并数据，生成对比图表
3. 使用不同的颜色或线型区分不同时间段

---

## 📤 CSV导出功能

**说明**：CSV导出功能在前端实现，将API返回的JSON数据转换为CSV格式下载。

**实现方式**：
1. 前端调用API获取数据
2. 使用JavaScript库（如`papaparse`）将JSON转换为CSV
3. 触发浏览器下载

---

## 🔍 映射管理（可选，后续实现）

### GET /api/mappings/stores
**功能**：获取店铺-负责人映射列表

### PUT /api/mappings/stores/{shop_domain}
**功能**：更新店铺-负责人映射

### GET /api/mappings/ad-accounts
**功能**：获取广告账户-负责人映射列表

### PUT /api/mappings/ad-accounts/{ad_account_id}
**功能**：更新广告账户-负责人映射

---

## 📋 接口清单总结

| 接口路径 | 方法 | 功能 | 优先级 |
|---------|------|------|--------|
| `/api/auth/login` | POST | 登录 | 高 |
| `/api/dashboard/data` | GET | 看板数据 | 高 |
| `/api/dashboard/date-range` | GET | 数据日期范围 | 中 |
| `/api/dashboard/stores` | GET | 店铺列表 | 高 |
| `/api/owners/summary` | GET | 负责人汇总 | 高 |
| `/api/owners/{owner}/hourly` | GET | 负责人小时数据 | 高 |
| `/api/stores/summary` | GET | 店铺汇总 | 高 |

---

## ✅ 设计验证

### 接口设计检查清单
- [x] 所有接口路径清晰明确
- [x] 请求参数完整且类型明确
- [x] 返回数据结构清晰
- [x] 错误处理规范统一
- [x] 符合RESTful风格
- [x] 支持前端所有功能需求

---

**最后更新**：2025-12-18




