"""
分析数据不准确的原因
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
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
today_end = now.replace(hour=now.hour, minute=now.minute, second=59, microsecond=999999)

print("=" * 80)
print("数据准确性分析")
print("=" * 80)
print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"查询范围: {today_start} 至 {today_end}")
print()

# 1. 检查是否有重复的小时数据
print("=" * 80)
print("1. 检查是否有重复的小时数据")
print("=" * 80)
try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    time_hour,
                    COUNT(*) as count,
                    SUM(total_orders) as total_orders,
                    SUM(total_gmv) as total_gmv
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = '2025-12-31'
                GROUP BY time_hour
                HAVING COUNT(*) > 1
            """
            cursor.execute(sql)
            duplicates = cursor.fetchall()
            
            if duplicates:
                print(f"⚠️  发现 {len(duplicates)} 个重复的小时数据:")
                for row in duplicates:
                    print(f"  时间点: {row['time_hour']}, 重复次数: {row['count']}, "
                          f"订单数总和: {row['total_orders']}, 销售额总和: ${float(row['total_gmv']):.2f}")
            else:
                print("✅ 没有发现重复的小时数据")
except Exception as e:
    print(f"查询失败: {e}")

print()

# 2. 检查是否有测试店铺的数据
print("=" * 80)
print("2. 检查是否有测试店铺的数据")
print("=" * 80)
try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    shop_domain,
                    SUM(total_orders) as total_orders,
                    SUM(total_gmv) as total_gmv
                FROM shoplazza_store_hourly
                WHERE DATE(time_hour) = '2025-12-31'
                  AND shop_domain LIKE '%test%'
                GROUP BY shop_domain
            """
            cursor.execute(sql)
            test_stores = cursor.fetchall()
            
            if test_stores:
                print(f"⚠️  发现 {len(test_stores)} 个测试店铺的数据:")
                total_test_orders = 0
                total_test_gmv = 0.0
                for row in test_stores:
                    orders = int(row['total_orders'])
                    gmv = float(row['total_gmv'])
                    total_test_orders += orders
                    total_test_gmv += gmv
                    print(f"  {row['shop_domain']}: 订单数={orders}, 销售额=${gmv:.2f}")
                print(f"  测试店铺总计: 订单数={total_test_orders}, 销售额=${total_test_gmv:.2f}")
            else:
                print("✅ 没有发现测试店铺的数据")
except Exception as e:
    print(f"查询失败: {e}")

print()

# 3. 检查每个小时的数据，看是否有异常
print("=" * 80)
print("3. 检查每个小时的数据（按小时汇总）")
print("=" * 80)
try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    time_hour,
                    total_orders,
                    total_gmv,
                    updated_at
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = '2025-12-31'
                ORDER BY time_hour ASC
            """
            cursor.execute(sql)
            hourly_data = cursor.fetchall()
            
            print(f"{'时间':<20} {'订单数':<10} {'销售额':<15} {'更新时间':<20}")
            print("-" * 70)
            
            total_orders = 0
            total_gmv = 0.0
            
            for row in hourly_data:
                time_hour = row['time_hour']
                orders = int(row['total_orders'])
                gmv = float(row['total_gmv'])
                updated_at = row['updated_at']
                
                total_orders += orders
                total_gmv += gmv
                
                print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {orders:<10} ${gmv:<14.2f} {str(updated_at):<20}")
            
            print("-" * 70)
            print(f"{'总计':<20} {total_orders:<10} ${total_gmv:<14.2f}")
            print()
            print(f"数据库总计: 订单数={total_orders}, 销售额=${total_gmv:.2f}")
            print(f"API总计: 订单数=221, 销售额=$15795.85")
            print(f"差异: 订单数={total_orders - 221}, 销售额=${total_gmv - 15795.85:.2f}")
except Exception as e:
    print(f"查询失败: {e}")

print()

# 4. 检查单店铺数据，看是否有重复累加
print("=" * 80)
print("4. 检查单店铺数据是否有重复累加（抽样检查）")
print("=" * 80)
try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            # 随机选择一个店铺检查
            sql = """
                SELECT 
                    shop_domain,
                    time_hour,
                    total_orders,
                    total_gmv,
                    updated_at
                FROM shoplazza_store_hourly
                WHERE DATE(time_hour) = '2025-12-31'
                  AND shop_domain = 'natie1.myshoplaza.com'
                ORDER BY time_hour ASC
            """
            cursor.execute(sql)
            store_data = cursor.fetchall()
            
            if store_data:
                print(f"店铺: natie1.myshoplaza.com")
                print(f"{'时间':<20} {'订单数':<10} {'销售额':<15} {'更新时间':<20}")
                print("-" * 70)
                
                store_total_orders = 0
                store_total_gmv = 0.0
                
                for row in store_data:
                    time_hour = row['time_hour']
                    orders = int(row['total_orders'])
                    gmv = float(row['total_gmv'])
                    updated_at = row['updated_at']
                    
                    store_total_orders += orders
                    store_total_gmv += gmv
                    
                    print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {orders:<10} ${gmv:<14.2f} {str(updated_at):<20}")
                
                print("-" * 70)
                print(f"{'总计':<20} {store_total_orders:<10} ${store_total_gmv:<14.2f}")
                print(f"API显示该店铺订单数: 46")
                print(f"差异: {store_total_orders - 46}")
except Exception as e:
    print(f"查询失败: {e}")

print()

# 5. 检查是否有未来时间的数据
print("=" * 80)
print("5. 检查是否有未来时间的数据")
print("=" * 80)
try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    time_hour,
                    total_orders,
                    total_gmv
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = '2025-12-31'
                  AND time_hour > %s
                ORDER BY time_hour ASC
            """
            cursor.execute(sql, (now,))
            future_data = cursor.fetchall()
            
            if future_data:
                print(f"⚠️  发现 {len(future_data)} 个未来时间的数据:")
                for row in future_data:
                    time_hour = row['time_hour']
                    orders = int(row['total_orders'])
                    gmv = float(row['total_gmv'])
                    time_diff = (time_hour - now).total_seconds() / 3600
                    print(f"  时间点: {time_hour}, 订单数={orders}, 销售额=${gmv:.2f}, "
                          f"距现在: {time_diff:.1f}小时")
            else:
                print("✅ 没有发现未来时间的数据")
except Exception as e:
    print(f"查询失败: {e}")

