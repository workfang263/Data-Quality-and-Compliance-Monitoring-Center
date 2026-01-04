"""
检查数据库中的数据分布
找出哪些小时有数据，哪些小时没有数据
"""
import sys
import io
from datetime import datetime
from database import Database
from utils import beijing_time

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

def check_db_data_distribution():
    """检查数据库中的数据分布"""
    db = Database()
    now = beijing_time()
    today = now.date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = now.replace(second=59, microsecond=999999)
    
    print("=" * 80)
    print("检查数据库中的数据分布")
    print("=" * 80)
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"今天范围：{today_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {today_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 重点关注的两个店铺
    target_shops = ['ershiyi01.myshoplaza.com', 'paidaxing01.myshoplaza.com']
    
    for shop_domain in target_shops:
        print("=" * 80)
        print(f"店铺：{shop_domain}")
        print("=" * 80)
        
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        time_hour,
                        total_orders,
                        total_gmv
                    FROM shoplazza_store_hourly
                    WHERE shop_domain = %s
                      AND time_hour >= %s AND time_hour <= %s
                    ORDER BY time_hour
                """
                cursor.execute(sql, (shop_domain, today_start, today_end))
                results = cursor.fetchall()
                
                if not results:
                    print("  数据库中没有数据")
                    continue
                
                print(f"{'时间':<20} {'订单数':<10} {'销售额':<15}")
                print("-" * 50)
                
                total_orders = 0
                for row in results:
                    time_hour = row['time_hour']
                    orders = int(row['total_orders'] or 0)
                    gmv = float(row['total_gmv'] or 0)
                    total_orders += orders
                    print(f"{str(time_hour):<20} {orders:<10} ${gmv:<14.2f}")
                
                print("-" * 50)
                print(f"{'总计':<20} {total_orders:<10}")
                print()
    
    print("=" * 80)
    print("检查完成")
    print("=" * 80)


if __name__ == '__main__':
    check_db_data_distribution()

