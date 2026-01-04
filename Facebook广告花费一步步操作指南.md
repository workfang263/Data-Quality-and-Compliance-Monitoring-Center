## 这份文档能帮你做什么
- 手把手点击操作，拿到 Facebook 各店铺的广告花费数据（按日）。
- 不需要写代码；用官方界面或 Postman 即可。
- 拿到数据后，你能算出每个店铺和每个人的 ROAS（销售额 ÷ 花费）。

---

## 📋 快速开始：整个流程概览

1. **导出店铺列表**（步骤2.1）
   - 运行 `python export_store_list.py` 导出38个店铺域名

2. **获取Facebook权限和广告账户ID**（步骤2.2-2.4）
   - 在Business Settings中查看所有广告账户
   - 找到每个店铺对应的广告账户ID（形如 `act_1234567890`）
   - 确认你的账号有权限访问这些账户

3. **填写映射表**（步骤2.3）
   - 在导出的CSV中填写每个店铺对应的广告账户ID

4. **获取长期访问令牌**（步骤1）
   - 在Graph API Explorer中生成token
   - 换成60天长期token

5. **获取广告花费数据**（步骤4或5）
   - 用Graph API Explorer逐个查询，或
   - 用Postman批量查询

6. **计算ROAS**（步骤7）
   - 在Excel中把花费数据和销售额数据合并
   - 计算 ROAS = 销售额 ÷ 花费

---

## 操作前你要准备的东西
- 你能登录自己的 Business Manager（BM），且能管理相关广告账户。
- 已有或可创建一个 Facebook App（用于 Marketing API）。
- 你有浏览器，能访问 https://developers.facebook.com/ ，能打开 Graph API Explorer。
- 一份“店铺域名 ↔ 广告账户 ID”的清单（38 个店铺，形如 `act_1234567890`）。不会做可在步骤 2 里补。

---

## 步骤 1：获取长期访问令牌（60 天）
1. 打开浏览器访问 Graph API Explorer：  
   https://developers.facebook.com/tools/explorer  
2. 右上角选择你的 App（没有就先在“我的应用”里创建一个）。
3. 在“用户或页面”下方，点击“获取用户访问令牌”，勾选权限：`ads_read`, `read_insights`, `business_management`。确认后会弹窗授权，点确认。现在拿到的是“短期”令牌。
4. 在结果框里复制当前的“访问令牌”（短期）。  
5. 用短期令牌换取长期令牌：在浏览器地址栏粘贴以下链接（替换 `YOUR_APP_ID`、`YOUR_APP_SECRET`、`SHORT_TOKEN`，一行放一起）：  
   ```
   https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_TOKEN
   ```  
   回车后页面会返回 JSON，包含 `access_token`（就是 60 天长期令牌）。复制保存。
6. 进入 BM 的“系统用户”页面，确保有一个 System User，并为它分配需要的广告账户权限（至少读权限）。把上面的长期令牌当作 System User 的令牌使用即可。

> 小贴士：令牌过期后重复第 3-5 步即可。

---

## 步骤 2：导出店铺列表并准备映射表

### 2.1 从数据库导出店铺域名列表

1. **运行导出脚本**：
   ```bash
   python export_store_list.py
   ```
   这会生成一个文件：`店铺列表_待填写广告账户ID.csv`

2. **打开生成的CSV文件**，你会看到类似这样的内容：
   ```
   店铺域名,广告账户ID,负责人
   shop1.myshoplaza.com,,
   shop2.myshoplaza.com,,
   ...
   ```
   "广告账户ID"和"负责人"列是空的，需要你后续填写。

---

### 2.2 获取广告账户列表和ID

> 💡 **如果你已经有App（如 ThinkPro MarketAPI Test）且该App关联了所有广告账户，可以直接用脚本自动获取列表，见下面的"方法C"**

#### 方法A：通过Business Settings查看所有广告账户（推荐）

1. **打开Business Settings**：
   - 访问：https://business.facebook.com/settings
   - 或者：登录Facebook → 点击右上角头像 → 选择"商务管理平台"

2. **进入"广告账户"页面**：
   - 左侧菜单找到"账户" → 点击"广告账户"
   - 右侧会列出所有广告账户

3. **查看广告账户ID**：
   - 每个广告账户旁边会显示ID（形如 `1234567890`）
   - 或者点击账户名称进入详情页，在页面顶部能看到完整ID
   - **记住**：API中使用的格式是 `act_1234567890`（前面加 `act_` 前缀）

4. **确认你的权限**：
   - 在广告账户列表中，找到"人员"列，确认你的账号或你所在的System User有权限
   - 如果没有权限，需要让BM管理员给你分配：
     - 点击广告账户名称进入详情
     - 点击"人员"标签
     - 点击"添加人员"或"编辑权限"
     - 选择你的账号或System User，分配"查看"或"管理"权限

#### 方法B：通过Ads Manager查看（单个账户）

1. **打开Ads Manager**：
   - 访问：https://business.facebook.com/adsmanager/
   - 或者：在Business Settings中点击"广告管理工具"

2. **查看当前账户ID**：
   - 在页面左上角，点击账户下拉菜单
   - 会显示当前账户名称和ID（形如 `1895080421118332`）
   - 或者在浏览器地址栏的URL中能找到：`act=1895080421118332`

3. **切换账户查看其他账户ID**：
   - 点击账户下拉菜单，选择其他账户
   - 重复步骤2查看每个账户的ID

#### 方法C：通过脚本自动获取（如果你的App已关联所有账户）⭐推荐

如果你已经有App（如 ThinkPro MarketAPI Test）且该App已经关联了所有广告账户，可以用脚本自动获取：

1. **获取长期访问令牌**（如果还没有）：
   - 按照"步骤1"获取长期token
   - 确保token有 `ads_read` 和 `business_management` 权限

2. **运行脚本获取账户列表**：
   ```bash
   # 先编辑脚本，把长期token粘贴进去
   # 打开 get_fb_ad_accounts.py，找到 ACCESS_TOKEN = "YOUR_LONG_LIVED_TOKEN"
   # 替换为你的长期token，例如：ACCESS_TOKEN = "EAAKLdZC7Ap4IBQ..."
   
   # 然后运行脚本
   python get_fb_ad_accounts.py
   ```

3. **查看结果**：
   - 脚本会生成两个文件：
     - `facebook_广告账户列表.json`：完整数据（JSON格式）
     - `facebook_广告账户列表.csv`：表格格式（方便在Excel中查看）
   - 打开CSV文件，你会看到所有账户的名称和ID

4. **匹配到店铺**：
   - 根据账户名称，手动匹配到对应的店铺域名
   - 在 `店铺列表_待填写广告账户ID.csv` 中填写对应的ID
   - 如果账户名称和店铺域名有对应关系（比如账户名包含店铺名），可以推断
   - 如果不确定，可以联系店铺负责人确认

---

### 2.3 填写映射表

1. **打开之前导出的CSV文件**：`店铺列表_待填写广告账户ID.csv`

2. **为每个店铺填写对应的广告账户ID**：
   - 根据你在Business Settings或Ads Manager中查到的ID
   - 格式：`act_1234567890`（注意前面要加 `act_`）
   - 如果某个店铺有多个广告账户，可以：
     - 选项1：在CSV中为同一店铺创建多行（每行一个账户）
     - 选项2：只填主账户，后续手动汇总多个账户的数据

3. **填写负责人（可选）**：
   - 如果知道每个店铺的负责人，填写到"负责人"列
   - 用于后续按人汇总ROAS

4. **保存文件**，例如保存为：`店铺_广告账户映射表.csv`

---

### 2.4 查看和管理自己的账户权限

#### 如何查看你当前有哪些广告账户的权限

1. **在Business Settings中查看**：
   - 访问：https://business.facebook.com/settings/ad-accounts
   - 在广告账户列表中，查看"人员"列
   - 如果看到你的名字或你所在的System User，说明有权限
   - 点击账户名称进入详情，在"人员"标签中可以看到你的具体权限级别

2. **在Ads Manager中查看**：
   - 访问：https://business.facebook.com/adsmanager/
   - 点击左上角的账户下拉菜单
   - 列表中显示的所有账户，都是你有权限访问的
   - 如果某个账户不在列表中，说明你没有权限

#### 如何请求权限（如果需要）

如果你发现某个广告账户没有权限，可以：

1. **联系BM管理员**：
   - 告诉管理员你需要访问哪些广告账户
   - 说明用途：用于收集广告花费数据，计算ROAS
   - 请求分配"查看"权限即可（不需要"管理"权限）

2. **或者自己分配（如果你是BM管理员）**：
   - 进入Business Settings → 广告账户
   - 点击需要分配的账户名称
   - 点击"人员"标签 → "添加人员"
   - 选择你的账号或System User
   - 选择权限级别："查看"（View）即可
   - 点击"分配"

#### 确认权限已正确分配

在开始取数前，确保：

1. **你的账号或System User有权限访问所有38个广告账户**：
   - 回到Business Settings → 广告账户
   - 逐个检查每个账户的"人员"列，确认你的账号在列表中
   - 如果某个账户没有权限，按上面的方法请求或分配权限

2. **权限级别至少是"查看"**：
   - "查看"权限可以读取报表数据（包括spend）
   - "管理"权限也可以（但通常只需要"查看"）

3. **测试权限**（可选）：
   - 在Graph API Explorer中，用你的长期token测试一个账户
   - 如果能成功返回数据，说明权限OK
   - 如果报错"权限不足"，需要重新分配权限

---

## 步骤 3：确认报表口径
- 时间粒度：按日（`time_increment=1`）。
- 时间范围：建议先抓“昨天”，再按需扩展 7/30 天。
- 归因窗口：默认即可（7d 点击 / 1d 浏览）。如需变更，可在参数里指定 `action_attribution_windows`。
- 时区：默认广告账户时区。若你的销售额按其他时区汇总，记得统一口径。
- 币种：随账户默认币种；如要统一汇率，后续在表格里换算即可。

---

## 步骤 4：用 Graph API Explorer 手动取数（最简单）
1. 进入 Graph API Explorer（同上）。  
2. 在“访问令牌”框贴入 **长期令牌**。  
3. 在“提交”按钮左侧的输入框，填入形如：  
   ```
   act_1234567890/insights
   ```  
   其中 `act_1234567890` 替换为你的广告账户 ID。  
4. 点击“添加字段”或直接在“参数”里添加：
   - `fields`: `spend,account_id,account_name,date_start,date_stop`
   - `time_range`: `{"since":"YYYY-MM-DD","until":"YYYY-MM-DD"}`（如昨天）
   - `level`: `account`
   - `time_increment`: `1`
5. 点击“提交”。下方会返回 JSON，示例：
   ```
   {
     "data": [
       {
         "account_id": "1234567890",
         "account_name": "My Ad Account",
         "date_start": "2024-12-07",
         "date_stop": "2024-12-07",
         "spend": "123.45"
       }
     ],
     "paging": { ... }
   }
   ```
6. 左下角“下载”可导出 JSON；或复制结果粘贴到本地记事本/Excel。
7. 对 38 个账户重复步骤 3-6，或在同一个请求里批量跑（见下一节 Postman 方式）。

---

## 步骤 5：用 Postman 批量请求（可一次跑多个账户）
1. 打开 Postman，创建一个新请求，方法选 `POST`，URL：  
   ```
   https://graph.facebook.com/v19.0/insights
   ```  
   > 说明：用这种批量方式，需要在 body 里用 `batch` 或逐个账户调用。对小白更简单的方式是逐个账户调用 `/{act_id}/insights`，这里给单账户示例。
2. 在 Headers 添加：`Content-Type: application/json`。  
3. Body 选 `raw` + `JSON`，填入：
   ```json
   {
     "fields": "spend,account_id,account_name,date_start,date_stop",
     "time_range": {"since": "YYYY-MM-DD", "until": "YYYY-MM-DD"},
     "level": "account",
     "time_increment": 1,
     "access_token": "YOUR_LONG_LIVED_TOKEN"
   }
   ```
   URL 改成对应的账户：`https://graph.facebook.com/v19.0/act_1234567890/insights`
4. 点击 Send，查看返回结果，与 Graph API Explorer 相同。
5. 导出：在 Postman 响应里复制 `spend`、`date_start` 等到 Excel。
6. 批量账户：可以复制这个请求，改账户 ID 一次次发送；或用 Postman 的 Collection Runner 做数据驱动（导入 CSV 映射表做变量），但小白可以先手动循环。

---

## 步骤 6：把花费数据整理成表
1. 在 Excel 建表头：`date_start`, `store_domain`, `ad_account_id`, `spend`, `currency`（可选）。  
2. 把每个账户返回的 `date_start`（或 `date_stop`，按日相同）、`spend` 填入对应店铺行。  
3. 若同一店铺有多个账户，把同一天的 spend 求和即可。  
4. 保存为 `fb_spend.csv`，后续可与销售额表做 VLOOKUP/PowerQuery 或导入数据库。

---

## 步骤 7：计算 ROAS（在 Excel 先跑起来）
1. 假设你有销售额表 `sales.csv`，字段 `date`, `store_domain`, `revenue`。  
2. 把 `fb_spend.csv` 另开一列，用 `VLOOKUP`/`XLOOKUP` 按 `date + store_domain` 匹配到 `spend`。  
3. 新增一列 `roas = revenue / spend`。  
4. 如果要按人汇总：在表里加 `owner_name`，用数据透视表按 `owner_name` 汇总 revenue、spend，再算 `roas = revenue/spend`。  
5. 全部店铺总 ROAS：透视表总计的 revenue ÷ spend 即可。

---

## 常见问题排查
- 报错 “权限不足”：确认令牌的权限包含 `ads_read`，且 System User 被分配了该广告账户的访问权限。
- 报错 “不支持的 get 请求” 或 4xx：检查 URL 是否是 `act_XXXX/insights`，版本是否 `v19.0`，令牌是否粘贴完整。
- 返回空数据：检查时间范围内是否有花费；检查账户是否启用；确认时区日期是否对齐（可能需要再试前一天/后一天）。
- 多币种：Facebook 报表按账户币种返回，若要统一需后续用汇率转换。

---

## 后续想要自动化怎么办
- 当你熟悉了手动流程，可以把“账户列表 + 令牌”放进一个 Python 小脚本或 Airflow/Dag 调度，每天自动拉昨天的花费并入库，再自动算 ROAS。需要时告诉我，我再给你一键可跑的脚本。


