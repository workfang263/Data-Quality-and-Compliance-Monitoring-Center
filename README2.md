# README2

## 0. 目标
- 按“负责人”汇总展示：销售额、订单数、访客数、客单价、广告花费、ROAS。
- 数据按天聚合；店铺与广告花费每 5 分钟更新，聚合实时触发。
- 点击负责人行，弹出该负责人（默认当天，最多 7 天）的小时级折线图，指标可选。
- 保留“总店铺”入口，去掉店铺多选；以负责人为核心查看。
- 映射（店铺/广告账户 → 负责人）支持单条编辑；无需批量、撤销、异常验证。
- 广告花费回填近 3 个月，批量 API，多线程+重试。

---

## 1. 数据表设计

### 1.1 合并前表（验证用，后台查看）
- `shoplazza_store_hourly`（已有，新增字段 `owner VARCHAR(255)`）  
  字段保持：`time_hour, shop_domain, total_gmv, total_orders, total_visitors, avg_order_value, owner`；仅存当天小时级数据。

- `fb_ad_account_spend_hourly`（新建）
  ```sql
  CREATE TABLE fb_ad_account_spend_hourly (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    time_hour DATETIME NOT NULL,
    ad_account_id VARCHAR(64) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    spend DECIMAL(18,4) NOT NULL,
    currency VARCHAR(16) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_account_time (ad_account_id, time_hour)
  );
  ```
  小时级，当天数据；回填 3 个月历史（一次性任务）。

### 1.2 合并后表（前端展示）
- `owner_daily_summary`
  ```sql
  CREATE TABLE owner_daily_summary (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    date DATE NOT NULL,
    owner VARCHAR(255) NOT NULL,
    total_gmv DECIMAL(18,4) NOT NULL DEFAULT 0,
    total_orders INT NOT NULL DEFAULT 0,
    total_visitors INT NOT NULL DEFAULT 0,
    avg_order_value DECIMAL(18,4) NOT NULL DEFAULT 0,
    total_spend DECIMAL(18,4) NOT NULL DEFAULT 0,
    roas DECIMAL(18,4) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_owner_date (owner, date)
  );
  ```
  - `avg_order_value = CASE WHEN total_orders>0 THEN total_gmv/total_orders ELSE 0 END`
  - `roas = CASE WHEN total_spend>0 THEN total_gmv/total_spend ELSE NULL END`（前端显示 “N/A”）。

### 1.3 映射表（可编辑）
- `store_owner_mapping`
  ```sql
  CREATE TABLE store_owner_mapping (
    id INT PRIMARY KEY AUTO_INCREMENT,
    shop_domain VARCHAR(255) NOT NULL UNIQUE,
    owner VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  );
  ```
- `ad_account_owner_mapping`
  ```sql
  CREATE TABLE ad_account_owner_mapping (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ad_account_id VARCHAR(64) NOT NULL UNIQUE,
    owner VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  );
  ```

---

## 2. 映射准备
- 导入店铺 → 负责人：`店铺列表_待填写广告账户ID.csv`。
- 导入广告账户ID → 负责人：36 个账户补全负责人。
- 后续修改：前端单条编辑上述映射表。

---

## 3. 数据采集与回填

### 3.1 店铺数据（已有）
- 5 分钟更新，当天数据。
- 写入 `shoplazza_store_hourly` 时，通过 `store_owner_mapping` 填充 `owner`。

### 3.2 广告花费（新增）
- **日常同步脚本**：`fb_spend_sync.py`
  - 每 5 分钟获取 36 个账户的当天小时花费，写入 `fb_ad_account_spend_hourly`。
  - 通过 `ad_account_owner_mapping` 填充 `owner`。
  - 带重试：参考现有店铺脚本的重试策略。
  - **覆盖模式**：同步前先清理指定日期范围内的旧数据，确保数据完全覆盖，避免残留错误数据。
  - 使用方式：
    ```bash
    # 默认同步今天
    python fb_spend_sync.py
    # 同步指定日期
    python fb_spend_sync.py --date 2025-12-10
    # 同步日期范围
    python fb_spend_sync.py --start 2025-12-08 --end 2025-12-10
    ```

### 3.3 历史回填（一次性）
- **回填脚本**：`fb_spend_backfill.py`
  - 批量 API 回填近 3 个月花费数据。
  - 支持分批/多线程 + 重试（参考现有多线程采集风格）。
  - 写入 `fb_ad_account_spend_hourly`。
  - **覆盖模式**：回填前先清理指定日期范围内的旧数据，确保数据完全覆盖，避免残留错误数据。
  - 数据准确性保证：
    - 自动过滤跨天数据（只保留请求日期当天的数据）
    - 使用去重逻辑避免重复数据累加
  - 使用方式：
    ```bash
    # 回填最近30天
    python fb_spend_backfill.py --days 30
    # 回填指定日期范围
    python fb_spend_backfill.py --start 2025-09-10 --end 2025-12-08
    ```

---

## 4. 聚合任务
- 触发：每次数据更新后立即聚合（方案 A）。
- 粒度：按天、按负责人。
- 来源：  
  - 店铺：`shoplazza_store_hourly` → owner+date 聚合 GMV/订单/访客/客单价。  
  - 花费：`fb_ad_account_spend_hourly` → owner+date 聚合 spend。  
- 写入：`owner_daily_summary`（UPSERT by owner+date）。
- 频率：随数据更新（5 分钟一次）。

---

## 5. 前端改造

### 5.1 主表：“各负责人数据汇总”
- 数据源：`owner_daily_summary`（按天，支持日期范围）。
- 列：负责人、销售额、订单数、访客数、客单价、广告花费、ROAS（spend=0 → “N/A”）。
- 日期选择：支持范围。
- 编辑映射：单条编辑 `store_owner_mapping` / `ad_account_owner_mapping`。
- 左侧店铺选择：移除，仅保留“总店铺”。

### 5.2 折线图（点击负责人行弹出）
- 数据源：小时级原始表  
  - 店铺：`shoplazza_store_hourly` 过滤 owner+日期范围  
  - 花费：`fb_ad_account_spend_hourly` 过滤 owner+日期范围  
- 指标：销售额、订单数、访客数、客单价、广告花费、ROAS（可选开关）。
- 时间范围：默认当天，最多 7 天，小时粒度。
- 行为：点击负责人行 → 弹窗/侧滑出折线图 → 用户勾选指标显示。

### 5.3 现有店铺折线图与核心指标
- 增加：广告花费、ROAS。
- 核心汇总：增加总广告花费、总 ROAS（spend=0 显示 “N/A”）。
- 保持其他现有功能不变。

---

## 6. ROAS 展示规则
- DB：`total_spend=0` → `roas=NULL`  
- 前端：`NULL` 显示 “N/A”。

---

## 7. 实施顺序（建议）
1) 建表：`fb_ad_account_spend_hourly`、`owner_daily_summary`、两张映射表。  
2) 导入映射：店铺→负责人，广告账户→负责人。  
3) 花费采集脚本：5 分钟更新，当天数据；带重试；采用覆盖模式。  
4) 回填脚本：3 个月历史（批量 API，多线程+重试）；采用覆盖模式。  
5) 聚合任务：实时触发（每次数据更新后），写入 `owner_daily_summary`。  
6) 前端：负责人汇总表；点击弹出折线图（≤7天，指标可选）；店铺折线图/核心指标增加花费和 ROAS；移除店铺多选，仅保留“总店铺”。  
7) 验证：对比合并前表与合并后表汇总，确认一致；ROAS=0 显示 “N/A”；使用 `verify_fb_spend_data.py` 验证广告花费数据准确性。

---

## 8. 数据准确性保证

### 8.1 覆盖模式
- **日常同步**（`fb_spend_sync.py`）和**历史回填**（`fb_spend_backfill.py`）均采用覆盖模式：
  - 先删除指定日期范围内的旧数据
  - 再重新收集并写入新数据
  - 确保数据完全覆盖，避免残留错误数据

### 8.2 数据过滤
- **跨天数据过滤**：自动过滤掉不属于请求日期的跨天数据（只保留当天的数据）
- **去重逻辑**：使用字典去重，避免同一小时的数据重复累加

### 8.3 数据验证
- 使用 `verify_fb_spend_data.py` 验证数据准确性：
  ```bash
  python verify_fb_spend_data.py --date 2025-12-10
  ```
- 对比数据库中的小时数据总和与 Facebook API 返回的日汇总数据，确保一致

---

说明：本 README2 为项目说明与操作指引文档。所有脚本和数据库表已实现并测试通过。


