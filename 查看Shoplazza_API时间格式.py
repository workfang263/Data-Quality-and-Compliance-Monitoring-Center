"""
查看 Shoplazza API 返回的 placed_at 字段格式
用于确认时间字符串是否包含时区信息
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

def check_placed_at_format():
    """检查 placed_at 字段格式"""
    
    # 方法1：从数据库查询已有的订单数据
    print("=" * 60)
    print("方法1：从数据库查询已有的订单数据")
    print("=" * 60)
    
    db = Database()
    stores = db.get_active_stores()
    
    if not stores:
        print("❌ 没有找到启用的店铺")
        return
    
    # 查询每个店铺的订单数据（如果有的话）
    # 注意：订单数据可能不在数据库中，因为代码是实时同步的
    # 所以我们需要用方法2：直接调用API
    
    print(f"\n找到 {len(stores)} 个启用的店铺")
    print("\n注意：订单数据可能不在数据库中（因为代码是实时同步的）")
    print("建议使用方法2：直接调用API查看\n")
    
    # 方法2：直接调用API
    print("=" * 60)
    print("方法2：直接调用API查看 placed_at 格式")
    print("=" * 60)
    
    # 选择一个店铺（建议选择"小一"的店铺）
    target_shop = None
    for store in stores:
        # 查找"小一"的店铺
        shop_domain = store['shop_domain']
        # 检查是否是"小一"的店铺
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT owner FROM store_owner_mapping WHERE shop_domain = %s", (shop_domain,))
                result = cur.fetchone()
                if result and result['owner'] == '小一':
                    target_shop = store
                    break
    
    if not target_shop:
        # 如果没有找到"小一"的店铺，使用第一个店铺
        target_shop = stores[0]
        print(f"⚠️  未找到'小一'的店铺，使用第一个店铺: {target_shop['shop_domain']}")
    else:
        print(f"✅ 找到'小一'的店铺: {target_shop['shop_domain']}")
    
    shop_domain = target_shop['shop_domain']
    access_token = target_shop['access_token']
    
    # 创建API对象
    api = ShoplazzaAPI(shop_domain, access_token)
    
    # 查询最近1天的订单（获取一些样本数据）
    now = datetime.now(pytz.timezone('Asia/Shanghai'))
    yesterday = now - timedelta(days=1)
    
    # 格式化时间为ISO 8601格式（北京时间）
    placed_at_min = yesterday.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    placed_at_max = now.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    
    print(f"\n查询时间范围：{placed_at_min} 到 {placed_at_max}")
    print("正在调用API...\n")
    
    try:
        # 调用API获取订单
        response = api.get_orders(
            placed_at_min=placed_at_min,
            placed_at_max=placed_at_max,
            page=1,
            limit=10  # 只获取10条，用于查看格式
        )
        
        if not response or 'orders' not in response:
            print("❌ API返回数据为空或格式不正确")
            print(f"响应内容: {response}")
            return
        
        orders = response.get('orders', [])
        
        if not orders:
            print("⚠️  没有找到订单数据")
            print("可能原因：")
            print("  1. 该时间段内没有订单")
            print("  2. 可以尝试扩大查询时间范围")
            return
        
        print(f"✅ 找到 {len(orders)} 条订单数据\n")
        print("=" * 60)
        print("placed_at 字段格式分析")
        print("=" * 60)
        
        # 分析每条订单的 placed_at 格式
        for i, order in enumerate(orders, 1):
            placed_at = order.get('placed_at', '')
            order_id = order.get('id', 'unknown')
            
            print(f"\n订单 {i} (ID: {order_id}):")
            print(f"  placed_at 原始值: {placed_at}")
            
            # 分析格式
            if not placed_at:
                print("  ⚠️  placed_at 字段为空")
                continue
            
            # 检查是否包含时区信息
            has_timezone = False
            timezone_info = None
            
            if 'Z' in placed_at:
                has_timezone = True
                timezone_info = 'Z (UTC)'
            elif '+00:00' in placed_at:
                has_timezone = True
                timezone_info = '+00:00 (UTC)'
            elif '+08:00' in placed_at:
                has_timezone = True
                timezone_info = '+08:00 (UTC+8)'
            elif '-08:00' in placed_at:
                has_timezone = True
                timezone_info = '-08:00 (UTC-8)'
            elif '+' in placed_at[-6:] or '-' in placed_at[-6:]:
                # 检查最后6个字符是否包含时区信息（如 +05:00, -05:00）
                timezone_part = placed_at[-6:]
                if ':' in timezone_part:
                    has_timezone = True
                    timezone_info = timezone_part
            
            if has_timezone:
                print(f"  ✅ 包含时区信息: {timezone_info}")
                print(f"  ✅ 代码可以自动识别并转换")
            else:
                print(f"  ❌ 不包含时区信息")
                print(f"  ⚠️  代码会假设是 UTC+8，可能导致错误")
                print(f"  ⚠️  需要修改代码，根据店铺时区配置进行转换")
        
        print("\n" + "=" * 60)
        print("总结")
        print("=" * 60)
        
        # 统计
        has_tz_count = sum(1 for o in orders if o.get('placed_at', '') and 
                          ('Z' in o.get('placed_at', '') or 
                           '+00:00' in o.get('placed_at', '') or 
                           '+08:00' in o.get('placed_at', '') or 
                           '-08:00' in o.get('placed_at', '') or
                           ('+' in o.get('placed_at', '')[-6:] or '-' in o.get('placed_at', '')[-6:])))
        
        no_tz_count = len(orders) - has_tz_count
        
        if has_tz_count > 0:
            print(f"✅ {has_tz_count} 条订单包含时区信息")
            print("   代码可以自动识别并转换，理论上不需要修改")
            print("   但建议还是修改代码，更清晰明确")
        
        if no_tz_count > 0:
            print(f"❌ {no_tz_count} 条订单不包含时区信息")
            print("   必须修改代码，根据店铺时区配置进行转换")
        
        if has_tz_count == len(orders):
            print("\n结论：所有订单都包含时区信息，代码可以自动识别")
            print("建议：可以不改代码，但建议还是改，更清晰")
        elif no_tz_count == len(orders):
            print("\n结论：所有订单都不包含时区信息，必须修改代码")
        else:
            print("\n结论：部分订单包含时区信息，部分不包含")
            print("建议：修改代码，统一处理")
        
    except Exception as e:
        print(f"❌ 调用API失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_placed_at_format()




