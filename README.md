# Shoplazza 多店铺数据看板系统

## 📋 项目概述

一个专为 Shoplazza 多店铺数据聚合设计的实时可视化看板系统，将所有店铺的数据概览按小时粒度汇总成"总店铺"时间序列，并提供灵活的筛选、对比与分析功能。

**核心价值**：在 Shoplazza 后台单个店铺已有详细折线图的基础上，提供所有店铺数据聚合的总览视图，支持精细的时间维度分析与对比。

---

## ✨ 核心功能

### 1. 数据可视化

#### 1.1 核心指标
- **总销售额（GMV）**：所有店铺的销售额汇总
- **总订单数（Orders）**：所有店铺的订单数汇总
- **总访客数（UV）**：所有店铺的访客数汇总
- **平均客单价**：总销售额 ÷ 总订单数

#### 1.2 折线图展示
- **小时模式**：显示每小时数据点（默认）
- **天模式**：显示每天数据点
- **实时刷新**：筛选条件改动后，图表自动刷新

#### 1.3 店铺选择
- **总店铺**：查看所有店铺的汇总数据（默认）
- **单店铺**：查看单个店铺的详细数据
- **多店铺对比**：同时查看多个店铺的数据对比

#### 1.4 时间筛选
- **日期范围**：支持任意起止日期选择
- **快捷选择**：今天、昨天、最近7天、最近30天、最近3个月
- **日内时段**：支持筛选一天中的特定时间段（如：08:00-12:00）
- **时段快捷**：全天、上午（00:00-12:00）、下午（12:00-18:00）、晚上（18:00-24:00）

#### 1.5 对比模式
- **基础对比**：昨天 vs 前天、上周 vs 本周、上月 vs 本月
- **自由对比**：支持添加多个对比段，自定义日期和时段
- **差值阴影**：显示对比段之间的差值区域
- **图例开关**：每条折线可独立显示/隐藏

#### 1.6 交互功能
- **图表缩放**：鼠标滚轮缩放、框选缩放
- **时间轴拖动**：鼠标拖拽平移时间轴
- **CSV导出**：导出当前筛选条件下的原始数据
- **工具提示**：鼠标悬停显示详细数据

---

## 🔄 数据同步机制

### 实时同步（5分钟粒度）

**执行方式**：Windows 任务计划程序，每5分钟自动执行

**同步范围**：
- 收集最近1小时的5分钟段数据
- 自动检测到新的一天时，收集最近1小时的数据
- 从当天 00:00:00 到最近完成的5分钟段

**执行脚本**：`run_sync.bat` → `data_sync.py --realtime`

**特点**：
- 自动处理跨天情况
- 并行处理多个店铺
- 使用MySQL原子操作，避免数据竞争
- 自动禁用API失败的店铺

### 每日同步（历史数据）

**执行方式**：Windows 任务计划程序，每天凌晨执行（可选）

**同步范围**：同步昨天的完整24小时数据

**使用场景**：用于补充或校验历史数据

---

## 📊 数据来源与处理

### API接口

#### 1. 数据分析接口（Data Analysis API）
- **端点**：`https://{shop_domain}/openapi/2022-01/data/analysis`
- **用途**：获取访客数（`data.uv`）
- **参数**：
  - `begin_time` / `end_time`：Unix时间戳（秒）
  - `tz`：8.0（北京时间）
  - `filter_crawler_type`：`"official_crawler"`（过滤爬虫流量）
  - `dt_by`：`"dt_by_hour"` 或 `"dt_by_day"`

#### 2. 订单列表接口（Order List API）
- **端点**：`https://{shop_domain}/openapi/2022-01/orders`
- **用途**：获取订单数和销售额（主要数据源）
- **参数**：
  - `placed_at_min` / `placed_at_max`：ISO 8601格式（按支付时间查询）
  - `page` / `limit`：分页参数（limit最大200）

### 数据过滤规则

- **礼品卡订单**：自动过滤，不统计
- **COD订单**：自动过滤，不统计
- **价格解析失败**：记录日志，不统计（订单数和销售额）

### 数据聚合规则

- **时间粒度**：按小时聚合
- **店铺汇总**：所有店铺同一小时的数据累加
- **访客数**：按天去重（同一IP在同一天只算一次）
- **时区**：统一使用北京时间（UTC+8）

---

## 🗄️ 数据库结构

### 1. 店铺配置表（shoplazza_stores）

```sql
CREATE TABLE shoplazza_stores (
    id INT PRIMARY KEY AUTO_INCREMENT,
    shop_domain VARCHAR(255) NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### 2. 数据聚合表（shoplazza_overview_hourly）

```sql
CREATE TABLE shoplazza_overview_hourly (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    time_hour DATETIME NOT NULL COMMENT '小时时间点（北京时间）',
    total_gmv DECIMAL(15, 2) NOT NULL COMMENT '总销售额',
    total_orders INT NOT NULL COMMENT '总订单数',
    total_visitors INT NOT NULL COMMENT '总访客数',
    avg_order_value DECIMAL(10, 2) NOT NULL COMMENT '平均客单价',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_time_hour (time_hour)
);
```

### 3. 单店铺明细表（shoplazza_store_hourly）

```sql
CREATE TABLE shoplazza_store_hourly (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    shop_domain VARCHAR(255) NOT NULL,
    time_hour DATETIME NOT NULL,
    total_gmv DECIMAL(15, 2) NOT NULL,
    total_orders INT NOT NULL,
    total_visitors INT NOT NULL,
    avg_order_value DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_shop_time (shop_domain, time_hour)
);
```

### 4. 同步状态表（sync_status）

```sql
CREATE TABLE sync_status (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sync_type VARCHAR(50) NOT NULL UNIQUE,
    last_sync_end_time DATETIME,
    sync_date DATE,
    total_visitors INT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

---

## 🚀 安装与配置

### 环境要求

- **操作系统**：Windows / Linux / macOS
- **Python版本**：3.11+
- **数据库**：MySQL 8.0+
- **Python包**：见 `requirements.txt`
- **Node.js**：18+（前端开发需要）

---

## 🎯 Demo 模式（演示模式）

### 快速体验（无需真实数据）

如果您只是想快速体验系统功能，可以使用 Demo 模式：

#### 方式1：使用模拟数据库（推荐）

1. **导入数据库结构**
   ```bash
   mysql -u root -p shoplazza_dashboard < db/schema.sql
   ```

2. **导入演示数据**
   ```bash
   mysql -u root -p shoplazza_dashboard < db/seeds.sql
   ```

3. **启动系统**
   ```bash
   # 后端
   cd backend
   python -m uvicorn app.main:app --reload
   
   # 前端（新终端）
   cd frontend
   npm install
   npm run dev
   ```

**演示数据说明：**
- ✅ 包含 90 天连续数据（包含今天在内的过去 90 天）
- ✅ 使用随机游动算法生成，数据有涨有跌，折线图平滑美观
- ✅ 包含 10 个虚构店铺、5 个负责人
- ✅ 所有数据已脱敏，无任何真实信息

#### 方式2：前端直接读取 JSON（无需后端）

如果后端未启动，前端可以直接读取 `frontend/public/demo_data.json` 展示图表效果。

**适用场景：**
- GitHub Pages 静态部署
- 快速演示系统界面
- 前端开发调试

---

### 生产环境配置

#### 1. 安装依赖

**后端依赖：**
```bash
pip install -r requirements.txt
pip install python-dotenv  # 环境变量支持
```

**前端依赖：**
```bash
cd frontend
npm install
```

#### 2. 配置环境变量

1. **复制环境变量模板**
   ```bash
   cp .env.example .env
   ```

2. **编辑 `.env` 文件，填入真实配置**
   ```ini
   # 数据库配置
   DB_PASSWORD=your_database_password
   
   # TikTok Token
   TIKTOK_ACCESS_TOKEN_1=your_tiktok_token_1
   TIKTOK_ACCESS_TOKEN_2=your_tiktok_token_2
   
   # Facebook Token
   FB_LONG_LIVED_TOKEN=your_facebook_token
   ```

3. **配置数据库**
   - 创建数据库：`CREATE DATABASE shoplazza_dashboard;`
   - 导入表结构：`mysql -u root -p shoplazza_dashboard < db/schema.sql`
   - 或使用 `init_db.py` 初始化

#### 3. 配置店铺信息

- 在 `shoplazza_stores` 表中添加店铺域名和Access Token
- 使用 `add_stores.py` 或直接操作数据库

#### 4. 配置Windows任务计划（可选）

- 创建定时任务，每5分钟执行 `run_sync.bat`
- 设置任务在后台运行

### 启动看板

**后端（FastAPI）：**
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

**前端（Vue）：**
```bash
cd frontend
npm run dev
```

访问地址：`http://localhost:5173`（前端默认端口）

**旧版 Streamlit 看板（可选）：**
```bash
# 方式1：使用批处理脚本
run_dashboard.bat

# 方式2：直接运行
streamlit run dashboard.py --server.port 8502 --server.address 0.0.0.0
```

访问地址：`http://服务器IP:8502`

---

## 🛠️ 工具脚本

### 数据同步脚本

#### 1. 实时同步（5分钟）
```bash
# Windows任务计划程序自动执行
run_sync.bat
```

#### 2. 补齐指定日期数据
```bash
# 补齐今天的数据（清空后重新同步）
python fill_date_data.py today 8

# 补齐昨天的数据
python fill_date_data.py yesterday 8

# 补齐N天前的数据（例如：3天前）
python fill_date_data.py -3 8

# 补齐指定日期（例如：2025-12-07）
python fill_date_data.py 2025-12-07 8

# 参数说明：
#   - 日期：today/yesterday/-N/YYYY-MM-DD
#   - 8：并行时间段数量（建议6-10）
```

#### 3. 补齐缺失数据
```bash
# 自动补齐所有缺失的5分钟段数据
python fill_missing_data.py
```

#### 4. 补齐今天数据
```bash
# 清空今天数据后，从00:00:00开始重新同步
python fill_today_data.py
```

### 数据验证脚本

#### 1. 验证今天数据
```bash
# 对比数据库和API的数据
python verify_today_data.py
```

#### 2. 验证昨天数据
```bash
# 对比数据库和API的数据
python verify_yesterday_data.py
```

#### 3. 检查同步状态
```bash
# 查看当前同步状态和最新数据
python check_sync_status.py
```

#### 4. 诊断订单丢失
```bash
# 诊断5分钟段查询和全天查询的差异
python diagnose_order_loss.py
```

### 店铺管理脚本

#### 1. 禁用店铺
```bash
# 禁用指定店铺（API失败时自动禁用）
python disable_store.py hedian.myshoplaza.com
```

#### 2. 添加店铺
```bash
# 添加新店铺
python add_stores.py
```

#### 3. 更新店铺Token
```bash
# 更新店铺的Access Token
python update_store_token.py
```

---

## ⚙️ 配置说明

### config.py 配置项

#### 数据库配置
```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'shoplazza_user',
    'password': '123456',
    'database': 'shoplazza_dashboard',
    'charset': 'utf8mb4'
}
```

#### API配置
```python
API_CONFIG = {
    'timeout': 30,           # 请求超时时间（秒）
    'max_retries': 2,        # 最大重试次数
    'retry_delay': 30,       # 重试间隔（秒）
    'page_limit': 200,       # 每页最大记录数
}
```

#### Streamlit配置
```python
STREAMLIT_CONFIG = {
    'port': 8502,            # 端口号
    'host': '0.0.0.0'        # 监听所有网络接口
}
```

---

## 🔧 Windows任务计划配置

### 5分钟实时同步任务

1. **打开任务计划程序**：运行 `taskschd.msc`

2. **创建基本任务**
   - 名称：`Shoplazza实时数据同步`
   - 触发器：重复任务，每5分钟执行一次
   - 操作：启动程序
   - 程序：`D:\projects\line chart\run_sync.bat`

3. **高级设置**
   - 勾选"使用最高权限运行"
   - 勾选"不管用户是否登录都要运行"
   - 勾选"如果任务失败，重新启动"
   - 设置为"运行任务"而不是"打开文件"

---

## 📈 数据准确性保证

### 数据验证机制

1. **API分页处理**：使用原子操作，完全依赖返回订单数判断分页，不依赖count字段
2. **并行写入保护**：使用MySQL原子操作，避免竞争条件导致数据丢失
3. **错误处理**：
   - API重试2次后失败，自动禁用店铺
   - 价格解析失败的订单记录日志
   - 除以0错误已修复（订单数为0时，客单价设为0）

### 数据校验命令

```bash
# 验证今天数据准确性
python verify_today_data.py

# 验证昨天数据准确性
python verify_yesterday_data.py
```

---

## 🐛 故障排查

### 常见问题

#### 1. 数据不准确
- **原因**：可能是历史数据在修复前同步的，存在数据丢失
- **解决**：重新同步数据
  ```bash
  python fill_date_data.py today 8
  python fill_date_data.py yesterday 8
  ```

#### 2. 同步失败
- **检查**：查看日志文件 `logs/app.log`
- **检查**：运行 `python check_sync_status.py`
- **检查**：确认Windows任务计划程序是否正常运行

#### 3. 店铺API失败
- **现象**：日志中显示API请求失败
- **处理**：系统会自动禁用失败的店铺
- **恢复**：修复店铺API后，手动启用店铺
  ```sql
  UPDATE shoplazza_stores SET is_active = TRUE WHERE shop_domain = 'xxx.myshoplaza.com';
  ```

#### 4. 端口被占用
- **现象**：Streamlit启动失败
- **解决**：修改 `config.py` 中的端口号，或关闭占用端口的程序

---

## 📝 数据同步逻辑

### 5分钟实时同步流程

1. **检测同步状态**
   - 读取 `sync_status` 表中的最后同步时间
   - 判断是否需要收集新一天的数据

2. **收集数据**
   - 并行处理所有启用的店铺
   - 按5分钟段收集订单和访客数据

3. **数据聚合**
   - 按小时汇总所有店铺的数据
   - 使用MySQL原子操作写入数据库

4. **更新同步状态**
   - 更新 `sync_status` 表
   - 记录最后同步时间

### 数据过滤逻辑

1. **过滤礼品卡订单**
   - 检查订单项是否全是礼品卡
   - 检查订单是否有礼品卡标识

2. **过滤COD订单**
   - 检查支付方式是否包含COD
   - 检查支付网关名称

3. **价格解析**
   - 优先使用 `total_price` 字段
   - 备用 `total_price_set.shop_money.amount`
   - 解析失败时记录日志，不统计订单

---

## 🎯 使用场景

### 场景1：查看今天的数据趋势
1. 选择日期：今天
2. 时段：全天
3. 颗粒度：小时
4. 店铺：总店铺

### 场景2：对比本周和上周的上午时段
1. 添加对比：本周 vs 上周
2. 时段：08:00-12:00
3. 颗粒度：小时
4. 指标：总销售额、总订单数

### 场景3：查看单个店铺的数据
1. 店铺选择：选择具体店铺
2. 日期：最近7天
3. 颗粒度：小时
4. 指标：查看该店铺的所有指标

---

## 📚 重要说明

### 订单统计规则

- **支付时间**：使用 `placed_at` 字段（订单支付时间）
- **时间范围**：按订单支付时间查询，与Shoplazza后台统计逻辑一致
- **订单过滤**：自动过滤礼品卡订单和COD订单
- **时区**：统一使用北京时间（UTC+8）

### 数据保留

- **保留策略**：无限制，保留所有历史数据
- **自动清理**：已禁用，不会自动删除数据

### 性能优化

- **并行处理**：多个店铺并行查询
- **分页处理**：自动处理API分页
- **原子操作**：使用MySQL原子操作，避免数据竞争

---

## 📞 技术支持

如遇问题，请检查：
1. 日志文件：`logs/app.log`
2. 同步状态：`python check_sync_status.py`
3. 数据验证：`python verify_today_data.py`

---

---

## 📸 系统截图

<!-- TODO: 预留位置，稍后添加折线图截图 -->
<!-- 
### 折线图展示
![折线图截图](screenshots/dashboard-chart.png)

### 数据汇总表
![数据汇总表截图](screenshots/data-summary.png)
-->

---

## 🔒 安全说明

### 代码安全

- ✅ 所有敏感信息（API Token、数据库密码）已从代码中移除
- ✅ 真实配置存储在 `.env` 文件中（已加入 `.gitignore`）
- ✅ GitHub 仓库仅包含脱敏的演示数据

### 环境变量

- ✅ 使用 `.env` 文件管理敏感配置
- ✅ 提供 `.env.example` 作为配置模板
- ✅ 支持 Mock 模式（无真实 Token 时返回模拟数据）

---

## 📝 数据说明

### 演示数据

- **数据范围**：包含今天在内的过去 90 天
- **数据量**：2,160 条小时级数据点
- **生成算法**：随机游动（Random Walk）
- **数据特点**：平滑波动，适合演示折线图效果

### 真实数据

- 配置 `.env` 文件后，系统自动使用真实 API
- 数据存储在 MySQL 数据库中
- 支持实时同步和历史数据回填

---

**文档版本**：v3.0（Demo 模式支持）  
**最后更新**：2026-01-04
