"""
检查时间问题：为什么10:50会显示16:00的数据
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
print("时间问题检查")
print("=" * 80)
print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"当前是: {now.hour}点{now.minute}分")
print()

# 查询今天的所有数据，包括时间戳
print("=" * 80)
print("数据库中的时间数据（包括创建时间和更新时间）")
print("=" * 80)

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
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = '2025-12-31'
                ORDER BY time_hour ASC
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            print(f"{'时间点':<20} {'订单数':<10} {'销售额':<15} {'创建时间':<20} {'更新时间':<20}")
            print("-" * 100)
            
            for row in rows:
                time_hour = row['time_hour']
                orders = int(row['total_orders'])
                gmv = float(row['total_gmv'])
                created_at = row['created_at']
                updated_at = row['updated_at']
                
                # 检查是否有未来的时间
                if time_hour > now:
                    print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {orders:<10} ${gmv:<14.2f} {str(created_at):<20} {str(updated_at):<20} ⚠️ 未来时间!")
                else:
                    print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {orders:<10} ${gmv:<14.2f} {str(created_at):<20} {str(updated_at):<20}")
            
            print("-" * 100)
            print(f"共 {len(rows)} 条数据")
            
            # 检查是否有未来的时间
            future_times = [r for r in rows if r['time_hour'] > now]
            if future_times:
                print()
                print("=" * 80)
                print("⚠️  发现未来的时间数据！")
                print("=" * 80)
                for r in future_times:
                    print(f"时间点: {r['time_hour']}, 当前时间: {now}, 差异: {(r['time_hour'] - now).total_seconds() / 3600:.1f}小时")
                print()
                print("可能原因:")
                print("1. 时区问题：数据库中的时间可能是UTC时间，而不是北京时间")
                print("2. 数据收集脚本的时间计算有问题")
                print("3. 数据被错误地写入了未来的时间")
            else:
                print()
                print("✅ 没有发现未来的时间数据")
                
except Exception as e:
    print(f"查询失败: {e}")
    import traceback
    traceback.print_exc()

