"""
诊断订单丢失问题的脚本
对比5分钟段查询和全天查询的差异，找出订单丢失的位置
"""
import sys
import io
from datetime import datetime, timedelta
from database import Database
from shoplazza_api import ShoplazzaAPI
from utils import beijing_time, datetime_to_iso8601
from data_sync import sync_store_data_for_five_minutes, _is_gift_card_order, _is_cod_order
import logging

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def diagnose_order_loss():
    """诊断订单丢失问题"""
    db = Database()
    now = beijing_time()
    today = now.date()
    today_start = datetime.combine(today, datetime.min.time())
    
    # 计算今天的所有5分钟段（到最近完成的段）
    current_minute = now.minute
    current_segment_start_minute = (current_minute // 5) * 5
    latest_completed_segment_end = now.replace(
        minute=current_segment_start_minute,
        second=0,
        microsecond=0
    ) - timedelta(microseconds=1)
    
    print("=" * 80)
    print("订单丢失问题诊断")
    print("=" * 80)
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"诊断日期：{today.strftime('%Y-%m-%d')}")
    print(f"时间段范围：{today_start.strftime('%H:%M:%S')} - {latest_completed_segment_end.strftime('%H:%M:%S')}")
    print()
    
    # 获取所有活跃店铺
    stores = db.get_active_stores()
    print(f"活跃店铺数量：{len(stores)}")
    print()
    
    # 方法1：全天查询（一次查询整个今天）
    print("=" * 80)
    print("方法1：全天查询（一次查询整个今天）")
    print("=" * 80)
    
    full_day_orders = {}  # {shop_domain: orders_count}
    full_day_total = 0
    
    for store in stores:
        shop_domain = store['shop_domain']
        access_token = store['access_token']
        
        try:
            api = ShoplazzaAPI(shop_domain, access_token)
            orders_data = api.get_orders_all_pages(
                placed_at_min=datetime_to_iso8601(today_start),
                placed_at_max=datetime_to_iso8601(latest_completed_segment_end)
            )
            
            if orders_data is None:
                print(f"  {shop_domain}: API调用失败（可能店铺已禁用）")
                full_day_orders[shop_domain] = 0
                continue
            
            if not orders_data:
                full_day_orders[shop_domain] = 0
                continue
            
            store_orders = 0
            for order in orders_data:
                if _is_gift_card_order(order) or _is_cod_order(order):
                    continue
                
                total_price_str = order.get('total_price') or order.get('total_price_set', {}).get('shop_money', {}).get('amount')
                if total_price_str is None:
                    continue
                
                try:
                    if isinstance(total_price_str, str):
                        total_price_str = total_price_str.strip().replace('$', '').replace(',', '')
                        if not total_price_str:
                            continue
                    float(total_price_str)
                    store_orders += 1
                except (ValueError, TypeError):
                    continue
            
            full_day_orders[shop_domain] = store_orders
            full_day_total += store_orders
            
        except Exception as e:
            print(f"  {shop_domain}: 查询失败 - {e}")
            full_day_orders[shop_domain] = 0
    
    print(f"\n全天查询总计：{full_day_total} 单")
    print()
    
    # 方法2：5分钟段查询（按5分钟段分别查询）
    print("=" * 80)
    print("方法2：5分钟段查询（按5分钟段分别查询，模拟fill_date_data.py）")
    print("=" * 80)
    
    # 计算所有5分钟段
    segments = []
    current_segment_start = today_start
    while current_segment_start < latest_completed_segment_end:
        current_segment_end = current_segment_start + timedelta(minutes=5) - timedelta(microseconds=1)
        segments.append((current_segment_start, current_segment_end))
        current_segment_start = current_segment_start + timedelta(minutes=5)
    
    print(f"5分钟段数量：{len(segments)}")
    print()
    
    segment_orders = {}  # {shop_domain: orders_count}
    segment_total = 0
    segment_details = {}  # {shop_domain: {segment: orders}}
    
    for store in stores:
        shop_domain = store['shop_domain']
        access_token = store['access_token']
        segment_orders[shop_domain] = 0
        segment_details[shop_domain] = {}
        
        print(f"处理店铺：{shop_domain}...")
        
        for segment_start, segment_end in segments:
            try:
                result = sync_store_data_for_five_minutes(
                    shop_domain,
                    access_token,
                    segment_start,
                    segment_end
                )
                
                if result.get('success'):
                    orders = result.get('orders', 0)
                    segment_orders[shop_domain] += orders
                    segment_details[shop_domain][f"{segment_start.strftime('%H:%M')}-{segment_end.strftime('%H:%M')}"] = orders
                else:
                    print(f"  ⚠️  时间段 {segment_start.strftime('%H:%M')}-{segment_end.strftime('%H:%M')} 收集失败: {result.get('error')}")
                    
            except Exception as e:
                print(f"  ❌ 时间段 {segment_start.strftime('%H:%M')}-{segment_end.strftime('%H:%M')} 异常: {e}")
        
        segment_total += segment_orders[shop_domain]
        print(f"  {shop_domain}: {segment_orders[shop_domain]} 单")
    
    print(f"\n5分钟段查询总计：{segment_total} 单")
    print()
    
    # 对比分析
    print("=" * 80)
    print("对比分析")
    print("=" * 80)
    
    print(f"全天查询订单数：{full_day_total}")
    print(f"5分钟段查询订单数：{segment_total}")
    print(f"差异：{full_day_total - segment_total:+d} 单")
    print()
    
    # 找出差异最大的店铺
    print("各店铺对比：")
    print(f"{'店铺域名':<45} {'全天查询':<10} {'5分钟段查询':<12} {'差异':<10}")
    print("-" * 80)
    
    diff_stores = []
    for shop_domain in set(list(full_day_orders.keys()) + list(segment_orders.keys())):
        full_day_count = full_day_orders.get(shop_domain, 0)
        segment_count = segment_orders.get(shop_domain, 0)
        diff = full_day_count - segment_count
        
        if diff != 0:
            diff_stores.append((shop_domain, full_day_count, segment_count, diff))
            print(f"{shop_domain:<45} {full_day_count:<10} {segment_count:<12} {diff:+d}")
    
    if not diff_stores:
        print("✅ 所有店铺的订单数一致")
    else:
        print(f"\n发现 {len(diff_stores)} 个店铺有差异")
        
        # 详细分析差异最大的店铺
        if diff_stores:
            max_diff_shop = max(diff_stores, key=lambda x: abs(x[3]))
            print(f"\n差异最大的店铺：{max_diff_shop[0]}")
            print(f"  全天查询：{max_diff_shop[1]} 单")
            print(f"  5分钟段查询：{max_diff_shop[2]} 单")
            print(f"  差异：{max_diff_shop[3]} 单")
            
            # 显示该店铺每个时间段的订单数
            if max_diff_shop[0] in segment_details:
                print(f"\n  各时间段订单数分布：")
                for segment, orders in segment_details[max_diff_shop[0]].items():
                    if orders > 0:
                        print(f"    {segment}: {orders} 单")
    
    print()
    print("=" * 80)
    print("诊断完成")
    print("=" * 80)
    
    # 结论和建议
    print("\n结论和建议：")
    if full_day_total == segment_total:
        print("✅ 两种查询方式的结果一致，问题可能不在查询方式")
        print("   建议检查：数据写入逻辑、数据累加逻辑")
    else:
        print(f"❌ 两种查询方式的结果不一致（差异：{full_day_total - segment_total} 单）")
        print("   问题可能在于：")
        print("   1. 5分钟段查询时某些时间段遗漏了订单")
        print("   2. 订单时间边界问题")
        print("   3. API在小时间范围查询时返回不准确")


if __name__ == '__main__':
    try:
        diagnose_order_loss()
    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        import traceback
        print(f"\n错误: {e}")
        traceback.print_exc()

