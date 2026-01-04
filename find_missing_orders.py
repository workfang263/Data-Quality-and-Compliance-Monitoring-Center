"""
找出缺失的订单
详细分析为什么API有227单，但数据库只有224单
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

def find_missing_orders():
    """找出缺失的订单"""
    db = Database()
    now = beijing_time()
    today = now.date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = now.replace(second=59, microsecond=999999)
    
    print("=" * 80)
    print("找出缺失的订单")
    print("=" * 80)
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"今天范围：{today_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {today_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 获取所有活跃店铺
    stores = db.get_active_stores()
    
    # 重点关注的两个店铺
    target_shops = ['ershiyi01.myshoplaza.com', 'paidaxing01.myshoplaza.com']
    
    for shop_domain in target_shops:
        print("=" * 80)
        print(f"分析店铺：{shop_domain}")
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
        
        try:
            api = ShoplazzaAPI(shop_domain, access_token)
            orders_data = api.get_orders_all_pages(
                placed_at_min=datetime_to_iso8601(today_start),
                placed_at_max=datetime_to_iso8601(today_end)
            )
            
            if orders_data is None:
                print(f"  API调用失败")
                continue
            
            if not orders_data:
                print(f"  没有订单数据")
                continue
            
            print(f"\nAPI返回的订单数：{len(orders_data)}")
            print()
            
            # 分析每个订单
            valid_orders = []
            skipped_orders = []
            
            for order in orders_data:
                order_id = order.get('id', 'unknown')
                order_info = {
                    'order_id': order_id,
                    'placed_at': order.get('placed_at', ''),
                    'total_price': order.get('total_price', ''),
                    'skip_reason': None
                }
                
                # 检查礼品卡订单
                if _is_gift_card_order(order):
                    order_info['skip_reason'] = '礼品卡订单'
                    skipped_orders.append(order_info)
                    continue
                
                # 检查COD订单
                if _is_cod_order(order):
                    order_info['skip_reason'] = 'COD订单'
                    skipped_orders.append(order_info)
                    continue
                
                # 检查金额字段
                total_price_str = order.get('total_price') or order.get('total_price_set', {}).get('shop_money', {}).get('amount')
                if total_price_str is None:
                    order_info['skip_reason'] = '金额字段缺失'
                    skipped_orders.append(order_info)
                    continue
                
                # 解析时间
                order_dt = _get_order_beijing_time(order)
                if order_dt is None:
                    order_info['skip_reason'] = '时间解析失败'
                    skipped_orders.append(order_info)
                    continue
                
                # 验证时间范围
                if not (today_start <= order_dt <= today_end):
                    order_info['skip_reason'] = f'时间不在范围内（订单时间={order_dt.strftime("%Y-%m-%d %H:%M:%S")}）'
                    skipped_orders.append(order_info)
                    continue
                
                # 验证未来时间
                if order_dt > now:
                    order_info['skip_reason'] = f'未来时间订单（订单时间={order_dt.strftime("%Y-%m-%d %H:%M:%S")}）'
                    skipped_orders.append(order_info)
                    continue
                
                # 有效订单
                order_info['order_time'] = order_dt
                valid_orders.append(order_info)
            
            print(f"有效订单数：{len(valid_orders)}")
            print(f"跳过订单数：{len(skipped_orders)}")
            print()
            
            # 显示跳过的订单详情
            if skipped_orders:
                print("跳过的订单详情：")
                print(f"{'订单ID':<20} {'跳过原因':<30} {'placed_at':<30}")
                print("-" * 80)
                for order_info in skipped_orders:
                    print(f"{order_info['order_id']:<20} {order_info['skip_reason']:<30} {order_info['placed_at']:<30}")
                print()
            
            # 显示有效订单的时间分布
            if valid_orders:
                print("有效订单的时间分布：")
                hour_counts = {}
                for order_info in valid_orders:
                    hour = order_info['order_time'].replace(minute=0, second=0, microsecond=0)
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1
                
                for hour in sorted(hour_counts.keys()):
                    print(f"  {hour.strftime('%Y-%m-%d %H:%M:%S')}: {hour_counts[hour]} 单")
                print()
        
        except Exception as e:
            print(f"  查询失败：{e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 80)
    print("分析完成")
    print("=" * 80)


if __name__ == '__main__':
    find_missing_orders()

