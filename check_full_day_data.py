"""
检查完整一天的数据
"""
import sys
import io
from datetime import datetime
from database import Database

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

db = Database()

# 查询今天完整一天的数据（00:00-23:59）
today_start = datetime(2025, 12, 31, 0, 0, 0)
today_end = datetime(2025, 12, 31, 23, 59, 59)

print("=" * 80)
print("查询今天完整一天的数据（00:00-23:59）")
print("=" * 80)
print(f"查询时间范围: {today_start} 至 {today_end}")
print()

data = db.get_hourly_data(today_start, today_end, None, None)

print(f"查询到 {len(data)} 条小时数据:")
print(f"{'时间':<20} {'订单数':<10} {'销售额':<15}")
print("-" * 50)

total_orders = 0
total_gmv = 0.0

for row in data:
    time_hour = row['time_hour']
    orders = int(row['total_orders'])
    gmv = float(row['total_gmv'])
    total_orders += orders
    total_gmv += gmv
    print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {orders:<10} ${gmv:<14.2f}")

print("-" * 50)
print(f"{'总计':<20} {total_orders:<10} ${total_gmv:<14.2f}")
print()

# 对比前端数据
frontend_orders = 232
frontend_gmv = 14084.66

print("=" * 80)
print("数据对比")
print("=" * 80)
print(f"数据库完整一天的数据: 订单数={total_orders}, 销售额=${total_gmv:.2f}")
print(f"前端显示的数据: 订单数={frontend_orders}, 销售额=${frontend_gmv:.2f}")
print()

if total_orders == frontend_orders and abs(total_gmv - frontend_gmv) < 0.01:
    print("✅ 数据库数据 = 前端显示的数据（完全一致）")
else:
    print(f"❌ 数据库数据 ≠ 前端显示的数据")
    print(f"   订单数差异: {total_orders - frontend_orders}")
    print(f"   销售额差异: ${total_gmv - frontend_gmv:.2f}")
    print()
    print("可能原因:")
    print("1. 前端查询的时间范围可能不同（可能包含了其他日期）")
    print("2. 前端查询的数据源可能不同（可能查询的是聚合后的数据）")
    print("3. 前端可能有缓存")

