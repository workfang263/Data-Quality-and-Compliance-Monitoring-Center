# Facebook和TikTok时区逻辑分析

## 1. Facebook之前的时区逻辑

### API返回格式

**Facebook Graph API返回的数据：**
```json
{
  "date_start": "2025-12-16",  // 账户时区的日期
  "hourly_stats_aggregated_by_advertiser_time_zone": "00:00:00 - 00:59:59"  // 账户时区的小时
}
```

**关键点：**
- `date_start`：是**账户时区**的日期，不是UTC时间
- `hourly_stats_aggregated_by_advertiser_time_zone`：是**账户时区**的小时，不是UTC时间
- 字段名中的 `by_advertiser_time_zone` 已经说明了是按账户时区返回的

### 当前代码处理逻辑（fb_spend_sync.py 第296-299行）

```python
# 提取开始小时，例如 "00:00:00 - 00:59:59" -> "00:00:00"
hour_start = hour_str.split(" - ")[0] if " - " in hour_str else hour_str
# 构建 time_hour：日期 + 小时，例如 2025-12-08 00:00:00
time_hour = datetime.datetime.strptime(
    f"{r['date_start']} {hour_start}",
    "%Y-%m-%d %H:%M:%S"
)
```

**问题分析：**
- ❌ 直接将 `date_start`（账户时区的日期）和 `hour_start`（账户时区的小时）拼接
- ❌ **没有进行时区转换**
- ❌ 直接当作北京时间存储

**举例说明：**
- 如果账户时区是UTC-8，订单在UTC-8的 `2025-12-16 00:00:00` 发生
- Facebook返回：`date_start: "2025-12-16"`, `hourly_stats: "00:00:00 - 00:59:59"`
- 代码拼接：`2025-12-16 00:00:00`
- 代码存储：`2025-12-16 00:00:00`（当作北京时间）
- **实际应该是**：`2025-12-16 16:00:00`（北京时间）
- **结果**：时间错位16小时 ❌

### 之前的假设

**之前所有Facebook账户可能都是UTC+8时区：**
- 如果账户时区是UTC+8，返回的 `00:00:00` 确实是UTC+8的00:00
- 代码当作UTC+8存储，**碰巧正确**
- 所以之前没有发现问题

### 现在的问题

**"小一"的新账户时区是UTC-8：**
- 如果账户时区是UTC-8，返回的 `00:00:00` 是UTC-8的00:00
- 代码当作UTC+8存储，**时间错位16小时**
- 必须修改代码

---

## 2. TikTok现在的时区逻辑

### API返回格式

**TikTok Marketing API返回的数据：**
```json
{
  "dimensions": {
    "stat_time_hour": "2025-12-08 00:00:00"  // 时间字符串，格式：YYYY-MM-DD HH:MM:SS
  },
  "metrics": {
    "spend": "12.34"
  }
}
```

### 当前代码处理逻辑（tt_spend_sync.py 第268-270行）

```python
# 解析时间字符串，例如 "2025-12-08 00:00:00"
try:
    time_hour = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
except:
    # 如果解析失败，尝试只解析日期
    try:
        time_hour = datetime.datetime.strptime(time_str.split()[0], "%Y-%m-%d")
    except:
        print(f"[WARN] {advertiser_id} {date_str} 无法解析时间: {time_str}")
        continue
```

**问题分析：**
- ⚠️ 直接解析时间字符串，**没有时区信息**
- ⚠️ **没有进行时区转换**
- ⚠️ 直接当作北京时间存储

**关键问题：**
- TikTok API返回的 `stat_time_hour` 是什么时区？
- 是账户时区？还是UTC时间？还是其他时区？

**需要确认：**
- 查看TikTok API文档或实际返回的数据
- 确认 `stat_time_hour` 的时区

**如果TikTok返回的是账户时区的时间：**
- 和Facebook一样，需要修改代码
- 根据账户时区配置进行转换

**如果TikTok返回的是UTC时间：**
- 可以自动转换（类似Shoplazza）
- 但建议还是加上时区配置，更清晰

---

## 总结

### Facebook

**之前的逻辑：**
- ❌ 假设所有账户都是UTC+8
- ❌ 直接将账户时区的时间当作北京时间存储
- ❌ 没有时区转换

**现在的问题：**
- ❌ "小一"的新账户是UTC-8，时间会错位16小时
- ❌ 必须修改代码，根据账户时区配置进行转换

### TikTok

**当前的逻辑：**
- ⚠️ 直接解析时间字符串，没有时区信息
- ⚠️ 没有时区转换
- ⚠️ 直接当作北京时间存储

**需要确认：**
- TikTok API返回的 `stat_time_hour` 是什么时区？
- 如果是账户时区，需要修改代码
- 如果是UTC时间，可以自动转换（但建议还是加上配置）

---

## 下一步

### 只修改Facebook（按你的要求）

1. **创建时区工具函数**（只用于Facebook）
2. **修改Facebook相关代码**：
   - `fb_spend_sync.py`
   - `fb_spend_backfill.py`

### TikTok处理

**建议：**
- 先查看TikTok API返回的实际时间格式
- 确认时区后再决定是否修改

**或者：**
- 统一加上时区配置（更安全）

---

## 回答你的问题

**问：Facebook之前是怎么样的时区逻辑？**

**答：**
- 假设所有账户都是UTC+8时区
- 直接将Facebook返回的账户时区时间当作北京时间存储
- 没有时区转换逻辑
- 之前可能所有账户确实都是UTC+8，所以没有发现问题

**问：TikTok现在又是怎么样的时区？**

**答：**
- 直接解析时间字符串，没有时区信息
- 没有时区转换，直接当作北京时间存储
- 需要确认TikTok API返回的时间是什么时区
- 如果是账户时区，需要修改代码
- 如果是UTC时间，可以自动转换（但建议还是加上配置）




