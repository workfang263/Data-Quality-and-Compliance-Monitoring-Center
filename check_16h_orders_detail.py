"""
详细检查16:00的订单数据
找出为什么API有订单，但数据库没有
"""
import sys
import io
from datetime import datetime
from database import Database
from shoplazza_api import ShoplazzaAPI
from utils import beijing_time, datetime_to_iso8601
from data_sync import _is_gift_card_order, _is_cod_order, _get_order_beijing_time

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

def check_16h_orders_detail():
    """详细检查16:00的订单数据"""
    db = Database()
    now = beijing_time()
    today = now.date()
    
    # 16:00的时间范围
    hour_16_start = datetime.combine(today, datetime.min.time()).replace(hour=16, minute=0, second=0, microsecond=0)
    hour_16_end = datetime.combine(today, datetime.min.time()).replace(hour=16, minute=59, second=59, microsecond=999999)
    
    print("=" * 80)
    print("详细检查16:00的订单数据")
    print("=" * 80)
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"16:00范围：{hour_16_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {hour_16_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 重点关注的两个店铺
    target_shops = ['ershiyi01.myshoplaza.com', 'paidaxing01.myshoplaza.com']
    
    stores = db.get_active_stores()
    
    for shop_domain in target_shops:
        print("=" * 80)
        print(f"店铺：{shop_domain}")
        print("=" * 80)
        
        # 找到店铺信息
        store = None
        for s in stores:
            if s['shop_domain'] == shop_domain:
                store = s
                break
        
        if not store:
            print(f"  未找到店铺：{shop_domain}")
            continue
        
        access_token = store['access_token']
        
        # 1. 从API查询16:00的订单
        print("\n1. 从API查询16:00的订单：")
        print("-" * 80)
        
        try:
            api = ShoplazzaAPI(shop_domain, access_token)
            orders_data = api.get_orders_all_pages(
                placed_at_min=datetime_to_iso8601(hour_16_start),
                placed_at_max=datetime_to_iso8601(hour_16_end)
            )
            
            if orders_data is None:
                print("  API调用失败")
                continue
            
            if not orders_data:
                print("  没有订单数据")
                continue
            
            print(f"  API返回订单数：{len(orders_data)}")
            print()
            
            # 分析每个订单
            valid_orders = []
            skipped_orders = []
            
            for order in orders_data:
                order_id = order.get('id', 'unknown')
                placed_at = order.get('placed_at', '')
                
                # 解析时间
                order_dt = _get_order_beijing_time(order)
                
                print(f"  订单ID: {order_id}")
                print(f"    placed_at: {placed_at}")
                if order_dt:
                    print(f"    解析后时间: {order_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"    是否在16:00范围内: {hour_16_start <= order_dt <= hour_16_end}")
                else:
                    print(f"    时间解析失败")
                
                # 检查过滤条件
                if _is_gift_card_order(order):
                    print(f"    ⚠️ 被过滤：礼品卡订单")
                    skipped_orders.append({'order_id': order_id, 'reason': '礼品卡订单'})
                    continue
                
                if _is_cod_order(order):
                    print(f"    ⚠️ 被过滤：COD订单")
                    skipped_orders.append({'order_id': order_id, 'reason': 'COD订单'})
                    continue
                
                total_price_str = order.get('total_price') or order.get('total_price_set', {}).get('shop_money', {}).get('amount')
                if total_price_str is None:
                    print(f"    ⚠️ 被过滤：金额字段缺失")
                    skipped_orders.append({'order_id': order_id, 'reason': '金额字段缺失'})
                    continue
                
                if order_dt is None:
                    print(f"    ⚠️ 被过滤：时间解析失败")
                    skipped_orders.append({'order_id': order_id, 'reason': '时间解析失败'})
                    continue
                
                if not (hour_16_start <= order_dt <= hour_16_end):
                    print(f"    ⚠️ 被过滤：时间不在16:00范围内")
                    skipped_orders.append({'order_id': order_id, 'reason': '时间不在范围内'})
                    continue
                
                if order_dt > now:
                    print(f"    ⚠️ 被过滤：未来时间订单")
                    skipped_orders.append({'order_id': order_id, 'reason': '未来时间订单'})
                    continue
                
                print(f"    ✅ 有效订单")
                valid_orders.append({
                    'order_id': order_id,
                    'order_time': order_dt,
                    'total_price': total_price_str
                })
                print()
            
            print(f"\n有效订单数：{len(valid_orders)}")
            print(f"跳过订单数：{len(skipped_orders)}")
            print()
            
            # 2. 从数据库查询16:00的数据
            print("2. 从数据库查询16:00的数据：")
            print("-" * 80)
            
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT 
                            time_hour,
                            total_orders,
                            total_gmv
                        FROM shoplazza_store_hourly
                        WHERE shop_domain = %s
                          AND time_hour = %s
                    """
                    cursor.execute(sql, (shop_domain, hour_16_start))
                    result = cursor.fetchone()
                    
                    if result:
                        print(f"  时间：{result['time_hour']}")
                        print(f"  订单数：{int(result['total_orders'] or 0)}")
                        print(f"  销售额：${float(result['total_gmv'] or 0):.2f}")
                    else:
                        print(f"  ❌ 数据库中没有16:00的数据")
            
            print()
        
        except Exception as e:
            print(f"  查询失败：{e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 80)
    print("检查完成")
    print("=" * 80)


if __name__ == '__main__':
    check_16h_orders_detail()

