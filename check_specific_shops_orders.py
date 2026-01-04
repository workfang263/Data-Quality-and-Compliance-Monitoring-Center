"""
检查特定店铺的订单详情，找出多出的订单
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

def check_shop_orders(shop_domain, access_token):
    """检查特定店铺的订单详情"""
    db = Database()
    now = beijing_time()
    today = now.date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = now.replace(second=59, microsecond=999999)
    
    print("=" * 80)
    print(f"检查店铺：{shop_domain}")
    print("=" * 80)
    print(f"今天范围：{today_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {today_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. 从API获取订单
    print("1. 从API获取订单：")
    print("-" * 80)
    
    api = ShoplazzaAPI(shop_domain, access_token)
    orders_data = api.get_orders_all_pages(
        placed_at_min=datetime_to_iso8601(today_start),
        placed_at_max=datetime_to_iso8601(today_end)
    )
    
    api_orders = []
    for order in orders_data or []:
        order_id = order.get('id', 'unknown')
        
        # 过滤礼品卡和COD订单
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
        
        api_orders.append({
            'order_id': order_id,
            'placed_at': order.get('placed_at', ''),
            'order_time': order_dt,
            'total_price': total_price_str,
            'hour': order_dt.replace(minute=0, second=0, microsecond=0)
        })
    
    print(f"API订单数：{len(api_orders)}")
    print()
    
    # 按小时分组
    api_hourly = {}
    for order in api_orders:
        hour = order['hour']
        if hour not in api_hourly:
            api_hourly[hour] = []
        api_hourly[hour].append(order)
    
    print("API订单按小时分布：")
    for hour in sorted(api_hourly.keys()):
        print(f"  {hour.strftime('%Y-%m-%d %H:00:00')}: {len(api_hourly[hour])} 单")
    print()
    
    # 2. 从数据库查询订单
    print("2. 从数据库查询订单：")
    print("-" * 80)
    
    db_hourly = {}
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    time_hour,
                    total_orders
                FROM shoplazza_store_hourly
                WHERE shop_domain = %s
                  AND time_hour >= %s AND time_hour <= %s
                ORDER BY time_hour
            """
            cursor.execute(sql, (shop_domain, today_start, today_end))
            results = cursor.fetchall()
            
            for row in results:
                time_hour = row['time_hour']
                orders = int(row['total_orders'] or 0)
                db_hourly[time_hour] = orders
                if orders > 0:
                    print(f"  {time_hour.strftime('%Y-%m-%d %H:00:00')}: {orders} 单")
    
    db_total = sum(db_hourly.values())
    print(f"\n数据库订单数：{db_total}")
    print()
    
    # 3. 对比分析
    print("3. 对比分析：")
    print("-" * 80)
    
    print(f"{'时间':<20} {'API':<10} {'数据库':<10} {'差异':<10}")
    print("-" * 80)
    
    all_hours = set(list(api_hourly.keys()) + list(db_hourly.keys()))
    diff_hours = []
    
    for hour in sorted(all_hours):
        api_count = len(api_hourly.get(hour, []))
        db_count = db_hourly.get(hour, 0)
        diff = db_count - api_count
        
        if diff != 0:
            diff_hours.append((hour, api_count, db_count, diff))
            print(f"{hour.strftime('%Y-%m-%d %H:00:00'):<20} {api_count:<10} {db_count:<10} {diff:+d}")
    
    if not diff_hours:
        print("✅ 所有小时的数据一致")
    else:
        print(f"\n发现 {len(diff_hours)} 个小时有差异")
        
        # 显示差异小时的订单详情
        for hour, api_count, db_count, diff in diff_hours:
            print(f"\n差异小时：{hour.strftime('%Y-%m-%d %H:00:00')}")
            print(f"  API订单数：{api_count}")
            print(f"  数据库订单数：{db_count}")
            print(f"  差异：{diff:+d}")
            
            if hour in api_hourly:
                print(f"\n  API订单列表：")
                for order in api_hourly[hour]:
                    print(f"    {order['order_id']}: {order['order_time'].strftime('%Y-%m-%d %H:%M:%S')} - ${order['total_price']}")
    
    print()
    print("=" * 80)
    print(f"总结：数据库 {db_total} 单，API {len(api_orders)} 单，差异 {db_total - len(api_orders):+d}")
    print("=" * 80)


if __name__ == '__main__':
    db = Database()
    stores = db.get_active_stores()
    
    # 检查有差异的店铺
    problem_shops = [
        'amao02.myshoplaza.com',
        'marmot01.myshoplaza.com',
        'paidaxing01.myshoplaza.com',
        'shutiao01.myshoplaza.com'
    ]
    
    for shop_domain in problem_shops:
        store = next((s for s in stores if s['shop_domain'] == shop_domain), None)
        if store:
            check_shop_orders(shop_domain, store['access_token'])
            print("\n" * 2)
        else:
            print(f"未找到店铺：{shop_domain}")

