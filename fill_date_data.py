"""
补齐指定日期的数据（10分钟粒度）

使用方法：
python fill_date_data.py [日期] [并行时间段数量]

参数：
  日期：要补齐的日期，格式：YYYY-MM-DD，例如：2025-12-08
        如果不提供日期，默认补齐今天的数据
        可以使用相对日期：
        - today 或 今天：今天
        - yesterday 或 昨天：昨天
        - 2 或 -1：前天（往前推1天，相对于今天）
        - 3 或 -2：三天前（往前推2天，相对于今天）
        - 4 或 -3：四天前（往前推3天，相对于今天）
  
  并行时间段数量：同时处理的时间段数量，默认6（建议4-8）

示例：
  python fill_date_data.py 2025-12-08              # 补齐 2025-12-08 的数据
  python fill_date_data.py yesterday                # 补齐昨天的数据
  python fill_date_data.py 3                        # 补齐三天前的数据
  python fill_date_data.py 2025-12-08 8            # 补齐指定日期，使用8个并行时间段
"""
import sys
import io
import msvcrt
import os
from datetime import datetime, timedelta, date
from data_sync import sync_store_data_for_ten_minutes, beijing_time
from database import Database
import concurrent.futures
from utils import setup_logging
from config import LOG_CONFIG
import logging
from aggregate_owner_daily import aggregate_date

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

setup_logging(LOG_CONFIG['log_file'], LOG_CONFIG['log_level'])
logger = logging.getLogger(__name__)


def acquire_lock():
    """
    获取进程锁（防止多个进程同时运行）
    使用与 data_sync.py 相同的锁文件，确保补全脚本和自动同步脚本不会同时运行
    
    Returns:
        file: 锁文件句柄（必须返回并保持打开状态，否则锁会失效）
    
    如果获取锁失败（另一个进程正在运行），直接退出程序
    """
    # 在脚本目录下创建锁文件（与 data_sync.py 使用相同的锁文件）
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
        print("⚠️  检测到另一个进程正在同步中（可能是自动同步脚本或另一个补全脚本），当前进程自动退出。")
        logger.info("进程锁获取失败，另一个进程正在运行，退出")
        sys.exit(0)
    except Exception as e:
        # 其他异常（例如文件权限问题）
        logger.error(f"获取进程锁失败: {e}")
        print(f"❌ 获取进程锁失败: {e}")
        sys.exit(1)


def parse_date_argument(date_arg: str) -> date:
    """
    解析日期参数
    
    Args:
        date_arg: 日期字符串
    
    Returns:
        date对象
    """
    date_arg_lower = date_arg.lower().strip()
    now = beijing_time()
    today = now.date()
    
    # 处理相对日期
    if date_arg_lower in ['today', '今天', '0']:
        return today
    elif date_arg_lower in ['yesterday', '昨天', '-1', '1']:
        return today - timedelta(days=1)
    elif date_arg_lower in ['前天', '-2', '2']:
        return today - timedelta(days=2)
    elif date_arg_lower in ['三天前', '-3', '3']:
        return today - timedelta(days=3)
    elif date_arg_lower in ['四天前', '-4', '4']:
        return today - timedelta(days=4)
    
    # 处理数字（相对于今天往前推N天）
    try:
        days = int(date_arg)
        if days < 0:
            return today + timedelta(days=days)  # days已经是负数，直接加
        elif days > 0:
            return today - timedelta(days=days)
        else:
            return today
    except ValueError:
        pass
    
    # 处理日期字符串 YYYY-MM-DD
    try:
        target_date = datetime.strptime(date_arg, '%Y-%m-%d').date()
        return target_date
    except ValueError:
        raise ValueError(f"无效的日期参数: {date_arg}。支持的格式：YYYY-MM-DD、today、yesterday、数字（相对日期）")


def fill_date_data(target_date: date, parallel_segments: int = 6):
    """
    补齐指定日期的数据
    
    Args:
        target_date: 目标日期
        parallel_segments: 并行时间段数量
    """
    db = Database()
    now = beijing_time()
    
    # 计算目标日期的开始和结束时间
    date_start = datetime.combine(target_date, datetime.min.time())
    date_end = datetime.combine(target_date, datetime.max.time().replace(microsecond=999999))
    
    # 如果目标日期是今天，结束时间应该是当前时间往前推一个10分钟段
    if target_date == now.date():
        current_minute = now.minute
        current_segment_start_minute = (current_minute // 10) * 10
        latest_completed_segment_end = now.replace(
            minute=current_segment_start_minute,
            second=0,
            microsecond=0
        ) - timedelta(microseconds=1)
        if latest_completed_segment_end < date_end:
            date_end = latest_completed_segment_end
    
    print("=" * 80)
    print(f"补齐 {target_date.strftime('%Y-%m-%d')} 的数据")
    print("=" * 80)
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标日期：{target_date.strftime('%Y-%m-%d')}")
    print(f"日期开始：{date_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"日期结束：{date_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 计算该日期的所有5分钟段
    segments = []
    current_segment_start = date_start
    
    while current_segment_start <= date_end:
        current_segment_end = current_segment_start + timedelta(minutes=10) - timedelta(microseconds=1)
        if current_segment_end > date_end:
            current_segment_end = date_end
        segments.append((current_segment_start, current_segment_end))
        current_segment_start = current_segment_start + timedelta(minutes=10)
    
    print(f"需要补全的时间段数量：{len(segments)}")
    if segments:
        print(f"时间段范围：{segments[0][0].strftime('%H:%M:%S')} - {segments[-1][1].strftime('%H:%M:%S')}")
    print()
    
    if not segments:
        print(f"没有需要补全的数据（日期 {target_date.strftime('%Y-%m-%d')} 没有完整的10分钟段）")
        return
    
    # 获取所有启用的店铺
    stores = db.get_active_stores()
    if not stores:
        print("没有启用的店铺")
        return
    
    print(f"活跃店铺数量：{len(stores)}")
    print(f"并行时间段数量：{parallel_segments}")
    print()
    
    # ⚠️ 重要：先清空该日期的数据，避免重复累加
    print("=" * 80)
    print(f"步骤1：清空 {target_date.strftime('%Y-%m-%d')} 的数据（避免重复累加）")
    print("=" * 80)
    
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
                cursor.execute(delete_sql, (date_start,))
                deleted_overview = cursor.rowcount
                
                cursor.execute(delete_store_sql, (date_start,))
                deleted_store = cursor.rowcount
                
                conn.commit()
                
                print(f"已删除汇总表数据：{deleted_overview} 条")
                print(f"已删除明细表数据：{deleted_store} 条")
                print()
    except Exception as e:
        logger.error(f"清空数据失败: {e}")
        print(f"⚠️  清空数据失败: {e}")
        print("继续执行数据补齐...")
        print()
    
    # 步骤2：分批并行处理时间段
    print("=" * 80)
    print(f"步骤2：开始补齐 {len(segments)} 个时间段的数据")
    print("=" * 80)
    
    total_segments = len(segments)
    completed_segments = 0
    failed_segments = 0
    
    # 分批处理
    for batch_start in range(0, total_segments, parallel_segments):
        batch_end = min(batch_start + parallel_segments, total_segments)
        batch_segments = segments[batch_start:batch_end]
        
        print(f"\n处理批次 {batch_start // parallel_segments + 1}：时间段 {batch_start + 1}-{batch_end} / {total_segments}")
        
        # 并行处理这个批次的时间段
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_segments) as executor:
            future_to_segment = {
                executor.submit(
                    process_segment,
                    segment_start,
                    segment_end,
                    stores,
                    batch_start + idx + 1,
                    total_segments
                ): (segment_start, segment_end)
                for idx, (segment_start, segment_end) in enumerate(batch_segments)
            }
            
            for future in concurrent.futures.as_completed(future_to_segment):
                segment_start, segment_end = future_to_segment[future]
                try:
                    success = future.result()
                    if success:
                        completed_segments += 1
                    else:
                        failed_segments += 1
                except Exception as e:
                    logger.error(f"处理时间段失败 {segment_start} - {segment_end}: {e}")
                    failed_segments += 1
    
    # 完成
    print()
    print("=" * 80)
    print("补齐完成")
    print("=" * 80)
    print(f"总时间段数：{total_segments}")
    print(f"成功补齐：{completed_segments}")
    print(f"失败：{failed_segments}")
    print()
    
    if completed_segments == total_segments:
        print("✅ 所有时间段补齐成功！")
    elif completed_segments > 0:
        print(f"⚠️  部分时间段补齐成功（{completed_segments}/{total_segments}）")
    else:
        print("❌ 所有时间段补齐失败")
    
    # 自动聚合指定日期的数据（幂等，重复聚合不会出错）
    print()
    print("=" * 80)
    print(f"开始聚合 {target_date} 的数据...")
    print("=" * 80)
    try:
        conn_agg = db.get_connection()
        aggregate_date(conn_agg, target_date, verbose=True)
        conn_agg.close()
        print(f"✅ 聚合任务完成: {target_date}")
    except Exception as e:
        logger.error(f"聚合任务失败: {e}", exc_info=True)
        print(f"❌ 聚合任务失败: {e}")


def process_segment(segment_start: datetime, segment_end: datetime, stores: list, 
                    segment_num: int, total_segments: int) -> bool:
    """
    处理单个时间段的数据
    
    Args:
        segment_start: 时间段开始时间
        segment_end: 时间段结束时间
        stores: 店铺列表
        segment_num: 时间段序号
        total_segments: 总时间段数
    
    Returns:
        是否成功
    """
    db = Database()
    
    try:
        # 并行处理所有店铺
        store_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_store = {
                executor.submit(
                    sync_store_data_for_ten_minutes,
                    store['shop_domain'],
                    store['access_token'],
                    segment_start,
                    segment_end
                ): store
                for store in stores
            }
            
            for future in concurrent.futures.as_completed(future_to_store):
                store = future_to_store[future]
                try:
                    result = future.result()
                    store_results[store['shop_domain']] = result
                except Exception as e:
                    logger.error(f"店铺 {store['shop_domain']} 数据收集失败: {e}")
                    store_results[store['shop_domain']] = {
                        'success': False,
                        'sales': 0.0,
                        'orders': 0,
                        'visitors': 0,
                        'error': str(e)
                    }
        
        # 汇总数据
        total_sales = 0.0
        total_orders = 0
        total_visitors = 0
        successful_stores = 0
        
        for shop_domain, result in store_results.items():
            if result.get('success'):
                total_sales += result.get('sales', 0.0)
                total_orders += result.get('orders', 0)
                total_visitors = max(total_visitors, result.get('visitors', 0))  # 访客数取最大值
                successful_stores += 1
        
        # 确定数据属于哪个小时
        time_hour = segment_start.replace(minute=0, second=0, microsecond=0)
        
        # 写入单店铺明细表（增量累加模式）
        store_write_success = 0
        for shop_domain, result in store_results.items():
            if result.get('success'):
                if db.insert_or_update_store_hourly_incremental(
                    shop_domain,
                    time_hour,
                    result.get('sales', 0.0),
                    result.get('orders', 0),
                    result.get('visitors', 0)
                ):
                    store_write_success += 1
        
        # 写入汇总表（增量累加模式）
        if total_sales > 0 or total_orders > 0 or total_visitors > 0:
            db.insert_or_update_hourly_data_incremental(
                time_hour,
                total_sales,
                total_orders,
                total_visitors
            )
        
        logger.info(
            f"时间段补齐完成 [{segment_num}/{total_segments}]: "
            f"{segment_start.strftime('%H:%M:%S')} - {segment_end.strftime('%H:%M:%S')}, "
            f"销售额=${total_sales:.2f}, 订单数={total_orders}, "
            f"访客数={total_visitors}, 单店铺写入成功={store_write_success}/{len(stores)}"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"处理时间段失败 {segment_start} - {segment_end}: {e}")
        return False


if __name__ == '__main__':
    # 获取进程锁（必须在主逻辑开始前）
    lock_handle = acquire_lock()
    
    try:
        # 解析参数
        target_date = None
        parallel_segments = 6
        
        if len(sys.argv) > 1:
            try:
                target_date = parse_date_argument(sys.argv[1])
            except ValueError as e:
                print(f"错误: {e}")
                print(__doc__)
                sys.exit(1)
        
        if len(sys.argv) > 2:
            try:
                parallel_segments = int(sys.argv[2])
                if parallel_segments < 1:
                    parallel_segments = 1
                elif parallel_segments > 10:
                    parallel_segments = 10
                    print(f"⚠️  并行数量超过限制，已调整为10")
            except ValueError:
                parallel_segments = 6
                print(f"⚠️  无效的并行数量参数，使用默认值6")
        
        # 如果没有提供日期，默认补齐今天
        if target_date is None:
            target_date = beijing_time().date()
        
        try:
            fill_date_data(target_date, parallel_segments)
        except KeyboardInterrupt:
            print("\n用户中断操作")
        except Exception as e:
            logger.error(f"补齐数据失败: {e}", exc_info=True)
            print(f"\n错误: {e}")
    finally:
        # 确保锁被释放
        if lock_handle:
            lock_handle.close()
            logger.info("进程锁已释放")




