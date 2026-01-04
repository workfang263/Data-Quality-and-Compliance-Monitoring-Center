"""
检查单店铺明细表的数据，看是否有重复累加
"""
import sys
import io
from datetime import datetime
from database import Database
from utils import beijing_time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

def check_store_detail():
    """检查明细表的数据"""
    db = Database()
    now = beijing_time()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    print("=" * 80)
    print("检查单店铺明细表数据")
    print("=" * 80)
    print()
    
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            # 按小时汇总明细表的订单数和销售额
            sql = """
                SELECT 
                    time_hour,
                    SUM(total_orders) as sum_orders,
                    SUM(total_gmv) as sum_gmv,
                    COUNT(DISTINCT shop_domain) as store_count
                FROM shoplazza_store_hourly
                WHERE DATE(time_hour) = DATE(%s)
                GROUP BY time_hour
                ORDER BY time_hour ASC
            """
            cursor.execute(sql, (today_start,))
            detail_rows = cursor.fetchall()
            
            # 查询汇总表的数据
            sql_overview = """
                SELECT 
                    time_hour,
                    total_orders,
                    total_gmv
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = DATE(%s)
                ORDER BY time_hour ASC
            """
            cursor.execute(sql_overview, (today_start,))
            overview_rows = cursor.fetchall()
            
            # 创建汇总表的字典，方便对比
            overview_dict = {row['time_hour']: row for row in overview_rows}
            
            print(f"{'时间':<20} {'明细表订单':<15} {'汇总表订单':<15} {'明细表销售额':<20} {'汇总表销售额':<20} {'差异订单':<15} {'状态'}")
            print("-" * 120)
            
            total_detail_orders = 0
            total_detail_gmv = 0.0
            total_overview_orders = 0
            total_overview_gmv = 0.0
            
            for row in detail_rows:
                time_hour = row['time_hour']
                detail_orders = row['sum_orders'] or 0
                detail_gmv = float(row['sum_gmv'] or 0)
                
                overview = overview_dict.get(time_hour)
                if overview:
                    overview_orders = overview['total_orders']
                    overview_gmv = float(overview['total_gmv'])
                    
                    diff_orders = detail_orders - overview_orders
                    status = "✅" if abs(diff_orders) <= 0 else f"❌ 差异 {diff_orders:+d}"
                    
                    total_detail_orders += detail_orders
                    total_detail_gmv += detail_gmv
                    total_overview_orders += overview_orders
                    total_overview_gmv += overview_gmv
                    
                    print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {detail_orders:<15} {overview_orders:<15} ${detail_gmv:<19.2f} ${overview_gmv:<19.2f} {diff_orders:<15} {status}")
                else:
                    print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {detail_orders:<15} {'N/A':<15} ${detail_gmv:<19.2f} {'N/A':<19.2f}")
            
            print("-" * 120)
            print(f"{'总计':<20} {total_detail_orders:<15} {total_overview_orders:<15} ${total_detail_gmv:<19.2f} ${total_overview_gmv:<19.2f}")
            print()
            
            # 对比总计
            diff_total_orders = total_detail_orders - total_overview_orders
            diff_total_gmv = total_detail_gmv - total_overview_gmv
            
            print(f"明细表总计：订单={total_detail_orders}, 销售额=${total_detail_gmv:.2f}")
            print(f"汇总表总计：订单={total_overview_orders}, 销售额=${total_overview_gmv:.2f}")
            print(f"差异：订单={diff_total_orders:+d}, 销售额=${diff_total_gmv:+.2f}")
            
            if abs(diff_total_orders) > 0 or abs(diff_total_gmv) > 0.01:
                print("❌ 明细表和汇总表数据不一致！")
            else:
                print("✅ 明细表和汇总表数据一致")

if __name__ == '__main__':
    try:
        check_store_detail()
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        traceback.print_exc()

