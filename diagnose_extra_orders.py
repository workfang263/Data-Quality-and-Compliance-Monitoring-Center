"""
诊断多出的订单问题
找出数据库中多出的订单，分析原因
"""
import sys
import io
from datetime import datetime, timedelta
from database import Database
from shoplazza_api import ShoplazzaAPI
from utils import beijing_time, datetime_to_iso8601
from data_sync import _is_gift_card_order, _is_cod_order, _get_order_beijing_time

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

def diagnose_extra_orders():
    """诊断多出的订单"""
    db = Database()
    now = beijing_time()
    today = now.date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = now.replace(second=59, microsecond=999999)
    
    print("=" * 80)
    print("诊断多出的订单问题")
    print("=" * 80)
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"今天范围：{today_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {today_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 获取所有活跃店铺
    stores = db.get_active_stores()
    print(f"活跃店铺数量：{len(stores)}")
    print()
    
    # 1. 从API获取所有订单
    print("=" * 80)
    print("1. 从API获取所有订单")
    print("=" * 80)
    
    api_orders = {}  # {order_id: order_info}
    api_total = 0
    
    for store in stores:
        shop_domain = store['shop_domain']
        access_token = store['access_token']
        
        try:
            api = ShoplazzaAPI(shop_domain, access_token)
            orders_data = api.get_orders_all_pages(
                placed_at_min=datetime_to_iso8601(today_start),
                placed_at_max=datetime_to_iso8601(today_end)
            )
            
            if orders_data is None:
                print(f"  {shop_domain}: API调用失败")
                continue
            
            if not orders_data:
                continue
            
            store_count = 0
            for order in orders_data:
                order_id = order.get('id', 'unknown')
                
                # 过滤礼品卡和COD订单（与验证脚本一致）
                if _is_gift_card_order(order) or _is_cod_order(order):
                    continue
                
                # 检查金额字段
                total_price_str = order.get('total_price') or order.get('total_price_set', {}).get('shop_money', {}).get('amount')
                if total_price_str is None:
                    continue
                
                # 解析时间
                order_dt = _get_order_beijing_time(order)
                if order_dt is None:
                    continue
                
                # 验证时间范围
                if not (today_start <= order_dt <= today_end):
                    continue
                
                api_orders[order_id] = {
                    'shop_domain': shop_domain,
                    'order_id': order_id,
                    'placed_at': order.get('placed_at', ''),
                    'order_time': order_dt,
                    'total_price': total_price_str
                }
                store_count += 1
                api_total += 1
            
            if store_count > 0:
                print(f"  {shop_domain}: {store_count} 单")
        
        except Exception as e:
            print(f"  {shop_domain}: 查询失败 - {e}")
    
    print(f"\nAPI总订单数：{api_total}")
    print()
    
    # 2. 从数据库查询所有订单（通过店铺小时表）
    print("=" * 80)
    print("2. 从数据库查询所有订单（通过店铺小时表汇总）")
    print("=" * 80)
    
    db_total = 0
    db_store_orders = {}
    
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    shop_domain,
                    SUM(total_orders) as total_orders
                FROM shoplazza_store_hourly
                WHERE time_hour >= %s AND time_hour <= %s
                GROUP BY shop_domain
                ORDER BY shop_domain
            """
            cursor.execute(sql, (today_start, today_end))
            results = cursor.fetchall()
            
            for row in results:
                shop_domain = row['shop_domain']
                orders = int(row['total_orders'] or 0)
                db_store_orders[shop_domain] = orders
                db_total += orders
                if orders > 0:
                    print(f"  {shop_domain}: {orders} 单")
    
    print(f"\n数据库总订单数：{db_total}")
    print()
    
    # 3. 对比分析
    print("=" * 80)
    print("3. 对比分析")
    print("=" * 80)
    
    diff = db_total - api_total
    print(f"数据库订单数：{db_total}")
    print(f"API订单数：{api_total}")
    print(f"差异：{diff:+d}（{'数据库多' if diff > 0 else 'API多' if diff < 0 else '一致'}）")
    print()
    
    # 4. 按店铺对比
    print("=" * 80)
    print("4. 按店铺对比")
    print("=" * 80)
    
    print(f"{'店铺域名':<40} {'数据库':<10} {'API':<10} {'差异':<10}")
    print("-" * 80)
    
    all_shops = set(list(db_store_orders.keys()) + [o['shop_domain'] for o in api_orders.values()])
    
    for shop_domain in sorted(all_shops):
        db_orders = db_store_orders.get(shop_domain, 0)
        api_orders_count = sum(1 for o in api_orders.values() if o['shop_domain'] == shop_domain)
        shop_diff = db_orders - api_orders_count
        
        if shop_diff != 0:
            print(f"{shop_domain:<40} {db_orders:<10} {api_orders_count:<10} {shop_diff:+d}")
    
    print()
    
    # 5. 检查是否有重复数据
    print("=" * 80)
    print("5. 检查数据库是否有重复数据（同一小时多次写入）")
    print("=" * 80)
    
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    shop_domain,
                    time_hour,
                    COUNT(*) as count,
                    SUM(total_orders) as total_orders
                FROM shoplazza_store_hourly
                WHERE time_hour >= %s AND time_hour <= %s
                GROUP BY shop_domain, time_hour
                HAVING COUNT(*) > 1
                ORDER BY shop_domain, time_hour
            """
            cursor.execute(sql, (today_start, today_end))
            duplicates = cursor.fetchall()
            
            if duplicates:
                print(f"发现 {len(duplicates)} 个重复的小时数据：")
                print(f"{'店铺域名':<40} {'时间':<20} {'记录数':<10} {'订单数':<10}")
                print("-" * 80)
                for row in duplicates:
                    print(f"{row['shop_domain']:<40} {str(row['time_hour']):<20} {row['count']:<10} {int(row['total_orders'] or 0):<10}")
            else:
                print("✅ 未发现重复数据")
    
    print()
    
    # 6. 检查是否有未来时间的订单
    print("=" * 80)
    print("6. 检查数据库中是否有未来时间的订单")
    print("=" * 80)
    
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    shop_domain,
                    time_hour,
                    total_orders
                FROM shoplazza_store_hourly
                WHERE time_hour > %s
                ORDER BY shop_domain, time_hour
            """
            cursor.execute(sql, (now,))
            future_data = cursor.fetchall()
            
            if future_data:
                print(f"发现 {len(future_data)} 个未来时间的数据：")
                print(f"{'店铺域名':<40} {'时间':<20} {'订单数':<10}")
                print("-" * 80)
                for row in future_data:
                    print(f"{row['shop_domain']:<40} {str(row['time_hour']):<20} {int(row['total_orders'] or 0):<10}")
            else:
                print("✅ 未发现未来时间的数据")
    
    print()
    print("=" * 80)
    print("诊断完成")
    print("=" * 80)


if __name__ == '__main__':
    diagnose_extra_orders()

