"""
检查验证脚本和前端数据差异的原因
"""
import sys
import io
from datetime import datetime
from database import Database
from utils import beijing_time

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

db = Database()
now = beijing_time()

print("=" * 80)
print("数据差异分析")
print("=" * 80)
print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 1. 查询今天的所有小时数据
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
today_end = now.replace(hour=now.hour, minute=now.minute, second=59, microsecond=999999)

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

# 2. 对比验证脚本的数据
verify_db_orders = 179
verify_db_gmv = 12764.18
frontend_orders = 232
frontend_gmv = 14084.66

print("=" * 80)
print("数据对比")
print("=" * 80)
print(f"验证脚本显示的数据库数据: 订单数={verify_db_orders}, 销售额=${verify_db_gmv:.2f}")
print(f"前端显示的数据: 订单数={frontend_orders}, 销售额=${frontend_gmv:.2f}")
print(f"实际数据库查询的数据: 订单数={total_orders}, 销售额=${total_gmv:.2f}")
print()

# 3. 分析差异
print("=" * 80)
print("差异分析")
print("=" * 80)

if total_orders == frontend_orders and abs(total_gmv - frontend_gmv) < 0.01:
    print("✅ 实际数据库数据 = 前端显示的数据（一致）")
else:
    print(f"❌ 实际数据库数据 ≠ 前端显示的数据")
    print(f"   订单数差异: {total_orders - frontend_orders}")
    print(f"   销售额差异: ${total_gmv - frontend_gmv:.2f}")

if total_orders == verify_db_orders and abs(total_gmv - verify_db_gmv) < 0.01:
    print("✅ 实际数据库数据 = 验证脚本显示的数据库数据（一致）")
else:
    print(f"⚠️  实际数据库数据 ≠ 验证脚本显示的数据库数据")
    print(f"   订单数差异: {total_orders - verify_db_orders}")
    print(f"   销售额差异: ${total_gmv - verify_db_gmv:.2f}")
    print()
    print("可能原因:")
    print("1. 验证脚本运行的时间点不同，当时数据库的数据还没有完全更新")
    print("2. 验证脚本查询的时间范围可能不同")
    print("3. 数据库中的数据在验证脚本运行后又被更新了")

