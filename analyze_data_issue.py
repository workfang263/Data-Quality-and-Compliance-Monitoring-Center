"""
详细分析数据不准确的原因
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

print("=" * 80)
print("数据不准确问题详细分析")
print("=" * 80)
print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 1. 检查是否有数据被重复累加（对比单店铺数据）
print("=" * 80)
print("1. 检查单店铺数据是否有重复累加")
print("=" * 80)

# 选择几个店铺进行详细检查
test_stores = ['natie1.myshoplaza.com', 'amao02.myshoplaza.com', 'paidaxing01.myshoplaza.com']

for shop_domain in test_stores:
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        time_hour,
                        total_orders,
                        total_gmv,
                        created_at,
                        updated_at
                    FROM shoplazza_store_hourly
                    WHERE shop_domain = %s
                      AND DATE(time_hour) = '2025-12-31'
                    ORDER BY time_hour ASC
                """
                cursor.execute(sql, (shop_domain,))
                store_data = cursor.fetchall()
                
                if store_data:
                    total_orders = sum(int(r['total_orders']) for r in store_data)
                    total_gmv = sum(float(r['total_gmv']) for r in store_data)
                    
                    # 检查是否有多次更新
                    update_times = {}
                    for r in store_data:
                        hour = r['time_hour']
                        if hour not in update_times:
                            update_times[hour] = []
                        update_times[hour].append(r['updated_at'])
                    
                    multiple_updates = {h: times for h, times in update_times.items() if len(times) > 1}
                    
                    print(f"\n店铺: {shop_domain}")
                    print(f"  数据库订单数: {total_orders}")
                    print(f"  数据库销售额: ${total_gmv:.2f}")
                    if multiple_updates:
                        print(f"  ⚠️  发现 {len(multiple_updates)} 个小时有多次更新:")
                        for h, times in list(multiple_updates.items())[:3]:
                            print(f"    {h.strftime('%H:00')}: 更新了 {len(times)} 次")
    except Exception as e:
        print(f"查询失败 {shop_domain}: {e}")

print()

# 2. 检查数据收集的时间范围
print("=" * 80)
print("2. 检查数据收集的时间范围")
print("=" * 80)

# 检查每个小时的数据更新时间，看是否有异常
try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    time_hour,
                    total_orders,
                    total_gmv,
                    updated_at,
                    created_at
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = '2025-12-31'
                ORDER BY time_hour ASC
            """
            cursor.execute(sql)
            hourly_data = cursor.fetchall()
            
            print(f"{'时间':<20} {'订单数':<10} {'销售额':<15} {'创建时间':<20} {'最后更新':<20}")
            print("-" * 90)
            
            for row in hourly_data:
                time_hour = row['time_hour']
                orders = int(row['total_orders'])
                gmv = float(row['total_gmv'])
                created_at = row['created_at']
                updated_at = row['updated_at']
                
                # 检查是否有多次更新
                update_count = 1 if created_at == updated_at else 2
                
                print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {orders:<10} ${gmv:<14.2f} "
                      f"{str(created_at):<20} {str(updated_at):<20}")
except Exception as e:
    print(f"查询失败: {e}")

print()

# 3. 检查是否有数据被多次写入（通过updated_at判断）
print("=" * 80)
print("3. 检查数据是否被多次写入")
print("=" * 80)

try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            # 检查哪些小时的数据被多次更新
            sql = """
                SELECT 
                    time_hour,
                    COUNT(*) as update_count,
                    MIN(updated_at) as first_update,
                    MAX(updated_at) as last_update,
                    SUM(total_orders) as total_orders,
                    SUM(total_gmv) as total_gmv
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = '2025-12-31'
                GROUP BY time_hour
                HAVING COUNT(*) > 1 OR MIN(updated_at) != MAX(updated_at)
                ORDER BY time_hour ASC
            """
            cursor.execute(sql)
            multiple_updates = cursor.fetchall()
            
            if multiple_updates:
                print(f"⚠️  发现 {len(multiple_updates)} 个小时的数据被多次更新:")
                for row in multiple_updates:
                    time_hour = row['time_hour']
                    update_count = row['update_count']
                    first_update = row['first_update']
                    last_update = row['last_update']
                    total_orders = int(row['total_orders'])
                    total_gmv = float(row['total_gmv'])
                    
                    print(f"  {time_hour.strftime('%H:00')}: 更新了 {update_count} 次, "
                          f"首次: {first_update}, 最后: {last_update}, "
                          f"订单数={total_orders}, 销售额=${total_gmv:.2f}")
            else:
                print("✅ 没有发现数据被多次更新（每个小时只有一条记录）")
except Exception as e:
    print(f"查询失败: {e}")

print()

# 4. 检查实时同步脚本和补全脚本是否冲突
print("=" * 80)
print("4. 检查实时同步脚本和补全脚本是否冲突")
print("=" * 80)

# 检查日志，看是否有冲突
print("检查要点:")
print("1. fill_today_data.py 使用覆盖模式写入（insert_or_update_hourly_data）")
print("2. 实时同步脚本使用增量累加模式（insert_or_update_hourly_data_incremental）")
print("3. 如果fill_today_data.py运行后，实时同步脚本继续运行，会继续累加数据")
print()
print("可能的问题:")
print("- fill_today_data.py 清空数据后重新收集")
print("- 但实时同步脚本可能在这之后继续运行，导致数据被重复累加")
print("- 或者fill_today_data.py收集的数据范围有问题")

