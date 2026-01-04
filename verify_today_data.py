"""
验证今天的数据是否准确
对比API返回的数据和数据库中的数据
"""
import sys
import io
from datetime import datetime, timedelta
from database import Database
from shoplazza_api import ShoplazzaAPI
from utils import beijing_time, datetime_to_iso8601, parse_iso8601

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

def verify_today_data():
    """验证今天的数据"""
    db = Database()
    
    # 获取今天的开始和结束时间
    now = beijing_time()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=now.hour, minute=now.minute, second=59, microsecond=999999)
    
    print("=" * 80)
    print(f"验证今天的数据准确性")
    print("=" * 80)
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"今天范围：{today_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {today_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"已过去时间：{now.hour}小时{now.minute}分钟")
    print()
    
    # 获取所有活跃店铺
    stores = db.get_active_stores()
    print(f"活跃店铺数量：{len(stores)}")
    print()
    
    # 1. 从数据库查询今天的数据
    print("=" * 80)
    print("1. 数据库中的数据（按小时聚合）")
    print("=" * 80)
    
    # 查询今天的数据
    db_data = db.get_hourly_data(
        start_time=today_start,
        end_time=today_end,
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
        print("⚠️  数据库中没有今天的数据！")
    
    print("-" * 80)
    print(f"{'总计':<20} {db_total_orders:<10} ${db_total_gmv:<14} {db_total_visitors:<10}")
    print()
    
    # 2. 从API查询今天的数据
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
                placed_at_min=datetime_to_iso8601(today_start),
                placed_at_max=datetime_to_iso8601(today_end)
            )
            
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
        begin_ts = int(today_start.timestamp())
        end_ts = int(today_end.timestamp())
        
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
                
                store_visitors = 0
                if analysis_data:
                    for item in analysis_data:
                        date_time_str = item.get('date_time', '')
                        uv = item.get('uv', 0)
                        
                        if date_time_str:
                            try:
                                item_dt = parse_iso8601(date_time_str)
                                if item_dt.date() == today_start.date():
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
        
        sorted_stores = sorted(api_store_orders.items(), key=lambda x: x[1], reverse=True)
        print(f"{'店铺域名':<40} {'订单数':<10}")
        print("-" * 80)
        
        for shop_domain, orders in sorted_stores:
            if orders > 0:
                print(f"{shop_domain:<40} {orders:<10}")
        
        print("-" * 80)
        print(f"{'总计':<40} {api_total_orders:<10}")
        print()
    
    # 5. 检查是否有缺失的小时数据
    print("=" * 80)
    print("5. 检查缺失的小时数据")
    print("=" * 80)
    
    expected_hours = []
    current_hour = today_start
    while current_hour <= now.replace(minute=0, second=0, microsecond=0):
        expected_hours.append(current_hour)
        current_hour += timedelta(hours=1)
    
    missing_hours = []
    for hour in expected_hours:
        if hour not in db_hourly_data:
            missing_hours.append(hour)
    
    if missing_hours:
        print(f"⚠️  发现 {len(missing_hours)} 个缺失的小时数据：")
        for hour in missing_hours:
            print(f"  - {hour.strftime('%Y-%m-%d %H:00')}")
    else:
        print("✅ 所有小时的数据都已存在")
    
    print()
    
    # 6. 检查同步状态
    print("=" * 80)
    print("6. 同步状态检查")
    print("=" * 80)
    
    # ⭐ 修复：使用新的同步类型 ten_minute_realtime（10分钟间隔）
    sync_status = db.get_sync_status('ten_minute_realtime')
    if sync_status:
        last_sync_time = sync_status['last_sync_end_time']
        sync_date = sync_status.get('sync_date')
        print(f"最后同步时间：{last_sync_time}")
        if sync_date:
            print(f"同步日期：{sync_date}")
        
        time_diff = now - last_sync_time
        if time_diff.total_seconds() > 600:  # 超过10分钟
            print(f"⚠️  警告：最后同步时间距现在已过去 {int(time_diff.total_seconds()/60)} 分钟")
            print(f"   如果超过10分钟，说明实时同步脚本可能没有正常运行")
        else:
            print(f"✅ 同步状态正常（{int(time_diff.total_seconds()/60)} 分钟前）")
    else:
        print("⚠️  未找到同步状态记录")
    
    print()
    print("=" * 80)
    print("验证完成")
    print("=" * 80)

if __name__ == '__main__':
    verify_today_data()

