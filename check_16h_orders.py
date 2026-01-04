"""
检查16:00数据的来源，查看实际订单时间
"""
import sys
import io
from datetime import datetime
from database import Database

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

db = Database()

print("=" * 80)
print("检查16:00数据的来源")
print("=" * 80)

# 查询16:00的单店铺数据
try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    shop_domain,
                    time_hour,
                    total_orders,
                    total_gmv,
                    created_at,
                    updated_at
                FROM shoplazza_store_hourly
                WHERE time_hour = '2025-12-31 16:00:00'
                ORDER BY total_orders DESC
                LIMIT 20
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            if rows:
                print(f"找到 {len(rows)} 个店铺在16:00的数据:")
                print(f"{'店铺域名':<40} {'订单数':<10} {'销售额':<15} {'创建时间':<20}")
                print("-" * 100)
                
                for row in rows:
                    shop_domain = row['shop_domain']
                    orders = int(row['total_orders'])
                    gmv = float(row['total_gmv'])
                    created_at = row['created_at']
                    print(f"{shop_domain:<40} {orders:<10} ${gmv:<14.2f} {str(created_at):<20}")
                
                print("-" * 100)
                print()
                print("这些数据是在什么时候写入的？")
                print(f"最早的创建时间: {min(r['created_at'] for r in rows)}")
                print(f"最晚的创建时间: {max(r['created_at'] for r in rows)}")
            else:
                print("没有找到16:00的单店铺数据")
                
except Exception as e:
    print(f"查询失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("可能的原因分析")
print("=" * 80)
print("1. API返回的订单时间可能是UTC时间，但实际订单是在16:00（北京时间）支付的")
print("2. 代码将UTC时间转换为北京时间时，可能有问题")
print("3. 或者API返回的订单时间本身就是错误的（未来的时间）")
print()
print("建议:")
print("1. 检查API返回的订单placed_at字段，看看实际时间是什么")
print("2. 检查时区转换逻辑是否正确")
print("3. 如果API返回的是未来的时间，需要过滤掉这些订单")

