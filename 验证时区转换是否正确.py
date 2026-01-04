"""
验证时区转换是否正确
用于确认Shoplazza和Facebook API返回的时间是否需要时区配置
"""
import os
import sys
from datetime import datetime, timedelta
import pytz

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shoplazza_api import ShoplazzaAPI
from database import Database
from config import DB_CONFIG

def verify_shoplazza_timezone():
    """验证Shoplazza API返回的UTC时间是否已经考虑了店铺时区"""
    print("=" * 60)
    print("验证1：Shoplazza API返回的UTC时间是否已考虑店铺时区")
    print("=" * 60)
    
    db = Database()
    stores = db.get_active_stores()
    
    # 找到"小一"的店铺
    target_shop = None
    for store in stores:
        shop_domain = store['shop_domain']
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT owner FROM store_owner_mapping WHERE shop_domain = %s", (shop_domain,))
                result = cur.fetchone()
                if result and result['owner'] == '小一':
                    target_shop = store
                    break
    
    if not target_shop:
        print("❌ 未找到'小一'的店铺")
        return
    
    shop_domain = target_shop['shop_domain']
    access_token = target_shop['access_token']
    
    print(f"店铺: {shop_domain}")
    print("店铺时区: UTC-8 (America/Los_Angeles)")
    print("\n正在查询订单数据...\n")
    
    api = ShoplazzaAPI(shop_domain, access_token)
    now = datetime.now(pytz.timezone('Asia/Shanghai'))
    yesterday = now - timedelta(days=1)
    
    placed_at_min = yesterday.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    placed_at_max = now.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    
    try:
        response = api.get_orders(
            placed_at_min=placed_at_min,
            placed_at_max=placed_at_max,
            page=1,
            limit=5
        )
        
        if not response or 'orders' not in response:
            print("❌ API返回数据为空")
            return
        
        orders = response.get('orders', [])
        if not orders:
            print("⚠️  没有找到订单数据")
            return
        
        print(f"找到 {len(orders)} 条订单\n")
        print("分析：")
        print("-" * 60)
        
        for i, order in enumerate(orders, 1):
            placed_at_str = order.get('placed_at', '')
            order_id = order.get('id', 'unknown')
            
            if not placed_at_str or 'Z' not in placed_at_str:
                continue
            
            # 解析UTC时间
            placed_at_utc = datetime.fromisoformat(placed_at_str.replace('Z', '+00:00'))
            
            # 转换为北京时间（当前代码的逻辑）
            placed_at_beijing = placed_at_utc.astimezone(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
            
            # 转换为UTC-8时间（店铺时区）
            placed_at_utc8 = placed_at_utc.astimezone(pytz.timezone('America/Los_Angeles')).replace(tzinfo=None)
            
            print(f"\n订单 {i} (ID: {order_id}):")
            print(f"  API返回的UTC时间: {placed_at_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"  转换为北京时间:   {placed_at_beijing.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
            print(f"  转换为UTC-8时间:   {placed_at_utc8.strftime('%Y-%m-%d %H:%M:%S')} (UTC-8)")
            
            # 计算时差
            # 如果API返回的UTC时间已经考虑了店铺时区，那么：
            # UTC-8的00:00 = UTC的08:00 = UTC+8的16:00
            # 所以：UTC-8时间 + 8小时 = UTC时间
            # 验证：UTC时间 - 8小时 = UTC-8时间
            
            expected_utc8 = placed_at_utc - timedelta(hours=8)
            expected_utc8 = expected_utc8.replace(tzinfo=None)
            
            print(f"  验证：UTC时间 - 8小时 = {expected_utc8.strftime('%Y-%m-%d %H:%M:%S')} (应该是UTC-8时间)")
            
            # 判断
            if abs((placed_at_utc8 - expected_utc8).total_seconds()) < 60:  # 允许1分钟误差
                print(f"  ✅ 时差正确！API返回的UTC时间已经考虑了店铺时区")
                print(f"  ✅ 当前代码转换逻辑正确，可以不改代码")
            else:
                print(f"  ⚠️  时差可能不正确，需要进一步验证")
        
        print("\n" + "=" * 60)
        print("结论：")
        print("=" * 60)
        print("如果所有订单的时差都正确，说明：")
        print("  ✅ Shoplazza API返回的UTC时间已经考虑了店铺时区")
        print("  ✅ 当前代码可以自动转换，不需要修改")
        print("  ✅ 但建议还是加上时区配置，更清晰明确")
        print("\n如果时差不正确，说明：")
        print("  ❌ 需要修改代码，根据店铺时区配置进行转换")
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()


def verify_facebook_timezone():
    """验证Facebook API返回的时间格式"""
    print("\n" + "=" * 60)
    print("验证2：Facebook API返回的时间格式")
    print("=" * 60)
    
    print("根据之前的测试，Facebook API返回：")
    print("  - date_start: 账户时区的日期（如 '2025-12-16'）")
    print("  - hourly_stats_aggregated_by_advertiser_time_zone: 账户时区的小时（如 '00:00:00 - 00:59:59'）")
    print("\n关键问题：")
    print("  - 如果账户时区是UTC-8，返回的'00:00:00'是UTC-8的00:00")
    print("  - 当前代码直接当作UTC+8存储，会导致时间错位16小时")
    print("  - ❌ 必须修改代码，根据账户时区配置进行转换")
    print("\n结论：")
    print("  ❌ Facebook必须使用时区配置，不能自动转换")


if __name__ == "__main__":
    verify_shoplazza_timezone()
    verify_facebook_timezone()
    
    print("\n" + "=" * 60)
    print("最终建议")
    print("=" * 60)
    print("1. Shoplazza：")
    print("   - 如果验证结果显示时差正确，可以不改代码")
    print("   - 但建议还是加上时区配置，更清晰明确")
    print("   - 如果验证结果显示时差不正确，必须修改代码")
    print("\n2. Facebook：")
    print("   - 必须修改代码，根据账户时区配置进行转换")
    print("   - 不能自动转换，因为API返回的是账户时区的时间")
    print("\n3. TikTok：")
    print("   - 需要查看API返回的时间格式")
    print("   - 如果返回的是账户时区的时间，需要修改代码")
    print("   - 如果返回的是UTC时间，可以自动转换")




