"""
数据同步脚本
每天凌晨3点自动执行，抓取昨天的数据
每10分钟执行一次，抓取今天的实时数据
"""
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
from collections import defaultdict
import concurrent.futures
from threading import Lock
import time

from database import Database
from shoplazza_api import ShoplazzaAPI
# 聚合
from aggregate_owner_daily import aggregate_date
from utils import (
    beijing_time, datetime_to_timestamp, datetime_to_iso8601,
    get_yesterday_range, setup_logging, parse_iso8601
)
from config import SYNC_CONFIG, LOG_CONFIG
import pytz
import msvcrt
import sys
import os

# 配置日志
setup_logging(LOG_CONFIG['log_file'], LOG_CONFIG['log_level'])
logger = logging.getLogger(__name__)

def acquire_lock():
    """
    获取进程锁（防止多个进程同时运行）
    
    Returns:
        file: 锁文件句柄（必须返回并保持打开状态，否则锁会失效）
    
    如果获取锁失败（另一个进程正在运行），直接退出程序
    """
    # 在脚本目录下创建锁文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lock_file_path = os.path.join(script_dir, "data_sync.lock")
    
    try:
        # 以追加模式打开（不破坏文件）
        lock_file = open(lock_file_path, 'a')
        
        # LK_NBLCK 是非阻塞锁：如果锁不住，立即抛出IOError而不是等待
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        
        # ⚠️ 重要：必须返回文件句柄，否则函数结束文件关闭，锁就失效了
        return lock_file
        
    except IOError:
        # 另一个进程正在运行，当前进程退出
        print("⚠️  检测到另一个进程正在同步中，当前进程自动退出。")
        logger.info("进程锁获取失败，另一个进程正在运行，退出")
        sys.exit(0)
    except Exception as e:
        # 其他异常（例如文件权限问题）
        logger.error(f"获取进程锁失败: {e}")
        print(f"❌ 获取进程锁失败: {e}")
        sys.exit(1)

def _is_gift_card_order(order: Dict[str, Any]) -> bool:
    """
    判断订单是否为礼品卡订单
    
    根据Shoplazza客服确认：数据概览不含销售礼品卡的订单
    
    Args:
        order: 订单对象
        
    Returns:
        True表示是礼品卡订单，False表示不是
    """
    # 方法1：检查订单项中是否全是礼品卡
    line_items = order.get('line_items', [])
    if line_items:
        # 如果所有商品都是礼品卡，则判定为礼品卡订单
        all_gift_cards = True
        for item in line_items:
            # 检查商品类型或SKU中是否包含gift card相关关键字
            product_type = str(item.get('product_type', '') or '').lower()
            sku = str(item.get('sku', '') or '').lower()
            title = str(item.get('title', '') or '').lower()
            
            # 判断是否包含礼品卡关键字
            is_gift_card = any(keyword in product_type or keyword in sku or keyword in title 
                             for keyword in ['gift card', 'giftcard', 'gift_card', '礼品卡'])
            
            if not is_gift_card:
                all_gift_cards = False
                break
        
        if all_gift_cards:
            return True
    
    # 方法2：检查订单是否有专门的礼品卡字段
    if order.get('gift_card') or order.get('giftcard') or order.get('gift_cards'):
        return True
    
    # 方法3：检查订单标题或备注
    order_name = str(order.get('name', '') or '').lower()
    if 'gift card' in order_name or 'giftcard' in order_name or '礼品卡' in order_name:
        return True
    
    return False


def _is_cod_order(order: Dict[str, Any]) -> bool:
    """
    判断订单是否为COD（货到付款）订单
    
    根据Shoplazza客服确认：数据概览去掉COD订单
    
    Args:
        order: 订单对象
        
    Returns:
        True表示是COD订单，False表示不是
    """
    # 方法1：检查支付方式
    payment_method = str(order.get('payment_method', '') or '').lower()
    if 'cod' in payment_method or 'cash_on_delivery' in payment_method or 'cash on delivery' in payment_method:
        return True
    
    # 方法2：检查支付网关名称
    payment_line = order.get('payment_line', {})
    if payment_line:
        payment_name = str(payment_line.get('payment_name', '') or '').lower()
        if 'cod' in payment_name or 'cash_on_delivery' in payment_name or 'cash on delivery' in payment_name:
            return True
    
    # 方法3：检查支付渠道
    payment_channel = str(payment_line.get('payment_channel', '') or '').lower() if payment_line else ''
    if 'cod' in payment_channel:
        return True
    
    # 方法4：检查订单备注或标签
    order_note = str(order.get('note', '') or '').lower()
    order_tags = str(order.get('tags', '') or '').lower()
    if 'cod' in order_note or 'cod' in order_tags or 'cash_on_delivery' in order_note or 'cash_on_delivery' in order_tags:
        return True
    
    return False


def _get_order_beijing_time(order: Dict[str, Any]) -> Optional[datetime]:
    """
    从订单对象中解析时间，并转换为北京时间（无时区）
    
    【测试要点】
    - 测试UTC时间（带Z）的解析和转换
    - 测试UTC时间（+00:00）的解析和转换
    - 测试北京时间（+08:00）的解析
    - 测试无时区信息的解析（使用parse_iso8601）
    - 测试缺失placed_at字段的情况（使用后备字段）
    - 测试返回类型是无时区的datetime（tzinfo=None）
    - 测试解析失败时返回None（不抛出异常）
    
    Args:
        order: 订单对象
        
    Returns:
        北京时间（datetime对象，无时区信息），如果解析失败返回None
        
    Raises:
        不抛出异常，解析失败时返回None并记录警告日志
        
    ⚠️ 重要说明：
        - 优先使用 placed_at（支付时间），这是最准确的时间
        - 如果 placed_at 缺失，使用 created_at 或 updated_at 作为后备（应对API抖动）
        - 如果使用了后备字段，会记录警告日志，便于监控数据质量
        - 这样既保证了数据准确性（优先使用支付时间），也保证了数据完整性（不会漏单）
    """
    order_id = order.get('id', 'unknown')
    
    # 优先使用 placed_at（支付时间，最准确）
    # 如果缺失，使用 created_at 或 updated_at 作为后备（应对API抖动、主从延迟等情况）
    time_str = order.get('placed_at', '') or order.get('created_at', '') or order.get('updated_at', '')
    
    # 记录使用了哪个字段（用于监控和调试）
    time_field_used = None
    if order.get('placed_at'):
        time_field_used = 'placed_at'
    elif order.get('created_at'):
        time_field_used = 'created_at'
    elif order.get('updated_at'):
        time_field_used = 'updated_at'
    
    # 如果所有时间字段都缺失，返回None
    if not time_str:
        logger.error(
            f"⚠️ 数据异常：订单所有时间字段都缺失！"
            f"订单ID={order_id}, "
            f"店铺={order.get('shop_domain', 'unknown')}, "
            f"请检查数据源！"
        )
        return None
    
    # 如果使用了后备字段，记录警告日志（不是错误，因为这是可接受的降级）
    if time_field_used != 'placed_at':
        logger.warning(
            f"⚠️ 订单使用了后备时间字段: 订单ID={order_id}, "
            f"使用字段={time_field_used}, "
            f"店铺={order.get('shop_domain', 'unknown')}, "
            f"placed_at={order.get('placed_at', 'N/A')}"
        )
    
    try:
        # 解析时间（优先使用placed_at，如果没有则使用created_at或updated_at）
        # 时间可能是ISO 8601格式（UTC或北京时间）
        # ⚠️ 重要：保持与现有逻辑完全一致，确保时区转换正确
        if 'Z' in time_str:
            # UTC时间，转换为北京时间
            order_dt_utc = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            order_dt = order_dt_utc.astimezone(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
        elif '+00:00' in time_str:
            # UTC时间
            order_dt_utc = datetime.fromisoformat(time_str)
            order_dt = order_dt_utc.astimezone(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
        elif '+08:00' in time_str:
            # 已经是北京时间
            order_dt = datetime.fromisoformat(time_str).replace(tzinfo=None)
        else:
            # 没有时区信息，使用parse_iso8601解析
            order_dt = parse_iso8601(time_str)
            # 转换为北京时间
            if order_dt.tzinfo is not None:
                order_dt = order_dt.astimezone(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
            else:
                # 假设是UTC时间，转换为北京时间
                order_dt = order_dt + timedelta(hours=8)
        
        # ⚠️ 关键：确保返回无时区的datetime，避免混合类型比较错误
        # 验证：确保tzinfo为None
        if order_dt.tzinfo is not None:
            logger.warning(f"警告：解析后的时间仍带时区信息，已移除: {time_str}")
            order_dt = order_dt.replace(tzinfo=None)
        
        return order_dt
        
    except Exception as e:
        # 解析失败，返回None并记录日志（不抛出异常）
        logger.warning(
            f"订单时间解析失败: 订单ID={order_id}, "
            f"时间字段={time_field_used}, "
            f"时间值={time_str}, "
            f"错误={e}"
        )
        return None


def sync_store_data(shop_domain: str, access_token: str, 
                   start_time: datetime, end_time: datetime,
                   target_date: datetime.date = None) -> Dict[str, Any]:
    """
    同步单个店铺的数据
    
    策略（方案A - 优先使用订单接口，更精准）：
    - 销售额：使用订单接口 total_price 累加（更精准，基于实际订单）
    - 订单数：使用订单接口订单条数（更精准，实际订单数量）
    - 访客数：使用数据分析接口 uv（只有这个接口有）
    - 同时记录数据分析接口的数据用于对比验证
    
    支付时间统计（新方案）：
    - 根据客服确认和官方文档：数据概览以订单成功支付的时间来统计
    - 官方文档确认：placed_at 字段就是"订单支付时间的时间戳"
    - 订单状态：opened → payment → placed（placed表示已完成付款订单）
    - API 支持按 placed_at 查询（placed_at_min/placed_at_max 参数）
    - 直接按支付时间精确查询，无需扩展查询窗口，与数据概览完全一致
    
    Args:
        shop_domain: 店铺域名
        access_token: 店铺访问令牌
        start_time: 查询起始时间（目标日期的开始时间）
        end_time: 查询结束时间（目标日期的结束时间）
        target_date: 目标统计日期（支付时间在这个日期的订单），如果为None则使用start_time的日期
    
    Returns:
        包含该店铺数据的字典
    """
    api = ShoplazzaAPI(shop_domain, access_token)
    db = Database()
    
    result = {
        'shop_domain': shop_domain,
        'success': False,
        'error': None,
        'data_count': 0
    }
    
    try:
        # 如果没有指定target_date，使用start_time的日期
        if target_date is None:
            target_date = start_time.date()
        
        # 转换为时间戳（用于数据分析接口）
        begin_ts = datetime_to_timestamp(start_time)
        end_ts = datetime_to_timestamp(end_time)
        
        # 使用 placed_at 参数查询订单（按支付时间查询，与数据概览一致）
        # 直接使用目标日期的时间范围，无需扩展查询窗口
        placed_at_min = datetime_to_iso8601(start_time)  # 目标日期 00:00:00
        placed_at_max = datetime_to_iso8601(end_time)    # 目标日期 23:59:59
        
        # 步骤1：调用数据分析接口获取访客数（按天去重，不过滤爬虫流量）
        # 注意：完全信任订单接口的销售额和订单数，不再使用分析接口的销售额和订单数
        logger.info(f"店铺 {shop_domain}: 获取访客数据（按天去重，不过滤爬虫）...")
        analysis_data_daily = api.get_data_analysis_all_pages(
            begin_ts, end_ts, 'dt_by_day',  # 使用天粒度获取按天去重的UV
            indicator=['uv']  # 只获取访客数
        )
        
        # 检查数据分析API是否失败（返回None表示API调用失败）
        analysis_api_failed = (analysis_data_daily is None)
        if analysis_api_failed:
            analysis_data_daily = []
        
        # 步骤2：调用订单接口获取订单数和销售额（唯一数据源，按支付时间查询，更精准）
        logger.info(f"店铺 {shop_domain}: 获取订单数据（主要数据源 - 按支付时间查询，placed_at_min={placed_at_min}, placed_at_max={placed_at_max}）...")
        orders_data = api.get_orders_all_pages(
            placed_at_min=placed_at_min,
            placed_at_max=placed_at_max
        )
        
        # 检查订单API是否失败（返回None表示API调用失败）
        orders_api_failed = (orders_data is None)
        if orders_api_failed:
            orders_data = []
        
        # 如果两个关键API都失败了，仅记录错误并跳过，不自动禁用店铺（由人工在后台决定是否禁用）
        if orders_api_failed and analysis_api_failed:
            fail_reason = f"订单API和数据分析API重试2次后均失败（日期：{target_date}）"
            logger.error(f"店铺 {shop_domain} API 均失败，本次跳过（未禁用店铺）: {fail_reason}")
            result['error'] = f"API调用失败，本次跳过: {fail_reason}"
            result['success'] = False
            return result
        elif orders_api_failed:
            # 只有订单API失败，访客数API成功，仍然记录警告但不禁用（因为访客数能获取到）
            logger.warning(f"⚠️  店铺 {shop_domain} 订单API调用失败（重试2次后），但数据分析API成功，继续处理")
        elif analysis_api_failed:
            # 只有数据分析API失败，订单API成功，仍然记录警告但不禁用（因为订单数据能获取到）
            logger.warning(f"⚠️  店铺 {shop_domain} 数据分析API调用失败（重试2次后），但订单API成功，继续处理（访客数将设为0）")
        
        # 按天获取访客数映射（天 -> 访客数）
        daily_visitors = {}
        if analysis_data_daily:
            for item in analysis_data_daily:
                date_time_str = item.get('date_time', '')
                uv = item.get('uv', 0)
                
                if not date_time_str:
                    continue
                
                try:
                    # 解析时间（天粒度）
                    if 'Z' in date_time_str:
                        dt_utc = datetime.fromisoformat(date_time_str.replace('Z', '+00:00'))
                        dt = dt_utc.astimezone(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
                    elif '+00:00' in date_time_str:
                        dt_utc = datetime.fromisoformat(date_time_str)
                        dt = dt_utc.astimezone(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
                    elif '+08:00' in date_time_str:
                        dt = datetime.fromisoformat(date_time_str).replace(tzinfo=None)
                    else:
                        dt_utc = datetime.fromisoformat(date_time_str)
                        dt = dt_utc + timedelta(hours=8)
                    
                    # 按天存储（使用日期作为key，不含时间）
                    day_key = dt.date()
                    daily_visitors[day_key] = uv
                except Exception as e:
                    logger.warning(f"解析天粒度访客数据失败: {e}")
                    continue
        
        # 按小时聚合数据（完全信任订单接口，不再使用分析接口的销售额和订单数）
        hourly_data = defaultdict(lambda: {
            'uv': 0,                    # 来自数据分析接口（按天去重，同一天所有小时使用相同值）
            'sales': 0.0,               # 来自订单接口total_price累加（唯一数据源）
            'orders': 0                 # 来自订单接口订单条数（唯一数据源）
        })
        
        # 处理订单数据（汇总每个订单的实际支付价格）
        # 重要：根据Shoplazza客服确认，数据概览以订单成功支付的时间来统计
        # 统计规则：
        # 根据Shoplazza客服确认的数据概览统计逻辑：
        # 1. 统计时间：使用 placed_at（订单支付时间）
        # 2. 订单范围：包含所有线上渠道（Mocart、Google、action等）
        # 3. 包含：已申请/申请中退款的订单（统计周期内成功支付的订单数量）
        # 4. 排除：销售礼品卡的订单、COD订单
        
        # 增强日志：记录订单处理状态
        processed_orders = 0
        skipped_orders = []
        
        if orders_data:
            for order in orders_data:
                order_id = order.get('id', 'unknown')
                # 过滤礼品卡订单：检查订单是否全是礼品卡
                if _is_gift_card_order(order):
                    skipped_orders.append({
                        'order_id': order_id,
                        'reason': '礼品卡订单'
                    })
                    logger.debug(f"跳过礼品卡订单: {order_id}, 店铺: {shop_domain}")
                    continue
                
                # 过滤COD订单：根据客服确认，数据概览去掉COD订单
                if _is_cod_order(order):
                    skipped_orders.append({
                        'order_id': order_id,
                        'reason': 'COD订单'
                    })
                    logger.debug(f"跳过COD订单: {order_id}, 店铺: {shop_domain}")
                    continue
                
                # 根据客服确认和官方文档：数据概览以订单成功支付的时间来统计
                # 官方文档明确说明：placed_at 字段就是"订单支付时间的时间戳"
                # （Timestamp indicating when the order was paid）
                # 
                # 因此：placed_at 就是支付时间，不是下单时间！
                # 订单状态流转：opened → payment → placed（placed表示已完成付款订单）
                
                # ✅ 使用公共函数解析订单时间（优先使用placed_at，如果没有则使用created_at或updated_at）
                order_dt = _get_order_beijing_time(order)
                if order_dt is None:
                    # 时间解析失败，跳过该订单
                    skipped_orders.append({
                        'order_id': order_id,
                        'reason': '时间解析失败'
                    })
                    logger.debug(f"订单时间解析失败，已跳过: {order_id}, 店铺: {shop_domain}")
                    continue
                
                # ⭐ 修复：过滤未来时间的订单（防止数据错误）
                # 获取当前北京时间
                current_time = beijing_time()
                if order_dt > current_time:
                    logger.warning(
                        f"跳过未来时间的订单: 订单ID={order_id}, "
                        f"订单时间={order_dt.strftime('%Y-%m-%d %H:%M:%S')}, "
                        f"当前时间={current_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                        f"店铺={shop_domain}"
                    )
                    skipped_orders.append({
                        'order_id': order_id,
                        'reason': f'未来时间订单（订单时间={order_dt.strftime("%Y-%m-%d %H:%M:%S")}）'
                    })
                    continue
                
                # API 已经按 placed_at（支付时间）筛选好了，返回的订单都在目标日期范围内
                # 无需再次按日期筛选，直接按小时聚合即可
                # 按小时聚合（使用placed_at的小时，即支付时间的小时）
                hour_key = order_dt.replace(minute=0, second=0, microsecond=0)
                
                # 先解析订单金额，确保订单数和销售额同步累加
                # 获取订单的实际支付价格（total_price字段）
                total_price_str = order.get('total_price') or order.get('total_price_set', {}).get('shop_money', {}).get('amount')
                
                # 如果金额字段完全缺失，记录详细错误并跳过
                if total_price_str is None:
                    order_id = order.get('id', 'unknown')
                    logger.warning(
                        f"订单金额字段缺失，订单已跳过 - "
                        f"店铺: {shop_domain}, "
                        f"目标日期: {target_date}, "
                        f"订单ID: {order_id}, "
                        f"placed_at: {order.get('placed_at', '')}, "
                        f"total_price: {order.get('total_price')}, "
                        f"total_price_set: {order.get('total_price_set')}"
                    )
                    skipped_orders.append({
                        'order_id': order_id,
                        'reason': '订单金额字段缺失'
                    })
                    continue
                
                try:
                    # 如果total_price是字符串，尝试解析
                    if isinstance(total_price_str, str):
                        # 移除可能的货币符号和空格
                        total_price_str = total_price_str.strip().replace('$', '').replace(',', '')
                        # 如果处理后的字符串为空，使用0
                        if not total_price_str:
                            total_price_str = '0'
                    
                    total_price = float(total_price_str)
                    
                    # 验证金额是否有效
                    if total_price < 0:
                        order_id = order.get('id', 'unknown')
                        logger.warning(
                            f"订单价格异常（负数）: {total_price}, "
                            f"店铺: {shop_domain}, "
                            f"目标日期: {target_date}, "
                            f"订单ID: {order_id}, "
                            f"原始值: {order.get('total_price')}"
                        )
                        # 负数价格也累加，但记录警告
                    
                    if total_price == 0:
                        order_id = order.get('id', 'unknown')
                        logger.warning(
                            f"订单价格为零，订单已记录但金额为0 - "
                            f"店铺: {shop_domain}, "
                            f"目标日期: {target_date}, "
                            f"订单ID: {order_id}"
                        )
                    
                    # 金额解析成功，同时累加订单数和销售额
                    hourly_data[hour_key]['orders'] += 1  # 订单数：主要数据源
                    hourly_data[hour_key]['sales'] += total_price  # 销售额：主要数据源
                    processed_orders += 1
                    
                except (ValueError, TypeError) as e:
                    # 价格解析失败，订单数和销售额都不累加，但记录详细错误信息
                    skipped_orders.append({
                        'order_id': order_id,
                        'placed_at': order.get('placed_at', ''),
                        'reason': f'价格解析失败: {str(e)}',
                        'total_price': order.get('total_price'),
                        'total_price_set': order.get('total_price_set')
                    })
                    logger.warning(
                        f"订单价格解析失败，订单已跳过 - "
                        f"店铺: {shop_domain}, "
                        f"目标日期: {target_date}, "
                        f"订单ID: {order_id}, "
                        f"placed_at: {order.get('placed_at', '')}, "
                        f"total_price原始值: {order.get('total_price')}, "
                        f"total_price_set: {order.get('total_price_set')}, "
                        f"错误: {e}"
                    )
                    continue
        
        # 将按天去重的访客数分配到对应日期的每个小时（在所有数据处理完成后）
        # 重要：即使没有订单，也要为有访客数据的日期创建24小时记录
        for day_key, uv_value in daily_visitors.items():
            # 为目标日期创建24小时的记录（即使没有订单）
            if day_key == target_date:
                for hour in range(24):
                    hour_key = datetime.combine(day_key, datetime.min.time()) + timedelta(hours=hour)
                    if hour_key not in hourly_data:
                        # 创建空记录（销售额和订单数为0，但有访客数）
                        hourly_data[hour_key] = {
                            'uv': 0,
                            'sales': 0.0,
                            'orders': 0
                        }
                    # 设置访客数（同一天所有小时使用相同的值）
                    hourly_data[hour_key]['uv'] = uv_value
        
        # 对于已经有数据的小时，也设置访客数
        for hour_key in hourly_data.keys():
            day_key = hour_key.date()
            if day_key in daily_visitors:
                # 同一天的所有小时使用相同的访客数（按天去重）
                hourly_data[hour_key]['uv'] = daily_visitors[day_key]
        
        # 记录访客数信息
        if daily_visitors:
            for day, uv in daily_visitors.items():
                logger.info(f"店铺 {shop_domain} {day} 按天去重访客数（不过滤爬虫）: {uv}")
        
        # 【方案2：添加聚合结果验证】
        # 验证聚合结果是否与API返回的数据一致
        if orders_data:
            # 计算API返回的有效订单总数和销售额
            api_valid_orders = [
                o for o in orders_data
                if not _is_gift_card_order(o) and not _is_cod_order(o)
            ]
            api_total_orders = len(api_valid_orders)
            api_total_sales = sum(float(o.get('total_price', 0)) for o in api_valid_orders)
            
            # 计算聚合后的订单总数和销售额
            aggregated_orders = sum(data['orders'] for data in hourly_data.values())
            aggregated_sales = sum(data['sales'] for data in hourly_data.values())
            
            # 对比验证
            orders_diff = api_total_orders - aggregated_orders
            sales_diff = api_total_sales - aggregated_sales
            
            if orders_diff != 0 or abs(sales_diff) >= 0.01:
                logger.error(
                    f"❌ 聚合结果验证失败: 店铺={shop_domain}, 日期={target_date}\n"
                    f"  API订单数={api_total_orders}, 聚合订单数={aggregated_orders}, 差异={orders_diff}\n"
                    f"  API销售额=${api_total_sales:.2f}, 聚合销售额=${aggregated_sales:.2f}, 差异=${sales_diff:.2f}\n"
                    f"  成功处理订单={processed_orders}, 跳过订单数={len(skipped_orders)}\n"
                    f"  请检查订单处理逻辑，可能存在订单被跳过的情况"
                )
                if skipped_orders:
                    logger.error(f"  跳过的订单详情: {skipped_orders}")
        
        # 记录订单处理统计信息
        total_api_orders = len([o for o in orders_data 
                                if not _is_gift_card_order(o) and not _is_cod_order(o)]) if orders_data else 0
        if processed_orders != total_api_orders:
            logger.error(
                f"❌ 订单处理数量不匹配: 店铺={shop_domain}, 日期={target_date}\n"
                f"  API有效订单数={total_api_orders}, 成功处理={processed_orders}, "
                f"跳过={len(skipped_orders)}\n"
                f"  跳过的订单详情: {skipped_orders}"
            )
        else:
            logger.info(
                f"✅ 订单处理完成: 店铺={shop_domain}, 日期={target_date}, "
                f"API有效订单={total_api_orders}, 成功处理={processed_orders}"
            )
        
        if skipped_orders:
            logger.warning(
                f"⚠️  店铺 {shop_domain} 跳过了 {len(skipped_orders)} 个订单:\n"
                f"  {skipped_orders}"
            )
        
        result['hourly_data'] = hourly_data
        result['data_count'] = len(hourly_data)
        result['success'] = True
        
        # 记录日志（完全信任订单接口，不再对比分析接口）
        total_orders = sum(data['orders'] for data in hourly_data.values())  # 订单接口
        total_sales = sum(data['sales'] for data in hourly_data.values())    # 订单接口
        # 访客数：由于是按天去重，同一天的所有小时使用相同值，所以取任意一小时的值即可（或使用daily_visitors汇总）
        total_uv = sum(daily_visitors.values()) if daily_visitors else 0     # 数据分析接口（按天去重）
        
        # 构建详细日志
        log_msg = (
            f"店铺 {shop_domain} 同步成功: {result['data_count']} 小时\n"
            f"  【订单接口】: {total_orders} 订单, ${total_sales:.2f} USD 销售额\n"
            f"  【访客数 - 分析接口（不过滤爬虫）】: {total_uv} 访客"
        )
        
        db.log_operation('data_sync', log_msg, shop_domain, 'success')
        
        # 保存统计数据到result中，用于后续验证
        result['total_orders'] = total_orders
        result['total_sales'] = total_sales
        result['total_visitors'] = total_uv
        
    except Exception as e:
        logger.error(f"同步店铺 {shop_domain} 数据失败: {e}")
        result['error'] = str(e)
        db.log_operation('data_sync', 
                        f"店铺 {shop_domain} 同步失败: {e}",
                        shop_domain, 'error')
    
    return result


def sync_all_stores(start_time: datetime = None, end_time: datetime = None, max_workers: int = 15):
    """
    同步所有店铺的数据（支持并行处理）
    
    新方案：使用 placed_at 参数按支付时间精确查询
    - API 支持按 placed_at（支付时间）查询，与数据概览完全一致
    - 无需扩展查询窗口，直接精确查询目标日期的支付时间范围
    - 数据更准确，性能更好
    
    Args:
        start_time: 起始时间（默认昨天开始，目标日期的 00:00:00）
        end_time: 结束时间（默认昨天结束，目标日期的 23:59:59）
        max_workers: 最大并发数（默认10，用于并行处理多个店铺）
    """
    if start_time is None or end_time is None:
        # 获取昨天的时间范围（作为目标日期）
        start_time, end_time, target_date = get_yesterday_range(extend_hours=0, return_target_date=True)
    else:
        target_date = start_time.date()
    
    logger.info(f"开始同步数据: 支付时间范围 {start_time} 至 {end_time} (目标统计日期: {target_date})")
    
    db = Database()
    stores = db.get_active_stores()
    
    if not stores:
        logger.warning("没有启用的店铺")
        return
    
    logger.info(f"找到 {len(stores)} 个启用店铺，使用 {max_workers} 个并发线程并行处理")
    
    # 按小时聚合所有店铺的数据（使用锁保证线程安全）
    all_hourly_data = defaultdict(lambda: {
        'total_gmv': 0.0,
        'total_orders': 0,
        'total_visitors': 0
    })
    # 维护每个店铺每天的UV值（用于正确累加访客数）
    daily_shop_visitors = defaultdict(lambda: defaultdict(int))  # {day: {shop_domain: uv}}
    data_lock = Lock()
    
    def sync_single_store(store):
        """同步单个店铺的数据"""
        shop_domain = store['shop_domain']
        access_token = store['access_token']
        
        logger.info(f"正在同步店铺: {shop_domain}")
        # 记录到数据库日志
        db.log_operation('sync', f"开始同步店铺: {shop_domain}, 目标日期: {target_date}", 
                        shop_domain=shop_domain, status='info')
        
        # 直接使用目标日期的时间范围（按支付时间查询，无需扩展窗口）
        result = sync_store_data(shop_domain, access_token, start_time, end_time, target_date)
        
        if result['success']:
            # 累加数据（使用锁保证线程安全）
            with data_lock:
                # 收集该店铺每天的UV值（取最大值，因为同一天所有小时可能不同）
                shop_daily_uv = {}  # {day: uv}
                for hour_key, data in result['hourly_data'].items():
                    day_key = hour_key.date()
                    if day_key not in shop_daily_uv:
                        shop_daily_uv[day_key] = 0
                    shop_daily_uv[day_key] = max(shop_daily_uv[day_key], data['uv'])
                
                # 累加销售额和订单数
                for hour_key, data in result['hourly_data'].items():
                    all_hourly_data[hour_key]['total_gmv'] += data['sales']
                    all_hourly_data[hour_key]['total_orders'] += data['orders']
                    # ❌ 不在这里累加访客数，因为UV是按天去重的
                
                # 存储该店铺每天的UV值
                for day_key, uv_value in shop_daily_uv.items():
                    daily_shop_visitors[day_key][shop_domain] = uv_value
            
            # 写入单店铺明细表（完全信任订单接口，对比字段传0）
            # 增强错误处理：检查每个写入操作的返回值
            write_failures = []
            for hour_key, data in result['hourly_data'].items():
                success = db.insert_or_update_store_hourly(
                    shop_domain=shop_domain,
                    time_hour=hour_key,
                    total_gmv=data['sales'],
                    total_orders=data['orders'],
                    total_visitors=data['uv'],
                    gmv_from_analysis=0.0,  # 不再使用分析接口的销售额
                    orders_from_analysis=0   # 不再使用分析接口的订单数
                )
                if not success:
                    write_failures.append({
                        'hour_key': hour_key,
                        'orders': data['orders'],
                        'sales': data['sales']
                    })
                    # 重试一次
                    time.sleep(0.5)  # 等待0.5秒后重试
                    retry_success = db.insert_or_update_store_hourly(
                        shop_domain=shop_domain,
                        time_hour=hour_key,
                        total_gmv=data['sales'],
                        total_orders=data['orders'],
                        total_visitors=data['uv'],
                        gmv_from_analysis=0.0,
                        orders_from_analysis=0
                    )
                    if not retry_success:
                        logger.error(
                            f"❌ 写入店铺 {shop_domain} 小时数据失败（重试后仍失败） - "
                            f"time_hour={hour_key.strftime('%Y-%m-%d %H:00')}, "
                            f"orders={data['orders']}, "
                            f"sales=${data['sales']:.2f}, "
                            f"target_date={target_date}"
                        )
                        write_failures[-1]['retry_failed'] = True
            
            if write_failures:
                logger.warning(
                    f"⚠️  店铺 {shop_domain} 有 {len(write_failures)} 条小时数据写入失败（已重试）"
                )
            
            # 记录成功日志
            order_count = result.get('total_orders', sum(data['orders'] for data in result['hourly_data'].values()))
            sales_sum = result.get('total_sales', sum(data['sales'] for data in result['hourly_data'].values()))
            db.log_operation('sync', 
                            f"店铺同步成功: 订单数={order_count}, 销售额=${sales_sum:.2f}", 
                            shop_domain=shop_domain, status='success')
            
            # 【方案3：添加同步后验证】
            # 验证数据完整性（严格验证，确保数据库数据与API数据一致）
            if target_date and order_count > 0:
                validation_result = validate_store_sync_result(
                    shop_domain, target_date,
                    order_count, sales_sum,
                    tolerance_orders=0,      # 不允许订单数差异
                    tolerance_sales=0.01     # 允许$0.01的销售额差异（浮点数精度问题）
                )
                
                if not validation_result:
                    logger.error(
                        f"❌ 同步后验证失败: 店铺={shop_domain}, 日期={target_date}\n"
                        f"  预期订单数={order_count}, 预期销售额=${sales_sum:.2f}\n"
                        f"  请检查数据库写入逻辑，可能存在数据写入失败或覆盖问题"
                    )
            
            # 返回成功结果
            return {
                'success': True, 
                'shop_domain': shop_domain,
                'total_orders': order_count,
                'total_sales': sales_sum
            }
        else:
            error_msg = result.get('error', '未知错误')
            logger.error(f"店铺 {shop_domain} 同步失败: {error_msg}")
            # 记录错误日志
            db.log_operation('error', f"店铺同步失败: {error_msg}", 
                            shop_domain=shop_domain, status='error')
            return {'success': False, 'shop_domain': shop_domain, 'error': error_msg}
    
    # 使用线程池并行处理所有店铺
    success_count = 0
    failed_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_store = {
            executor.submit(sync_single_store, store): store
            for store in stores
        }
        
        for future in concurrent.futures.as_completed(future_to_store):
            store = future_to_store[future]
            try:
                result = future.result()
                if result['success']:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"店铺 {store['shop_domain']} 处理异常: {e}")
                failed_count += 1
    
    logger.info(f"店铺同步完成: 成功 {success_count} 个, 失败 {failed_count} 个")
    
    # 计算每天的访客数：累加所有店铺当天的UV值
    # 因为UV是按天去重的，需要累加所有店铺的UV值，而不是累加小时值
    daily_visitor_sum = {}
    for day_key, shop_visitors in daily_shop_visitors.items():
        # 累加所有店铺当天的UV值
        daily_visitor_sum[day_key] = sum(shop_visitors.values())
    
    # 将每天的访客数应用到所有小时数据
    for hour_key in all_hourly_data.keys():
        day_key = hour_key.date()
        if day_key in daily_visitor_sum:
            all_hourly_data[hour_key]['total_visitors'] = daily_visitor_sum[day_key]
    
    # 写入数据库前，确保同一天所有小时的访客数都相同（按天取最大值，作为备用）
    # 因为访客数是按天去重的，同一天所有小时应该使用相同的值
    daily_visitor_max = {}
    for hour_key, data in all_hourly_data.items():
        day_key = hour_key.date()
        if day_key not in daily_visitor_max:
            daily_visitor_max[day_key] = 0
        daily_visitor_max[day_key] = max(daily_visitor_max[day_key], data['total_visitors'])
    
    # 补充缺失的小时数据：确保日期范围内的所有小时都有记录
    # 即使某个小时没有订单，也要创建记录（销售额和订单数为0）
    # 重要：只处理目标日期的数据，不要包含今天（即使查询窗口扩展到了今天）
    # timedelta已在文件顶部导入，不需要重复导入
    complete_hourly_data = {}
    current_date = start_time.date()
    # 只处理到目标日期（昨天），不包含今天
    end_date = target_date
    
    while current_date <= end_date:
        # 为每一天的24小时创建记录
        for hour in range(24):
            hour_key = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=hour)
            
            if hour_key in all_hourly_data:
                # 如果已有数据，使用现有数据
                complete_hourly_data[hour_key] = all_hourly_data[hour_key]
            else:
                # 如果没有数据，创建空记录（销售额和订单数为0，访客数使用当天的值）
                day_key = hour_key.date()
                corrected_visitors = daily_visitor_max.get(day_key, 0)
                complete_hourly_data[hour_key] = {
                    'total_gmv': 0.0,
                    'total_orders': 0,
                    'total_visitors': corrected_visitors
                }
        
        current_date += timedelta(days=1)
    
    # 写入数据库（使用完整的小时数据）
    # 重要：只写入目标日期的数据，不写入今天的数据
    success_count = 0
    for hour_key, data in complete_hourly_data.items():
        day_key = hour_key.date()
        # 只写入目标日期的数据，跳过今天的数据
        if day_key != target_date:
            continue
        
        # 使用当天的最大访客数（确保同一天所有小时都相同）
        corrected_visitors = daily_visitor_max.get(day_key, data['total_visitors'])
        avg_order_value = data['total_gmv'] / data['total_orders'] if data['total_orders'] > 0 else 0.0
        
        if db.insert_or_update_hourly_data(
            hour_key,
            data['total_gmv'],
            data['total_orders'],
            corrected_visitors,  # 使用修正后的访客数
            avg_order_value
        ):
            success_count += 1
    
    logger.info(f"数据同步完成，成功写入 {success_count} 条小时数据")
    
    # 记录总体同步结果到数据库
    total_gmv = sum(data['total_gmv'] for data in complete_hourly_data.values() 
                   if data['total_gmv'] > 0 and data['total_orders'] > 0)
    total_orders = sum(data['total_orders'] for data in complete_hourly_data.values())
    # 访客数：累加所有天的访客数（已经正确累加了所有店铺的UV值）
    total_visitors = sum(daily_visitor_sum.values()) if daily_visitor_sum else 0
    
    db.log_operation('sync', 
                    f"数据同步完成: 日期={target_date}, 写入记录数={success_count}, "
                    f"总订单数={total_orders}, 总销售额=${total_gmv:.2f}, 总访客数={total_visitors}", 
                    status='success')
    
    # 数据保留策略已移除：不再删除历史数据，可以保留任意月数的数据
    # db.cleanup_old_data(SYNC_CONFIG['data_retention_months'])  # 已禁用


def validate_store_sync_result(shop_domain: str, target_date: date, 
                                expected_orders: int, expected_sales: float,
                                tolerance_orders: int = 3, tolerance_sales: float = 10.0):
    """
    验证店铺同步结果的数据完整性
    
    Args:
        shop_domain: 店铺域名
        target_date: 目标日期
        expected_orders: 预期订单数（从API获取）
        expected_sales: 预期销售额（从API获取）
        tolerance_orders: 订单数差异容忍度（默认3单，因为可能存在API延迟）
        tolerance_sales: 销售额差异容忍度（默认$10，因为可能存在API延迟）
    
    Returns:
        bool: True表示验证通过，False表示验证失败
    """
    db = Database()
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = datetime.combine(target_date, datetime.max.time()).replace(microsecond=999999)
    
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        SUM(total_orders) as total_orders,
                        SUM(total_gmv) as total_gmv
                    FROM shoplazza_store_hourly
                    WHERE shop_domain = %s 
                      AND time_hour >= %s AND time_hour <= %s
                """
                cursor.execute(sql, (shop_domain, start_datetime, end_datetime))
                result = cursor.fetchone()
                
                if result:
                    db_orders = int(result['total_orders'] or 0)
                    db_sales = float(result['total_gmv'] or 0)
                    
                    orders_diff = expected_orders - db_orders
                    sales_diff = expected_sales - db_sales
                    
                    # 只有在差异超过容忍度时才报告
                    if abs(orders_diff) > tolerance_orders or abs(sales_diff) > tolerance_sales:
                        logger.warning(
                            f"⚠️  数据验证失败: 店铺={shop_domain}, "
                            f"日期={target_date}, "
                            f"API订单数={expected_orders}, 数据库订单数={db_orders}, 差异={orders_diff}, "
                            f"API销售额=${expected_sales:.2f}, 数据库销售额=${db_sales:.2f}, 差异=${sales_diff:.2f}"
                        )
                        return False
                    else:
                        logger.debug(
                            f"✅ 数据验证通过: 店铺={shop_domain}, "
                            f"日期={target_date}, "
                            f"订单数差异={orders_diff}, 销售额差异=${sales_diff:.2f}（在容忍范围内）"
                        )
                        return True
                else:
                    logger.warning(
                        f"⚠️  数据验证失败: 店铺={shop_domain}, "
                        f"日期={target_date}, 数据库中没有找到数据"
                    )
                    return False
    except Exception as e:
        logger.error(f"数据验证异常: 店铺={shop_domain}, 日期={target_date}, 错误={e}")
        return False


def sync_historical_data(months: int = 3, max_workers: int = 15):
    """
    回溯历史数据（首次运行使用，支持并行处理40+店铺）
    
    改进策略：排除最近1小时的数据，避免API数据延迟导致的问题
    
    Args:
        months: 回溯月数（默认3个月）
        max_workers: 最大并发数（默认10，用于并行处理多个店铺）
    """
    logger.info(f"=" * 60)
    logger.info(f"开始回溯 {months} 个月的历史数据")
    logger.info(f"使用 {max_workers} 个并发线程处理多个店铺")
    logger.info(f"=" * 60)
    
    now = beijing_time()
    # 改进：排除今天的数据，只同步到昨天，避免API数据延迟问题
    # 历史数据同步应该只同步已完成的数据，避免API延迟导致的缺失
    yesterday = (now - timedelta(days=1)).date()
    end_time = datetime.combine(yesterday, datetime.max.time()).replace(microsecond=999999)
    start_time = end_time - timedelta(days=months * 30)
    start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    
    logger.info(f"回溯时间范围: {start_time.date()} 至 {end_time.date()}")
    logger.info(f"注意：排除今天的数据（当前时间: {now}），避免API数据延迟导致的问题")
    
    # 按天分批同步，避免一次请求数据量过大
    current_start = start_time
    days_per_batch = 7  # 每次同步7天
    total_days = (end_time - start_time).days
    batch_count = (total_days + days_per_batch - 1) // days_per_batch
    
    batch_num = 0
    while current_start < end_time:
        batch_num += 1
        current_end = min(current_start + timedelta(days=days_per_batch), end_time)
        current_end = current_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        logger.info(f"[批次 {batch_num}/{batch_count}] 回溯数据: {current_start.date()} 至 {current_end.date()}")
        
        # 如果是跨天的情况，需要按天分别处理
        current_date = current_start.date()
        end_date = current_end.date()
        
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time()).replace(microsecond=999999)
            
            # 确保不超过end_time
            if day_end > end_time:
                day_end = end_time.replace(second=59, microsecond=999999)
            
            logger.info(f"  同步日期: {current_date}")
            sync_all_stores(day_start, day_end, max_workers=max_workers)
            
            current_date += timedelta(days=1)
        
        current_start = current_end + timedelta(seconds=1)
        current_start = current_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 每批次之间短暂休息，避免API限流
        if current_start < end_time:
            logger.info(f"批次 {batch_num} 完成，等待 5 秒后继续...")
            import time
            time.sleep(5)
    
    logger.info("=" * 60)
    logger.info("历史数据回溯完成！")
    logger.info("=" * 60)


def sync_store_data_for_ten_minutes(
    shop_domain: str, 
    access_token: str,
    start_time: datetime, 
    end_time: datetime
) -> Dict[str, Any]:
    """
    收集单个店铺在指定10分钟时间段内的数据
    
    Args:
        shop_domain: 店铺域名
        access_token: 访问令牌
        start_time: 开始时间（例如：00:00:00）
        end_time: 结束时间（例如：00:09:59）
    
    Returns:
        {
            'success': bool,
            'sales': float,      # 销售额
            'orders': int,       # 订单数
            'visitors': int,     # 访客数（当天累计，不过滤爬虫）
            'error': str
        }
    """
    # ⚠️ 关键防护：确保start_time和end_time都是无时区的datetime，避免混合类型比较错误
    # 即使调用方传入带时区的datetime，也能正常工作
    if start_time.tzinfo is not None:
        start_time = start_time.replace(tzinfo=None)
    if end_time.tzinfo is not None:
        end_time = end_time.replace(tzinfo=None)
    
    api = ShoplazzaAPI(shop_domain, access_token)
    
    result = {
        'success': False,
        'sales': 0.0,
        'orders': 0,
        'visitors': 0,
        'error': None
    }
    
    try:
        # 1. 收集订单数据（按支付时间查询）
        placed_at_min = datetime_to_iso8601(start_time)
        placed_at_max = datetime_to_iso8601(end_time)
        
        orders_data = api.get_orders_all_pages(
            placed_at_min=placed_at_min,
            placed_at_max=placed_at_max
        )
        
        # 检查订单API是否失败（返回None表示API调用失败）
        orders_api_failed = (orders_data is None)
        
        # 如果订单API失败，设置为空列表以便后续处理
        if orders_api_failed:
            orders_data = []
        
        # 统计订单数和销售额（使用与历史同步完全相同的逻辑）
        processed_orders = 0
        skipped_orders = []
        # ✅ 新增：初始化跳过订单记录（用于输出到文件，用于数据审计）
        skipped_orders_for_file = []
        
        if orders_data:
            for order in orders_data:
                order_id = order.get('id', 'unknown')
                
                # ✅ 新增：解析订单时间（使用公共函数）
                order_dt = _get_order_beijing_time(order)
                if order_dt is None:
                    skip_info = {
                        'order_id': order_id,
                        'shop_domain': shop_domain,
                        'reason': '时间解析失败',
                        'placed_at': order.get('placed_at', ''),
                        'order_time': None,
                        'time_range': f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}, {end_time.strftime('%Y-%m-%d %H:%M:%S')})"
                    }
                    skipped_orders.append(skip_info)
                    skipped_orders_for_file.append(skip_info)
                    logger.debug(f"订单时间解析失败，已跳过: {order_id}, 店铺: {shop_domain}")
                    continue
                
                # ✅ 新增：核心防御 - 只处理当前10分钟窗口内的数据
                # 使用左闭右开区间 [start_time, end_time)
                # ⚠️ 重要：确保start_time、end_time、order_dt都是无时区的datetime，避免TypeError
                if not (start_time <= order_dt < end_time):
                    skip_info = {
                        'order_id': order_id,
                        'shop_domain': shop_domain,
                        'reason': '订单时间不在范围内',
                        'placed_at': order.get('placed_at', ''),
                        'order_time': order_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'time_range': f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}, {end_time.strftime('%Y-%m-%d %H:%M:%S')})"
                    }
                    skipped_orders.append(skip_info)
                    skipped_orders_for_file.append(skip_info)
                    logger.debug(
                        f"订单时间不在范围内，已跳过: {order_id}, "
                        f"订单时间={order_dt.strftime('%Y-%m-%d %H:%M:%S')}, "
                        f"范围=[{start_time.strftime('%Y-%m-%d %H:%M:%S')}, {end_time.strftime('%Y-%m-%d %H:%M:%S')}), "
                        f"店铺: {shop_domain}"
                    )
                    continue
                
                # ✅ 新增：过滤未来时间的订单（防止数据错误）
                current_time = beijing_time()  # 返回无时区的datetime
                if order_dt > current_time:
                    skip_info = {
                        'order_id': order_id,
                        'shop_domain': shop_domain,
                        'reason': '未来时间订单',
                        'placed_at': order.get('placed_at', ''),
                        'order_time': order_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'time_range': f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}, {end_time.strftime('%Y-%m-%d %H:%M:%S')})"
                    }
                    skipped_orders.append(skip_info)
                    skipped_orders_for_file.append(skip_info)
                    logger.warning(
                        f"跳过未来时间的订单: 订单ID={order_id}, "
                        f"订单时间={order_dt.strftime('%Y-%m-%d %H:%M:%S')}, "
                        f"当前时间={current_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                        f"店铺={shop_domain}"
                    )
                    continue
                
                # 过滤礼品卡订单（与历史同步一致）
                if _is_gift_card_order(order):
                    skip_info = {
                        'order_id': order_id,
                        'shop_domain': shop_domain,
                        'reason': '礼品卡订单',
                        'placed_at': order.get('placed_at', ''),
                        'order_time': order_dt.strftime('%Y-%m-%d %H:%M:%S') if order_dt else None,
                        'time_range': f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}, {end_time.strftime('%Y-%m-%d %H:%M:%S')})"
                    }
                    skipped_orders.append(skip_info)
                    skipped_orders_for_file.append(skip_info)
                    logger.debug(f"跳过礼品卡订单: {order_id}, 店铺: {shop_domain}")
                    continue
                
                # 过滤COD订单（与历史同步一致）
                if _is_cod_order(order):
                    skip_info = {
                        'order_id': order_id,
                        'shop_domain': shop_domain,
                        'reason': 'COD订单',
                        'placed_at': order.get('placed_at', ''),
                        'order_time': order_dt.strftime('%Y-%m-%d %H:%M:%S') if order_dt else None,
                        'time_range': f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}, {end_time.strftime('%Y-%m-%d %H:%M:%S')})"
                    }
                    skipped_orders.append(skip_info)
                    skipped_orders_for_file.append(skip_info)
                    logger.debug(f"跳过COD订单: {order_id}, 店铺: {shop_domain}")
                    continue
                
                # 获取订单的实际支付价格（与历史同步一致）
                total_price_str = order.get('total_price') or order.get('total_price_set', {}).get('shop_money', {}).get('amount')
                
                # 如果金额字段完全缺失，记录详细错误并跳过（与历史同步一致）
                if total_price_str is None:
                    skip_info = {
                        'order_id': order_id,
                        'shop_domain': shop_domain,
                        'reason': '金额字段缺失',
                        'placed_at': order.get('placed_at', ''),
                        'order_time': order_dt.strftime('%Y-%m-%d %H:%M:%S') if order_dt else None,
                        'time_range': f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}, {end_time.strftime('%Y-%m-%d %H:%M:%S')})"
                    }
                    logger.warning(
                        f"订单金额字段缺失，订单已跳过 - "
                        f"店铺: {shop_domain}, "
                        f"订单ID: {order_id}, "
                        f"placed_at: {order.get('placed_at', '')}, "
                        f"total_price: {order.get('total_price')}, "
                        f"total_price_set: {order.get('total_price_set')}"
                    )
                    skipped_orders.append(skip_info)
                    skipped_orders_for_file.append(skip_info)
                    continue
                
                try:
                    # 价格解析逻辑（与历史同步完全一致）
                    if isinstance(total_price_str, str):
                        # 移除可能的货币符号和空格
                        total_price_str = total_price_str.strip().replace('$', '').replace(',', '')
                        # 如果处理后的字符串为空，使用0
                        if not total_price_str:
                            total_price_str = '0'
                    
                    total_price = float(total_price_str)
                    
                    # 验证金额是否有效（与历史同步一致）
                    if total_price < 0:
                        logger.warning(
                            f"订单价格异常（负数）: {total_price}, "
                            f"店铺: {shop_domain}, "
                            f"订单ID: {order_id}, "
                            f"原始值: {order.get('total_price')}"
                        )
                        # 负数价格也累加，但记录警告（与历史同步一致）
                    
                    if total_price == 0:
                        logger.warning(
                            f"订单价格为零，订单已记录但金额为0 - "
                            f"店铺: {shop_domain}, "
                            f"订单ID: {order_id}"
                        )
                    
                    # 金额解析成功，同时累加订单数和销售额（与历史同步一致）
                    result['orders'] += 1
                    result['sales'] += total_price
                    processed_orders += 1
                    
                except (ValueError, TypeError) as e:
                    # 价格解析失败，订单数和销售额都不累加（与历史同步一致）
                    skip_info = {
                        'order_id': order_id,
                        'shop_domain': shop_domain,
                        'reason': f'价格解析失败: {str(e)}',
                        'placed_at': order.get('placed_at', ''),
                        'order_time': order_dt.strftime('%Y-%m-%d %H:%M:%S') if order_dt else None,
                        'time_range': f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}, {end_time.strftime('%Y-%m-%d %H:%M:%S')})",
                        'total_price': str(order.get('total_price', '')),
                        'total_price_set': str(order.get('total_price_set', ''))
                    }
                    skipped_orders.append(skip_info)
                    skipped_orders_for_file.append(skip_info)
                    logger.warning(
                        f"订单价格解析失败，订单已跳过 - "
                        f"店铺: {shop_domain}, "
                        f"订单ID: {order_id}, "
                        f"placed_at: {order.get('placed_at', '')}, "
                        f"total_price原始值: {order.get('total_price')}, "
                        f"total_price_set: {order.get('total_price_set')}, "
                        f"错误: {e}"
                    )
                    continue
        
        # 记录订单处理统计（与历史同步一致）
        if skipped_orders:
            logger.warning(
                f"⚠️  店铺 {shop_domain} 跳过了 {len(skipped_orders)} 个订单: {skipped_orders}"
            )
        
        # 2. 收集访客数（不过滤爬虫流量，按天去重）
        # 查询当天00:00:00到end_time的数据，获取当天的累计访客数
        today_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        begin_ts = datetime_to_timestamp(today_start)
        end_ts = datetime_to_timestamp(end_time)
        
        # 使用天粒度查询（dt_by_day），获取按天去重的访客数
        analysis_data = api.get_data_analysis_all_pages(
            begin_ts, end_ts, 'dt_by_day',
            indicator=['uv'],
            filter_crawler_type=''  # 不过滤爬虫流量（空字符串）
        )
        
        # 检查数据分析API是否失败（返回None表示API调用失败）
        analysis_api_failed = (analysis_data is None)
        
        # 如果两个关键API都失败了，仅记录错误并跳过，不自动禁用店铺（由人工在后台决定是否禁用）
        if orders_api_failed and analysis_api_failed:
            fail_reason = f"订单API和数据分析API重试2次后均失败（时间段：{start_time} - {end_time}）"
            logger.error(f"店铺 {shop_domain} API 均失败，本次跳过（未禁用店铺）: {fail_reason}")
            result['error'] = f"API调用失败，本次跳过: {fail_reason}"
            result['success'] = False
            return result
        elif orders_api_failed:
            # 只有订单API失败，访客数API成功，仍然记录警告但不禁用（因为访客数能获取到）
            logger.warning(f"⚠️  店铺 {shop_domain} 订单API调用失败（重试2次后），但数据分析API成功，继续处理")
            # 将orders_data设置为空列表，继续处理
            orders_data = []
        elif analysis_api_failed:
            # 只有数据分析API失败，订单API成功，仍然记录警告但不禁用（因为订单数据能获取到）
            logger.warning(f"⚠️  店铺 {shop_domain} 数据分析API调用失败（重试2次后），但订单API成功，继续处理（访客数将设为0）")
            # 将analysis_data设置为空列表，继续处理
            analysis_data = []
        
        if analysis_data:
            # 查找当天的访客数（使用与历史同步完全相同的解析逻辑）
            today = start_time.date()
            for item in analysis_data:
                date_time_str = item.get('date_time', '')
                uv = item.get('uv', 0)
                
                if not date_time_str:
                    continue
                
                try:
                    # 使用与历史同步完全相同的时间解析逻辑
                    if 'Z' in date_time_str:
                        dt_utc = datetime.fromisoformat(date_time_str.replace('Z', '+00:00'))
                        dt = dt_utc.astimezone(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
                    elif '+00:00' in date_time_str:
                        dt_utc = datetime.fromisoformat(date_time_str)
                        dt = dt_utc.astimezone(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
                    elif '+08:00' in date_time_str:
                        dt = datetime.fromisoformat(date_time_str).replace(tzinfo=None)
                    else:
                        dt_utc = datetime.fromisoformat(date_time_str)
                        dt = dt_utc + timedelta(hours=8)
                    
                    # 按天存储（使用日期作为key，不含时间）
                    item_date = dt.date()
                    if item_date == today:
                        # 处理UV数据（与历史同步一致）
                        if isinstance(uv, dict):
                            result['visitors'] = int(uv.get('value', 0))
                        elif isinstance(uv, (int, float)):
                            result['visitors'] = int(uv)
                        break
                except Exception as e:
                    logger.warning(f"店铺 {shop_domain} 解析访客数日期失败: {e}")
                    continue
        
        # ✅ 新增：将跳过的订单记录到文件（用于数据审计和问题排查）
        # 使用追加模式，按天生成文件，避免产生大量文件
        if skipped_orders_for_file:
            import csv
            import os
            
            # 创建logs目录（如果不存在）
            logs_dir = 'logs'
            os.makedirs(logs_dir, exist_ok=True)
            
            # 生成文件名：skipped_orders_YYYYMMDD.csv（按天生成，追加模式）
            today_str = start_time.strftime('%Y%m%d')
            filename = os.path.join(logs_dir, f'skipped_orders_{today_str}.csv')
            
            # 写入CSV文件（追加模式）
            file_exists = os.path.exists(filename)
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                fieldnames = ['order_id', 'shop_domain', 'reason', 'placed_at', 'order_time', 'time_range', 'current_time', 'total_price', 'total_price_set']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # 如果文件不存在，写入表头
                if not file_exists:
                    writer.writeheader()
                
                # 写入跳过的订单数据
                writer.writerows(skipped_orders_for_file)
            
            logger.info(f"已记录 {len(skipped_orders_for_file)} 个跳过订单到文件: {filename}")
        
        result['success'] = True
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"店铺 {shop_domain} 收集10分钟数据失败: {e}")
    
    return result


def sync_yesterday_final_data():
    """
    在00:00:00执行时，收集昨天的最终数据（覆盖模式）
    
    逻辑（与 fill_today_data.py 一致）：
    1. 清空昨天的数据（避免重复累加）
    2. 按10分钟段收集昨天00:00:00-23:59:59的全部数据（144个段）
    3. 按小时汇总数据
    4. 使用覆盖模式写入（insert_or_update_hourly_data 和 insert_or_update_store_hourly）
    5. 更新sync_status：标记昨天数据已完成
    """
    db = Database()
    now = beijing_time()
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday_start.replace(hour=23, minute=59, second=59, microsecond=0)
    
    logger.info("=" * 80)
    logger.info(f"检测到00:00:00执行，开始收集昨天 {yesterday_start.date()} 的最终数据（覆盖模式）...")
    logger.info("=" * 80)
    logger.info(f"昨天范围：{yesterday_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {yesterday_end.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # 获取所有启用的店铺
    stores = db.get_active_stores()
    if not stores:
        logger.warning("没有启用的店铺，跳过同步")
        return
    
    logger.info(f"活跃店铺数量：{len(stores)}")
    logger.info("")
    
    # 1. 清空昨天的数据（避免重复累加）
    logger.info("=" * 80)
    logger.info("步骤1：清空昨天的数据（避免重复累加）")
    logger.info("=" * 80)
    
    delete_sql = """
        DELETE FROM shoplazza_overview_hourly
        WHERE DATE(time_hour) = DATE(%s)
    """
    delete_store_sql = """
        DELETE FROM shoplazza_store_hourly
        WHERE DATE(time_hour) = DATE(%s)
    """
    
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # 先查询有多少条数据
                count_sql = """
                    SELECT COUNT(*) as count FROM shoplazza_overview_hourly
                    WHERE DATE(time_hour) = DATE(%s)
                """
                cursor.execute(count_sql, (yesterday_start,))
                count_result = cursor.fetchone()
                old_count = count_result['count'] if count_result else 0
                
                # 删除总店铺数据
                cursor.execute(delete_sql, (yesterday_start,))
                deleted_overview = cursor.rowcount
                
                # 删除单店铺数据
                cursor.execute(delete_store_sql, (yesterday_start,))
                deleted_store = cursor.rowcount
                
                conn.commit()
                logger.info(f"已删除总店铺数据：{deleted_overview} 条")
                logger.info(f"已删除单店铺数据：{deleted_store} 条")
                logger.info("")
    except Exception as e:
        logger.error(f"清空昨天的数据失败: {e}")
        logger.warning("继续执行收集，但可能存在重复累加问题")
        logger.info("")
    
    # 2. 计算昨天所有10分钟段（00:00:00-23:59:59，共144个段）
    segments = []
    current_segment_start = yesterday_start
    
    while current_segment_start <= yesterday_end:
        current_segment_end = current_segment_start + timedelta(minutes=10) - timedelta(microseconds=1)
        if current_segment_end > yesterday_end:
            current_segment_end = yesterday_end
        segments.append((current_segment_start, current_segment_end))
        current_segment_start = current_segment_start + timedelta(minutes=10)
    
    logger.info(f"需要收集的时间段数量：{len(segments)}")
    logger.info(f"时间段范围：{segments[0][0].strftime('%H:%M:%S')} - {segments[-1][1].strftime('%H:%M:%S')}")
    logger.info("")
    
    if not segments:
        logger.warning("没有需要收集的数据")
        return
    
    # 并行处理配置
    PARALLEL_SEGMENTS = 8  # 同时处理8个时间段
    
    logger.info(f"并行处理配置：同时处理 {PARALLEL_SEGMENTS} 个时间段")
    logger.info(f"每个时间段内：{len(stores)}个店铺并行处理（10个线程）")
    logger.info("")
    total_segments = len(segments)
    
    def process_segment(segment_idx, start_time, end_time):
        """处理单个时间段的数据（与 fill_today_data.py 的 process_segment 逻辑一致）"""
        segment_data = {
            'idx': segment_idx,
            'start_time': start_time,
            'end_time': end_time,
            'hourly_data': {},  # 总店铺数据（按小时汇总）
            'store_hourly_data': {},  # 单店铺数据 {shop_domain: {hour_start: {sales, orders, visitors}}}
            'success': True,
            'error': None
        }
        
        try:
            # 并行收集所有店铺的数据
            all_store_data = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_store = {
                    executor.submit(sync_store_data_for_ten_minutes,
                                  store['shop_domain'], store['access_token'],
                                  start_time, end_time): store
                    for store in stores
                }
                
                for future in concurrent.futures.as_completed(future_to_store):
                    store = future_to_store[future]
                    try:
                        result = future.result()
                        all_store_data[store['shop_domain']] = result
                    except Exception as e:
                        logger.error(f"店铺 {store['shop_domain']} 数据收集异常: {e}")
                        all_store_data[store['shop_domain']] = {
                            'success': False,
                            'sales': 0.0,
                            'orders': 0,
                            'visitors': 0,
                            'error': str(e)
                        }
            
            # 按小时汇总数据（总店铺和单店铺）
            hour_start = start_time.replace(minute=0, second=0, microsecond=0)
            
            # 初始化小时数据
            if hour_start not in segment_data['hourly_data']:
                segment_data['hourly_data'][hour_start] = {
                    'sales': 0.0,
                    'orders': 0,
                    'visitors': 0,
                    'shop_visitors': {}  # 用于存储每个店铺的访客数，避免重复累加
                }
            
            for shop_domain, result in all_store_data.items():
                if result['success']:
                    # 总店铺数据累加
                    segment_data['hourly_data'][hour_start]['sales'] += result['sales']
                    segment_data['hourly_data'][hour_start]['orders'] += result['orders']
                    # 访客数：每个店铺的访客数是当天累计值，取每个店铺的最大值，然后所有店铺累加
                    # 因为不同店铺的访客是不同的IP，应该累加
                    if shop_domain not in segment_data['hourly_data'][hour_start]['shop_visitors']:
                        segment_data['hourly_data'][hour_start]['shop_visitors'][shop_domain] = 0
                    # 取每个店铺的最大值（因为按天去重，同一店铺在不同时间段查询可能值不同）
                    segment_data['hourly_data'][hour_start]['shop_visitors'][shop_domain] = max(
                        segment_data['hourly_data'][hour_start]['shop_visitors'][shop_domain],
                        result['visitors']
                    )
                    
                    # 单店铺数据保存
                    if shop_domain not in segment_data['store_hourly_data']:
                        segment_data['store_hourly_data'][shop_domain] = {}
                    if hour_start not in segment_data['store_hourly_data'][shop_domain]:
                        segment_data['store_hourly_data'][shop_domain][hour_start] = {
                            'sales': 0.0,
                            'orders': 0,
                            'visitors': 0
                        }
                    
                    # 累加单店铺数据（同一小时的多个10分钟段会累加）
                    segment_data['store_hourly_data'][shop_domain][hour_start]['sales'] += result['sales']
                    segment_data['store_hourly_data'][shop_domain][hour_start]['orders'] += result['orders']
                    # 访客数取最大值（因为按天去重）
                    segment_data['store_hourly_data'][shop_domain][hour_start]['visitors'] = max(
                        segment_data['store_hourly_data'][shop_domain][hour_start]['visitors'],
                        result['visitors']
                    )
        except Exception as e:
            segment_data['success'] = False
            segment_data['error'] = str(e)
            logger.error(f"处理时间段 {start_time} - {end_time} 失败: {e}")
        
        return segment_data
    
    # 3. 收集所有时间段的数据（分批并行处理）
    all_results = []
    segment_idx = 0
    
    logger.info("=" * 80)
    logger.info("步骤2：收集所有时间段的数据")
    logger.info("=" * 80)
    
    while segment_idx < total_segments:
        # 获取当前批次的时间段（最多PARALLEL_SEGMENTS个）
        batch_segments = segments[segment_idx:segment_idx + PARALLEL_SEGMENTS]
        batch_size = len(batch_segments)
        
        logger.info(f"正在并行处理 {batch_size} 个时间段: [{segment_idx+1}-{segment_idx+batch_size}]/{total_segments}")
        
        # 并行处理当前批次的所有时间段
        batch_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_SEGMENTS) as executor:
            future_to_segment = {
                executor.submit(process_segment, segment_idx + i, start_time, end_time): (start_time, end_time)
                for i, (start_time, end_time) in enumerate(batch_segments)
            }
            
            for future in concurrent.futures.as_completed(future_to_segment):
                start_time, end_time = future_to_segment[future]
                try:
                    result = future.result()
                    batch_results.append(result)
                except Exception as e:
                    logger.error(f"时间段 {start_time} - {end_time} 处理异常: {e}")
                    batch_results.append({
                        'idx': segment_idx + batch_segments.index((start_time, end_time)),
                        'start_time': start_time,
                        'end_time': end_time,
                        'hourly_data': {},
                        'success': False,
                        'error': str(e)
                    })
        
        # 收集所有批次的结果
        all_results.extend(batch_results)
        
        segment_idx += batch_size
        
        # 显示进度
        progress = (segment_idx * 100) // total_segments
        logger.info(f"  进度: {segment_idx}/{total_segments} ({progress}%)")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("步骤3：按小时汇总所有数据并写入数据库")
    logger.info("=" * 80)
    
    # 按索引排序，确保顺序
    all_results.sort(key=lambda x: x['idx'])
    
    # 汇总所有时间段的小时数据（累加同一小时的所有10分钟段）
    all_hourly_data = {}  # 总店铺数据
    all_store_hourly_data = {}  # 单店铺数据 {shop_domain: {hour_start: {sales, orders, visitors}}}
    all_hourly_shop_visitors = {}  # 每个小时每个店铺的访客数 {hour_start: {shop_domain: max_visitors}}
    failed_segments = []
    
    for result in all_results:
        if result['success']:
            # 汇总总店铺数据
            for hour_start, data in result['hourly_data'].items():
                if hour_start not in all_hourly_data:
                    all_hourly_data[hour_start] = {
                        'sales': 0.0,
                        'orders': 0,
                        'visitors': 0
                    }
                    all_hourly_shop_visitors[hour_start] = {}
                
                # 累加同一小时的所有10分钟段
                all_hourly_data[hour_start]['sales'] += data['sales']
                all_hourly_data[hour_start]['orders'] += data['orders']
                
                # 访客数：取每个店铺的最大值（因为按天去重），然后所有店铺累加
                shop_visitors = data.get('shop_visitors', {})
                for shop_domain, visitors in shop_visitors.items():
                    if shop_domain not in all_hourly_shop_visitors[hour_start]:
                        all_hourly_shop_visitors[hour_start][shop_domain] = 0
                    all_hourly_shop_visitors[hour_start][shop_domain] = max(
                        all_hourly_shop_visitors[hour_start][shop_domain],
                        visitors
                    )
            
            # 汇总单店铺数据
            for shop_domain, shop_hourly_data in result.get('store_hourly_data', {}).items():
                if shop_domain not in all_store_hourly_data:
                    all_store_hourly_data[shop_domain] = {}
                
                for hour_start, data in shop_hourly_data.items():
                    if hour_start not in all_store_hourly_data[shop_domain]:
                        all_store_hourly_data[shop_domain][hour_start] = {
                            'sales': 0.0,
                            'orders': 0,
                            'visitors': 0
                        }
                    
                    # 累加同一小时的所有10分钟段
                    all_store_hourly_data[shop_domain][hour_start]['sales'] += data['sales']
                    all_store_hourly_data[shop_domain][hour_start]['orders'] += data['orders']
                    # 访客数取最大值（因为按天去重）
                    all_store_hourly_data[shop_domain][hour_start]['visitors'] = max(
                        all_store_hourly_data[shop_domain][hour_start]['visitors'],
                        data['visitors']
                    )
        else:
            failed_segments.append(result)
            logger.error(f"时间段 {result['start_time']} - {result['end_time']} 处理失败: {result.get('error')}")
    
    if failed_segments:
        logger.warning(f"有 {len(failed_segments)} 个时间段处理失败")
        logger.info("")
    
    # 计算每个小时的总访客数（所有店铺累加）
    for hour_start in all_hourly_data.keys():
        total_visitors = 0
        if hour_start in all_hourly_shop_visitors:
            # 累加所有店铺的访客数（不同店铺的访客是不同的IP）
            for shop_domain, visitors in all_hourly_shop_visitors[hour_start].items():
                total_visitors += visitors
        all_hourly_data[hour_start]['visitors'] = total_visitors
    
    # 4. 一次性写入所有小时的数据（覆盖模式，因为已经清空了）
    logger.info(f"正在写入总店铺数据：{len(all_hourly_data)} 个小时...")
    success_count = 0
    fail_count = 0
    
    # 写入总店铺数据
    for hour_start, data in sorted(all_hourly_data.items()):
        total_gmv = data['sales']
        total_orders = data['orders']
        total_visitors = data['visitors']
        avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
        
        # 使用覆盖模式（因为已经清空了昨天的数据）
        success = db.insert_or_update_hourly_data(
            hour_start,
            total_gmv,
            total_orders,
            total_visitors,
            avg_order_value
        )
        
        if success:
            success_count += 1
            logger.info(
                f"补全总店铺数据成功: {hour_start} | "
                f"订单={total_orders}, 销售额=${total_gmv:.2f}, 访客={total_visitors}"
            )
        else:
            fail_count += 1
            logger.error(f"补全总店铺数据失败: {hour_start}")
    
    logger.info(f"总店铺数据写入完成：成功 {success_count} 条，失败 {fail_count} 条")
    logger.info("")
    
    # 写入单店铺数据
    logger.info(f"正在写入单店铺数据...")
    store_success_count = 0
    store_fail_count = 0
    
    for shop_domain, shop_hourly_data in all_store_hourly_data.items():
        for hour_start, data in sorted(shop_hourly_data.items()):
            total_gmv = data['sales']
            total_orders = data['orders']
            total_visitors = data['visitors']
            avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
            
            # 写入单店铺明细数据（使用覆盖模式）
            success = db.insert_or_update_store_hourly(
                shop_domain=shop_domain,
                time_hour=hour_start,
                total_gmv=total_gmv,
                total_orders=total_orders,
                total_visitors=total_visitors,
                gmv_from_analysis=0.0,
                orders_from_analysis=0
            )
            
            if success:
                store_success_count += 1
            else:
                store_fail_count += 1
                logger.error(f"补全单店铺数据失败: {shop_domain}, {hour_start}")
    
    logger.info(f"单店铺数据写入完成：成功 {store_success_count} 条，失败 {store_fail_count} 条")
    logger.info("")
    
    # 5. 更新同步状态：标记昨天数据已完成
    db.update_sync_status('ten_minute_realtime', yesterday_end, yesterday_start.date(), 0)
    
    logger.info("=" * 80)
    logger.info(f"昨天 {yesterday_start.date()} 的最终数据收集完成（覆盖模式）")
    logger.info("=" * 80)


def process_ten_minute_segment(start_time: datetime, end_time: datetime, db: Database) -> bool:
    """
    处理单个10分钟段的数据收集和写入
    
    Args:
        start_time: 段开始时间
        end_time: 段结束时间
        db: 数据库实例
    
    Returns:
        是否成功
    """
    try:
        # 1. 获取所有启用的店铺
        stores = db.get_active_stores()
        if not stores:
            logger.warning("没有启用的店铺，跳过同步")
            return False
        
        # 2. 并行收集所有店铺的数据（10个线程）
        all_store_data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_store = {
                executor.submit(sync_store_data_for_ten_minutes, 
                              store['shop_domain'], store['access_token'],
                              start_time, end_time): store
                for store in stores
            }
            
            for future in concurrent.futures.as_completed(future_to_store):
                store = future_to_store[future]
                try:
                    result = future.result()
                    all_store_data[store['shop_domain']] = result
                except Exception as e:
                    logger.error(f"店铺 {store['shop_domain']} 数据收集异常: {e}")
                    all_store_data[store['shop_domain']] = {
                        'success': False,
                        'sales': 0.0,
                        'orders': 0,
                        'visitors': 0,
                        'error': str(e)
                    }
        
        # 3. 汇总所有店铺的数据
        total_sales = 0.0
        total_orders = 0
        total_visitors = 0
        
        # 确定数据属于哪个小时
        time_hour = start_time.replace(minute=0, second=0, microsecond=0)
        
        # 4. 写入单店铺明细表（增量累加模式）
        # ⭐ 修复：使用增量累加模式，在数据库层面累加，避免重复累加问题
        write_failures_realtime = []
        for shop_domain, data in all_store_data.items():
            if data['success']:
                # 直接使用增量累加函数，传入本次段的增量值
                # data['sales'] 和 data['orders'] 是本次10分钟段该店铺的增量值
                # 函数内部会在数据库层面累加，避免重复累加问题
                success = db.insert_or_update_store_hourly_incremental(
                    shop_domain=shop_domain,
                    time_hour=time_hour,
                    total_gmv=data['sales'],
                    total_orders=data['orders'],
                    total_visitors=data['visitors']
                )
                
                if not success:
                    write_failures_realtime.append({
                        'shop_domain': shop_domain,
                        'time_hour': time_hour,
                        'orders': data['orders'],
                        'sales': data['sales'],
                        'retry_failed': False
                    })
                    # 重试一次（使用增量累加函数）
                    import time
                    time.sleep(0.3)
                    retry_success = db.insert_or_update_store_hourly_incremental(
                        shop_domain=shop_domain,
                        time_hour=time_hour,
                        total_gmv=data['sales'],
                        total_orders=data['orders'],
                        total_visitors=data['visitors']
                    )
                    if retry_success:
                        success = True
                    else:
                        write_failures_realtime[-1]['retry_failed'] = True
                
                if success:
                    # 累加数据（使用API采集的增量值）
                    total_sales += data['sales']
                    total_orders += data['orders']
                    total_visitors += data['visitors']
        
        # 5. 写入汇总表（增量累加模式）
        # ⭐ 修复：使用增量累加模式，在数据库层面累加，避免重复累加问题
        # total_sales 和 total_orders 已经是本次10分钟段收集到的所有店铺的累加值
        # 直接传入给增量累加函数，函数内部会在数据库层面累加
        success = db.insert_or_update_hourly_data_incremental(
            time_hour, total_sales, total_orders, total_visitors
        )
        
        if success:
            logger.info(f"成功更新小时数据: {time_hour}, "
                       f"销售额=${total_sales:.2f}, 订单数={total_orders}, 访客数={total_visitors}")
            return True
        else:
            logger.error(f"更新小时数据失败: {time_hour}")
            return False
            
    except Exception as e:
        logger.error(f"处理10分钟段失败 {start_time} - {end_time}: {e}")
        return False


def sync_realtime_data_ten_minutes():
    """
    十分钟实时数据同步主函数
    
    逻辑：
    1. 从 sync_status 表获取最后同步时间
    2. 计算本次要收集的时间段（10分钟）
    3. 并行收集所有店铺的数据
    4. 按小时汇总并累加到数据库
    5. 更新 sync_status 表
    """
    db = Database()
    now = beijing_time()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # ⭐ 判断是否是00:00:00执行（跨天处理）
    is_cross_day_execution = (now.hour == 0 and now.minute == 0 and now.second < 10)
    
    if is_cross_day_execution:
        logger.info("检测到00:00:00执行，开始收集昨天的最终数据...")
        sync_yesterday_final_data()
        logger.info("昨天最终数据收集完成，今天的数据将从00:10:00开始收集")
        return
    
    # 1. 计算当前正在进行的10分钟段和最近完成的段
    current_minute = now.minute
    current_segment_start_minute = (current_minute // 10) * 10  # 17:29 → 20（当前段的开始）
    current_segment_start = now.replace(minute=current_segment_start_minute, second=0, microsecond=0)
    current_segment_end = current_segment_start + timedelta(minutes=10) - timedelta(microseconds=1)
    
    # 2. 判断当前段是否已完成，并计算最近完成的段
    if now >= current_segment_end:
        # 当前段已完成，应该收集当前段
        recent_10min_start = current_segment_start
        recent_10min_end = current_segment_end
        logger.debug(
            f"当前段已完成 | "
            f"当前段: {current_segment_start} - {current_segment_end} | "
            f"当前时间: {now} >= 段结束时间 {current_segment_end}"
        )
    else:
        # 当前段还没完成，计算最近完成的段（往前推一个10分钟段）
        recent_10min_start_minute = current_segment_start_minute - 10
        if recent_10min_start_minute < 0:
            recent_10min_start_minute += 60
            recent_10min_start_hour = now.hour - 1
        else:
            recent_10min_start_hour = now.hour
        
        recent_10min_start = now.replace(
            hour=recent_10min_start_hour,
            minute=recent_10min_start_minute,
            second=0,
            microsecond=0
        )
        recent_10min_end = recent_10min_start + timedelta(minutes=10) - timedelta(microseconds=1)
        logger.debug(
            f"当前段未完成 | "
            f"当前段（进行中）: {current_segment_start} - {current_segment_end} | "
            f"最近完成的段: {recent_10min_start} - {recent_10min_end} | "
            f"当前时间: {now} < 段结束时间 {current_segment_end}"
        )
    
    # 2. 获取最后同步时间
    sync_status = db.get_sync_status('ten_minute_realtime')
    
    if sync_status:
        last_sync_end_time = sync_status['last_sync_end_time']
        
        # ⭐ 自动转换旧格式数据（整点格式 → 结束时间格式）
        if last_sync_end_time.second == 0 and last_sync_end_time.microsecond == 0:
            old_format_time = last_sync_end_time
            # 转换逻辑：17:10:00 - 1秒 = 17:09:59
            # 注意：数据库的 DATETIME 类型不支持微秒精度，所以使用 17:09:59 即可
            last_sync_end_time = (last_sync_end_time - timedelta(seconds=1)).replace(microsecond=0)
            logger.info(f"检测到旧格式同步状态 {old_format_time}，自动转换为新格式 {last_sync_end_time}")
            db.update_sync_status(
                'ten_minute_realtime',
                last_sync_end_time,
                sync_status['last_sync_date'],
                sync_status.get('last_visitor_cumulative', 0)
            )
        
        # 如果最后同步时间不是今天的，从今天00:00:00开始
        if last_sync_end_time.date() != today_start.date():
            next_segment_start = today_start
        else:
            # 计算下一个应该同步的段的开始时间
            next_segment_start = last_sync_end_time + timedelta(seconds=1)
            next_segment_start = next_segment_start.replace(second=0, microsecond=0)
            # 对齐到10分钟边界
            next_segment_minute = (next_segment_start.minute // 10) * 10
            next_segment_start = next_segment_start.replace(minute=next_segment_minute, second=0, microsecond=0)
    else:
        # 首次运行：从最近完成的段开始
        next_segment_start = recent_10min_start
    
    # 3. 连续补录所有缺失的段
    segments_to_process = []
    segment_start = next_segment_start
    
    while segment_start <= recent_10min_end:
        segment_end = segment_start + timedelta(minutes=10) - timedelta(microseconds=1)
        # 只处理已完成的段
        if segment_end <= now:
            segments_to_process.append((segment_start, segment_end))
        segment_start = segment_end + timedelta(seconds=1)
        segment_start = segment_start.replace(second=0, microsecond=0)
        segment_minute = (segment_start.minute // 10) * 10
        segment_start = segment_start.replace(minute=segment_minute, second=0, microsecond=0)
    
    if not segments_to_process:
        logger.info("没有新数据需要收集")
        return
    
    logger.info(f"发现 {len(segments_to_process)} 个缺失的10分钟段需要补录")
    
    # 4. 依次处理每个缺失的段
    for segment_start, segment_end in segments_to_process:
        logger.info(f"处理10分钟段: {segment_start} - {segment_end}")
        success = process_ten_minute_segment(segment_start, segment_end, db)
        
        if success:
            # 更新同步状态
            sync_date = segment_start.date()
            db.update_sync_status('ten_minute_realtime', segment_end, sync_date, 0)
            logger.info(f"10分钟段处理完成: {segment_start} - {segment_end}")
        else:
            logger.error(f"10分钟段处理失败: {segment_start} - {segment_end}")
            # 如果某个段处理失败，停止后续段的处理（避免数据不连续）
            break
    
    # 聚合：所有段处理完成后聚合今天的数据（幂等，重复聚合不会出错）
    try:
        conn_agg = db.get_connection()
        aggregate_date(conn_agg, today_start.date(), verbose=False)
        conn_agg.close()
        logger.info(f"聚合任务完成: {today_start.date()}")
    except Exception as e:
        logger.error(f"聚合任务失败: {e}", exc_info=True)


if __name__ == '__main__':
    import sys

    # 获取进程锁（必须在主逻辑开始前）
    lock_handle = acquire_lock()
    
    try:
        # 检查命令行参数
        if len(sys.argv) > 1:
            if sys.argv[1] == '--historical':
                # 回溯历史数据
                # 支持两种格式：
                # 1. python data_sync.py --historical 1
                # 2. python data_sync.py --historical --months 1
                months = 3  # 默认值
                if len(sys.argv) > 2:
                    if sys.argv[2] == '--months' and len(sys.argv) > 3:
                        # 格式：--historical --months 1
                        try:
                            months = int(sys.argv[3])
                        except ValueError:
                            print(f"❌ 错误: 无效的月数参数: {sys.argv[3]}")
                            print("用法: python data_sync.py --historical --months <月数>")
                            sys.exit(1)
                    else:
                        # 格式：--historical 1
                        try:
                            months = int(sys.argv[2])
                        except ValueError:
                            print(f"❌ 错误: 无效的月数参数: {sys.argv[2]}")
                            print("用法: python data_sync.py --historical <月数>")
                            sys.exit(1)
                sync_historical_data(months)
            elif sys.argv[1] == '--manual':
                # 手动同步昨天数据
                sync_all_stores()
            elif sys.argv[1] == '--realtime':
                # 十分钟实时同步
                sync_realtime_data_ten_minutes()
            else:
                print("用法:")
                print("  python data_sync.py                        # 同步昨天数据")
                print("  python data_sync.py --historical [月数]     # 回溯历史数据")
                print("  python data_sync.py --historical --months <月数>  # 回溯历史数据（指定月数）")
                print("  python data_sync.py --manual               # 手动同步昨天数据")
                print("  python data_sync.py --realtime             # 十分钟实时同步")
        else:
            # 默认同步昨天数据
            sync_all_stores()
    finally:
        # 确保锁被释放（虽然程序结束会自动释放，但显式关闭更安全）
        if lock_handle:
            lock_handle.close()
            logger.info("进程锁已释放")

        

