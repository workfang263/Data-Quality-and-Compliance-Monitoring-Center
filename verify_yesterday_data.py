"""
验证指定日期的数据是否准确
对比API返回的数据和数据库中的数据

使用方法：
python verify_yesterday_data.py                    # 验证昨天的数据
python verify_yesterday_data.py --date 2025-01-15   # 验证指定日期的数据
"""
import sys
import io
import argparse
from datetime import datetime, timedelta
from database import Database
from shoplazza_api import ShoplazzaAPI
from utils import beijing_time, datetime_to_iso8601, parse_iso8601

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

def verify_yesterday_data(target_date_str: str = None):
    """
    验证指定日期的数据，如果不指定则验证昨天
    
    Args:
        target_date_str: 目标日期字符串，格式：YYYY-MM-DD，如果不指定则验证昨天
    """
    db = Database()
    
    # 如果指定了日期，使用指定日期；否则使用昨天
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            print(f"❌ 日期格式错误，请使用 YYYY-MM-DD 格式，例如：2025-01-15")
            return
    else:
        now = beijing_time()
        target_date = (now - timedelta(days=1)).date()
    
    # 获取目标日期的开始和结束时间
    target_start = datetime.combine(target_date, datetime.min.time())
    target_end = datetime.combine(target_date, datetime.max.time().replace(microsecond=999999))
    
    print("=" * 80)
    print(f"验证 {target_date.strftime('%Y-%m-%d')} 的数据准确性")
    print("=" * 80)
    now = beijing_time()
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标日期范围：{target_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {target_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 获取所有活跃店铺
    stores = db.get_active_stores()
    print(f"活跃店铺数量：{len(stores)}")
    print()
    
    # 1. 从数据库查询昨天的数据
    print("=" * 80)
    print("1. 数据库中的数据（按小时聚合）")
    print("=" * 80)
    
    # 查询目标日期的数据
    db_data = db.get_hourly_data(
        start_time=target_start,
        end_time=target_end,
        start_hour=None,
        end_hour=None
    )
    
    db_total_orders = 0
    db_total_gmv = 0.0
    db_total_visitors = 0
    db_hourly_data = {}
    
    if db_data:
        print(f"{'时间':<20} {'订单数':<10} {'销售额':<15} {'访客数':<10}")
        print("-" * 80)
        for row in db_data:
            time_hour = row['time_hour']
            orders = row['total_orders']
            gmv = row['total_gmv']
            visitors = row['total_visitors']
            
            db_total_orders += orders
            db_total_gmv += float(gmv)
            db_total_visitors += visitors
            db_hourly_data[time_hour] = {
                'orders': orders,
                'gmv': float(gmv),
                'visitors': visitors
            }
            
            print(f"{time_hour.strftime('%Y-%m-%d %H:00'):<20} {orders:<10} ${gmv:<14} {visitors:<10}")
    else:
        print(f"⚠️  数据库中没有 {target_date.strftime('%Y-%m-%d')} 的数据！")
    
    print("-" * 80)
    print(f"{'总计':<20} {db_total_orders:<10} ${db_total_gmv:<14} {db_total_visitors:<10}")
    print()
    
    # 2. 从API查询昨天的数据
    print("=" * 80)
    print("2. API返回的数据（所有店铺汇总）")
    print("=" * 80)
    
    api_total_orders = 0
    api_total_gmv = 0.0
    api_total_visitors = 0
    api_store_orders = {}  # 每个店铺的订单数
    
    # 按店铺收集数据
    for store in stores:
        shop_domain = store['shop_domain']
        access_token = store['access_token']
        
        print(f"\n正在查询店铺：{shop_domain}...")
        
        try:
            # 创建API实例
            api = ShoplazzaAPI(shop_domain, access_token)
            
            # 查询订单数据
            orders_data = api.get_orders_all_pages(
                placed_at_min=datetime_to_iso8601(target_start),
                placed_at_max=datetime_to_iso8601(target_end)
            )
            
            if orders_data is None:
                print(f"  ❌ API调用失败（可能店铺已禁用或过期）")
                api_store_orders[shop_domain] = 0
                continue
            
            store_orders = 0
            store_gmv = 0.0
            
            # 过滤礼品卡和COD订单（与实时同步脚本逻辑完全一致）
            from data_sync import _is_gift_card_order, _is_cod_order
            
            for order in orders_data:
                order_id = order.get('id', 'unknown')
                
                # 过滤礼品卡订单（与实时同步脚本一致）
                if _is_gift_card_order(order):
                    continue
                
                # 过滤COD订单（与实时同步脚本一致）
                if _is_cod_order(order):
                    continue
                
                # 获取订单的实际支付价格（与实时同步脚本完全一致）
                total_price_str = order.get('total_price') or order.get('total_price_set', {}).get('shop_money', {}).get('amount')
                
                # 如果金额字段完全缺失，跳过（与实时同步脚本一致）
                if total_price_str is None:
                    continue
                
                try:
                    # 处理字符串格式（与实时同步脚本一致）
                    if isinstance(total_price_str, str):
                        total_price_str = total_price_str.strip().replace('$', '').replace(',', '')
                        # 如果处理后的字符串为空，跳过
                        if not total_price_str:
                            continue
                    
                    total_price = float(total_price_str)
                    
                    # 验证金额是否有效（与实时同步脚本一致）
                    # 负数价格也累加（与实时同步脚本一致）
                    # 零价格也累加（与实时同步脚本一致）
                    
                    # 金额解析成功，同时累加订单数和销售额（与实时同步脚本一致）
                    store_orders += 1
                    store_gmv += total_price
                    
                except (ValueError, TypeError):
                    # 价格解析失败，订单数和销售额都不累加（与实时同步脚本一致）
                    continue
            
            api_total_orders += store_orders
            api_total_gmv += store_gmv
            api_store_orders[shop_domain] = store_orders
            
            print(f"  订单数：{store_orders}, 销售额：${store_gmv:.2f}")
            
        except Exception as e:
            print(f"  ❌ 查询失败：{str(e)}")
            api_store_orders[shop_domain] = 0
    
    # 查询访客数（使用数据分析API，查询所有店铺并累加）
    print(f"\n正在查询所有店铺的访客数...")
    try:
        from utils import datetime_to_timestamp
        begin_ts = int(target_start.timestamp())
        end_ts = int(target_end.timestamp())
        
        # 查询所有店铺的访客数并累加（与实时同步脚本逻辑一致）
        for store in stores:
            shop_domain = store['shop_domain']
            access_token = store['access_token']
            
            try:
                api = ShoplazzaAPI(shop_domain, access_token)
                analysis_data = api.get_data_analysis_all_pages(
                    begin_ts, end_ts, 'dt_by_day',
                    indicator=['uv'],
                    filter_crawler_type=''  # 不过滤爬虫流量
                )
                
                if analysis_data is None:
                    continue  # API调用失败，跳过
                
                store_visitors = 0
                if analysis_data:
                    for item in analysis_data:
                        date_time_str = item.get('date_time', '')
                        uv = item.get('uv', 0)
                        
                        if date_time_str:
                            try:
                                item_dt = parse_iso8601(date_time_str)
                                if item_dt.date() == target_date:
                                    # 处理UV数据（与实时同步脚本一致）
                                    if isinstance(uv, dict):
                                        store_visitors = int(uv.get('value', 0))
                                    elif isinstance(uv, (int, float)):
                                        store_visitors = int(uv)
                                    break
                            except Exception:
                                continue
                
                # 累加所有店铺的访客数（与实时同步脚本一致）
                api_total_visitors += store_visitors
                
            except Exception as e:
                print(f"  ⚠️  店铺 {shop_domain} 访客数查询失败：{str(e)}")
        
        print(f"  查询完成，总访客数：{api_total_visitors}")
        
    except Exception as e:
        print(f"  ⚠️  访客数查询失败：{str(e)}")
    
    print()
    print("-" * 80)
    print(f"{'总计':<20} {api_total_orders:<10} ${api_total_gmv:<14} {api_total_visitors:<10}")
    print()
    
    # 3. 对比分析
    print("=" * 80)
    print("3. 数据对比分析")
    print("=" * 80)
    
    print(f"{'指标':<15} {'数据库':<15} {'API':<15} {'差异':<15} {'状态'}")
    print("-" * 80)
    
    # 订单数对比
    orders_diff = api_total_orders - db_total_orders
    orders_status = "✅ 正常" if abs(orders_diff) <= 0 else f"❌ 差异 {orders_diff:+d}"
    orders_diff_str = f"{orders_diff:+d}"
    print(f"{'订单数':<15} {db_total_orders:<15} {api_total_orders:<15} {orders_diff_str:<15} {orders_status}")
    
    # 销售额对比（允许0.01的误差）
    gmv_diff = api_total_gmv - db_total_gmv
    gmv_status = "✅ 正常" if abs(gmv_diff) < 0.01 else f"❌ 差异 ${gmv_diff:+.2f}"
    gmv_diff_str = f"${gmv_diff:+.2f}"
    print(f"{'销售额':<15} ${db_total_gmv:<14} ${api_total_gmv:<14} {gmv_diff_str:<14} {gmv_status}")
    
    # 访客数对比（允许一定误差）
    visitors_diff = api_total_visitors - db_total_visitors
    visitors_status = "⚠️  有差异" if abs(visitors_diff) > 100 else "✅ 正常"
    visitors_diff_str = f"{visitors_diff:+d}"
    print(f"{'访客数':<15} {db_total_visitors:<15} {api_total_visitors:<15} {visitors_diff_str:<15} {visitors_status}")
    
    print()
    
    # 4. 各店铺订单数分布
    if api_store_orders:
        print("=" * 80)
        print("4. 各店铺订单数分布（API数据）")
        print("=" * 80)
        
        # 按订单数排序
        sorted_stores = sorted(api_store_orders.items(), key=lambda x: x[1], reverse=True)
        
        print(f"{'店铺域名':<45} {'订单数'}")
        print("-" * 80)
        for shop_domain, orders_count in sorted_stores:
            if orders_count > 0:
                print(f"{shop_domain:<45} {orders_count}")
        print("-" * 80)
        print(f"{'总计':<45} {api_total_orders}")
        print()
    
    # 5. 检查缺失的小时数据
    print("=" * 80)
    print("5. 检查缺失的小时数据")
    print("=" * 80)
    
    expected_hours = 24
    actual_hours = len(db_hourly_data)
    
    if actual_hours == expected_hours:
        print("✅ 所有小时的数据都已存在")
    else:
        missing_hours = []
        for hour in range(24):
            hour_time = target_start.replace(hour=hour)
            if hour_time not in db_hourly_data:
                missing_hours.append(hour)
        
        if missing_hours:
            print(f"❌ 缺失 {len(missing_hours)} 个小时的数据:")
            for hour in missing_hours:
                print(f"   {target_start.replace(hour=hour).strftime('%Y-%m-%d %H:00')}")
        else:
            print(f"⚠️  小时数据数量不一致（预期24小时，实际{actual_hours}小时）")
    
    print()
    
    # 6. 同步状态检查
    print("=" * 80)
    print("6. 同步状态检查")
    print("=" * 80)
    
    # 优先检查10分钟实时同步（当前使用的同步类型）
    status = db.get_sync_status('ten_minute_realtime')
    if not status:
        # 如果没有10分钟同步状态，检查5分钟同步状态（旧版本兼容）
        status = db.get_sync_status('five_minute_realtime')
    
    if status:
        last_sync_time = status['last_sync_end_time']
        if isinstance(last_sync_time, str):
            last_sync_time = datetime.strptime(last_sync_time, '%Y-%m-%d %H:%M:%S')
        
        last_sync_date = last_sync_time.date() if hasattr(last_sync_time, 'date') else last_sync_time
        sync_type = status.get('sync_type', 'unknown')
        
        print(f"同步类型：{sync_type}")
        print(f"最后同步时间：{last_sync_time}")
        if last_sync_date == target_date:
            print(f"✅ {target_date.strftime('%Y-%m-%d')} 数据已同步")
        elif last_sync_date < target_date:
            print(f"⚠️  最后同步日期早于目标日期，可能缺少数据")
        else:
            print(f"ℹ️  最后同步日期晚于目标日期")
    else:
        print("⚠️  没有同步状态记录")
    
    print()
    print("=" * 80)
    print("验证完成")
    print("=" * 80)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='验证指定日期的数据准确性')
    parser.add_argument('--date', type=str, help='要验证的日期，格式：YYYY-MM-DD（不指定则验证昨天）')
    args = parser.parse_args()
    
    try:
        verify_yesterday_data(args.date)
    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        import traceback
        print(f"\n错误: {e}")
        traceback.print_exc()

