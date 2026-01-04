"""
检查今天数据是否重复
"""
import sys
import io
from datetime import datetime
from database import Database
from utils import beijing_time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

def check_double_data():
    """检查今天的数据是否有重复累加"""
    db = Database()
    now = beijing_time()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    print("=" * 80)
    print("检查今天数据是否有重复")
    print("=" * 80)
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查数据库中每个小时的数据
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            # 查询今天所有小时的数据
            sql = """
                SELECT 
                    time_hour,
                    total_orders,
                    total_gmv,
                    total_visitors,
                    updated_at
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = DATE(%s)
                ORDER BY time_hour ASC
            """
            cursor.execute(sql, (today_start,))
            rows = cursor.fetchall()
            
            if not rows:
                print("⚠️  今天没有数据")
                return
            
            print(f"今天共有 {len(rows)} 个小时的数据")
            print()
            print(f"{'时间':<20} {'订单数':<12} {'销售额':<18} {'访客数':<12} {'更新时间'}")
            print("-" * 100)
            
            total_orders = 0
            total_gmv = 0.0
            total_visitors = 0
            
            for row in rows:
                time_hour = row['time_hour']
                orders = row['total_orders']
                gmv = row['total_gmv']
                visitors = row['total_visitors']
                updated_at = row['updated_at']
                
                total_orders += orders
                total_gmv += float(gmv)
                total_visitors += visitors
                
                print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {orders:<12} ${float(gmv):<17.2f} {visitors:<12} {updated_at}")
            
            print("-" * 100)
            print(f"{'总计':<20} {total_orders:<12} ${total_gmv:<17.2f} {total_visitors:<12}")
            print()
            
            # 检查是否有重复的小时记录（理论上不应该有，因为有唯一索引）
            sql_duplicate = """
                SELECT 
                    time_hour,
                    COUNT(*) as count
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = DATE(%s)
                GROUP BY time_hour
                HAVING COUNT(*) > 1
            """
            cursor.execute(sql_duplicate, (today_start,))
            duplicates = cursor.fetchall()
            
            if duplicates:
                print("❌ 发现重复的小时记录！")
                for dup in duplicates:
                    print(f"  时间: {dup['time_hour']}, 重复次数: {dup['count']}")
            else:
                print("✅ 没有重复的小时记录（每个小时只有一条数据）")
            print()
            
            # 检查每个小时的订单数是否异常（比如某些小时的订单数特别大）
            print("检查异常的小时数据：")
            print("-" * 100)
            avg_orders = total_orders / len(rows) if rows else 0
            
            for row in rows:
                orders = row['total_orders']
                time_hour = row['time_hour']
                # 如果某个小时的订单数超过平均值的3倍，可能是重复累加了
                if avg_orders > 0 and orders > avg_orders * 3:
                    print(f"⚠️  {time_hour.strftime('%H:00')}: 订单数 {orders} (平均值: {avg_orders:.1f})")
            
            print()
            
            # 检查明细表（单店铺数据）
            print("检查单店铺明细表：")
            print("-" * 100)
            
            sql_store = """
                SELECT 
                    shop_domain,
                    time_hour,
                    total_orders,
                    total_gmv
                FROM shoplazza_store_hourly
                WHERE DATE(time_hour) = DATE(%s)
                ORDER BY time_hour ASC, shop_domain
                LIMIT 50
            """
            cursor.execute(sql_store, (today_start,))
            store_rows = cursor.fetchall()
            
            if store_rows:
                print(f"前50条明细数据：")
                print(f"{'店铺':<40} {'时间':<20} {'订单数':<12} {'销售额':<18}")
                print("-" * 100)
                for row in store_rows[:20]:  # 只显示前20条
                    print(f"{row['shop_domain']:<40} {row['time_hour'].strftime('%Y-%m-%d %H:00'):<20} {row['total_orders']:<12} ${float(row['total_gmv']):<17.2f}")
                print(f"... (共 {len(store_rows)} 条明细数据)")
            else:
                print("⚠️  明细表今天没有数据")
            print()

if __name__ == '__main__':
    try:
        check_double_data()
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        traceback.print_exc()

