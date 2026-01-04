"""
补全缺失时间段的数据

使用方法：
python fill_missing_data.py
"""
import sys
import time
import msvcrt
import os
from datetime import datetime, timedelta
from data_sync import sync_store_data_for_ten_minutes, beijing_time
from database import Database
import concurrent.futures
from utils import setup_logging
from config import LOG_CONFIG
import logging
from aggregate_owner_daily import aggregate_date

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


def get_missing_time_segments():
    """
    获取缺失的时间段
    从sync_status表获取最后同步时间，然后计算需要补全的时间段
    """
    db = Database()
    
    # 获取最后同步时间
    sync_status = db.get_sync_status('ten_minute_realtime')
    if not sync_status:
        logger.warning("没有找到同步状态记录，无法确定缺失时间段")
        return []
    
    last_sync_end_time = sync_status['last_sync_end_time']
    now = beijing_time()
    
    logger.info(f"最后同步时间: {last_sync_end_time}, 当前时间: {now}")
    
    # 如果最后同步时间是今天的
    if last_sync_end_time.date() == now.date():
        # 计算从最后同步时间到当前时间的所有10分钟段
        segments = []
        current_time = last_sync_end_time
        
        # ⭐ 统一处理：无论是旧格式还是新格式，都转换为"已收集段的结束时间"
        # 如果last_sync_end_time是整点（例如16:30:00），这是旧格式
        # 如果last_sync_end_time不是整点（例如16:29:59.999999），这是新格式
        if current_time.second == 0 and current_time.microsecond == 0:
            # 旧格式：整点表示"下一个段的开始"，需要转换为"已收集段的结束时间"
            # 例如：16:30:00 表示 16:25:00-16:29:59 已收集完，实际结束时间是 16:29:59.999999
            actual_end_time = current_time - timedelta(minutes=5) + timedelta(seconds=59, microseconds=999999)
            # 下一个段从这个整点开始（即16:30:00），这就是我们要开始补齐的起点
            next_segment_start = current_time
        else:
            # 新格式：current_time 是"已收集段的结束时间"
            # 例如：16:29:59.999999 表示 16:25:00-16:29:59 已收集完
            actual_end_time = current_time
            # 计算下一个10分钟段的开始（当前结束时间 + 1秒，然后对齐到10分钟）
            next_segment_start = current_time + timedelta(seconds=1)
            next_segment_start = next_segment_start.replace(second=0, microsecond=0)
            # 如果秒数为0，说明正好是整点，直接使用
            # 否则，计算下一个10分钟段的开始
            if next_segment_start.minute % 10 != 0:
                current_minute = next_segment_start.minute
                next_segment_start_minute = ((current_minute // 10) + 1) * 10
                if next_segment_start_minute >= 60:
                    next_segment_start_minute = 0
                    next_segment_start_hour = next_segment_start.hour + 1
                else:
                    next_segment_start_hour = next_segment_start.hour
                
                next_segment_start = next_segment_start.replace(
                    hour=next_segment_start_hour,
                    minute=next_segment_start_minute
                )
        
        # 计算当前时间往前推一个10分钟段的结束时间（最近完成的段）
        # 注意：只补齐已完成的段，不补齐正在进行的段
        current_minute = now.minute
        current_segment_start_minute = (current_minute // 10) * 10
        current_segment_start = now.replace(minute=current_segment_start_minute, second=0, microsecond=0)
        current_segment_end = current_segment_start + timedelta(minutes=10) - timedelta(microseconds=1)
        
        # 如果当前段已完成，最近完成的段就是当前段
        if now >= current_segment_end:
            recent_segment_end = current_segment_end
        else:
            # 当前段未完成，最近完成的段是前一个段
            recent_segment_start_minute = current_segment_start_minute - 10
            if recent_segment_start_minute < 0:
                recent_segment_start_minute += 60
                recent_segment_start_hour = now.hour - 1
            else:
                recent_segment_start_hour = now.hour
            
            recent_segment_start = now.replace(
                hour=recent_segment_start_hour,
                minute=recent_segment_start_minute,
                second=0,
                microsecond=0
            )
            recent_segment_end = recent_segment_start + timedelta(minutes=5) - timedelta(microseconds=1)
        
        logger.info(f"计算缺失时间段: 从 {next_segment_start} 到 {recent_segment_end}（最近完成的段）")
        
        # 生成所有需要补全的时间段（只补全已完成的段）
        # next_segment_start 是要开始补齐的段的开始时间
        # recent_segment_end 是最近完成的段的结束时间
        # 只有当 next_segment_start <= recent_segment_end 时，才有缺失的段
        segment_start = next_segment_start
        
        # 生成所有缺失的10分钟段
        while segment_start <= recent_segment_end:
            segment_end = segment_start + timedelta(minutes=10) - timedelta(microseconds=1)
            
            # 只添加已完成的段（段结束时间 <= 当前时间）
            if segment_end <= now:
                segments.append((segment_start, segment_end))
            else:
                # 遇到未完成的段，停止
                break
            
            # 计算下一个段的开始时间（对齐到10分钟边界）
            segment_start = segment_end + timedelta(seconds=1)
            segment_start = segment_start.replace(second=0, microsecond=0)
            segment_minute = (segment_start.minute // 10) * 10
            segment_start = segment_start.replace(minute=segment_minute, second=0, microsecond=0)
        
        return segments
    else:
        logger.warning("最后同步时间不是今天的，无法补全")
        return []


def sync_time_segment(start_time, end_time):
    """
    同步指定时间段的数据
    """
    logger.info(f"开始补全时间段: {start_time} - {end_time}")
    
    db = Database()
    stores = db.get_active_stores()
    if not stores:
        logger.warning("没有启用的店铺，跳过同步")
        return False
    
    # 并行收集所有店铺的数据
    all_store_data = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_store = {
            executor.submit(sync_store_data_for_ten_minutes, 
                          shop['shop_domain'], shop['access_token'], 
                          start_time, end_time): shop['shop_domain']
            for shop in stores
        }
        
        for future in concurrent.futures.as_completed(future_to_store):
            shop_domain = future_to_store[future]
            try:
                result = future.result()
                # ⭐ 修复：检查返回的数据格式
                if result is None:
                    logger.error(f"店铺 {shop_domain} 数据收集返回 None")
                    all_store_data[shop_domain] = {'success': False, 'error': '返回数据为None'}
                elif not isinstance(result, dict):
                    logger.error(f"店铺 {shop_domain} 数据收集返回格式错误: {type(result)}")
                    all_store_data[shop_domain] = {'success': False, 'error': f'返回数据类型错误: {type(result)}'}
                elif 'success' not in result:
                    logger.error(f"店铺 {shop_domain} 数据收集返回缺少success字段: {result}")
                    all_store_data[shop_domain] = {'success': False, 'error': '返回数据缺少success字段'}
                else:
                    all_store_data[shop_domain] = result
                    # 如果success为False但没有error字段，添加默认错误信息
                    if not result.get('success') and 'error' not in result:
                        result['error'] = '数据收集失败（原因未知）'
                        logger.warning(f"店铺 {shop_domain} 数据收集失败，但没有错误信息: {result}")
            except Exception as e:
                logger.error(f"店铺 {shop_domain} 数据收集异常: {e}", exc_info=True)
                all_store_data[shop_domain] = {'success': False, 'error': str(e)}
    
    # ⭐ 修复：按小时汇总数据
    # sync_store_data_for_ten_minutes返回的是 {'success': bool, 'sales': float, 'orders': int, 'visitors': int}
    # 而不是 {'hourly_data': {...}}
    # 需要直接使用sales、orders、visitors字段，并按小时汇总
    
    # 计算10分钟段属于哪个小时
    time_hour = start_time.replace(minute=0, second=0, microsecond=0)
    
    # 汇总所有店铺的数据
    hourly_data = {
        time_hour: {
            'sales': 0.0,
            'orders': 0,
            'visitors': 0
        }
    }
    total_sales = 0.0
    total_orders = 0
    total_visitors = 0
    
    # ⭐ 修复：直接使用sales、orders、visitors字段（而不是hourly_data）
    successful_stores = []
    failed_stores = []
    
    for shop_domain, data in all_store_data.items():
        # ⭐ 修复：更严格的检查逻辑
        if data is None:
            logger.error(f"店铺 {shop_domain} 数据为 None")
            failed_stores.append({'shop_domain': shop_domain, 'reason': '数据为None'})
            continue
        
        if not isinstance(data, dict):
            logger.error(f"店铺 {shop_domain} 数据格式错误: {type(data)}")
            failed_stores.append({'shop_domain': shop_domain, 'reason': f'数据格式错误: {type(data)}'})
            continue
        
        # 检查success字段
        success = data.get('success')
        if success is True:
            # 累加数据（即使订单数为0，只要API调用成功，就应该累加）
            hourly_data[time_hour]['sales'] += data.get('sales', 0.0)
            hourly_data[time_hour]['orders'] += data.get('orders', 0)
            # 访客数：取最大值（因为是累计值，同一天所有小时使用相同值）
            hourly_data[time_hour]['visitors'] = max(
                hourly_data[time_hour]['visitors'],
                data.get('visitors', 0)
            )
            
            total_sales += data.get('sales', 0.0)
            total_orders += data.get('orders', 0)
            successful_stores.append(shop_domain)
            
            logger.debug(
                f"店铺 {shop_domain} 数据: 订单={data.get('orders', 0)}, "
                f"销售额=${data.get('sales', 0.0):.2f}, 访客={data.get('visitors', 0)}"
            )
        else:
            # success为False或None，记录失败原因
            error_msg = data.get('error', '未知错误')
            if success is False:
                logger.warning(f"店铺 {shop_domain} 数据收集失败: {error_msg}")
            else:
                logger.warning(f"店铺 {shop_domain} 数据收集失败（success字段为None或缺失）: {error_msg}")
            failed_stores.append({'shop_domain': shop_domain, 'reason': error_msg})
    
    # 记录统计信息
    if failed_stores:
        logger.warning(
            f"⚠️  有 {len(failed_stores)} 个店铺数据收集失败: "
            f"{[f['shop_domain'] for f in failed_stores[:5]]}"  # 只显示前5个
        )
    
    logger.info(
        f"数据汇总: 成功={len(successful_stores)}, 失败={len(failed_stores)}, "
        f"总订单={total_orders}, 总销售额=${total_sales:.2f}"
    )
    
    # ⭐ 修复：验证数据是否合理
    if total_orders < 0 or total_sales < 0:
        logger.error(
            f"数据异常：订单数或销售额为负数。"
            f"时间段: {start_time} - {end_time}, 订单数: {total_orders}, 销售额: ${total_sales:.2f}"
        )
    
    if total_orders > 0 and total_sales == 0:
        logger.warning(
            f"数据异常：有订单但销售额为0，可能存在价格解析问题。"
            f"时间段: {start_time} - {end_time}, 订单数: {total_orders}"
        )
    
    # ⭐ 修复：写入数据库，并验证写入是否成功
    store_write_failures = []
    store_write_success_count = 0
    
    # 写入单店铺明细数据（使用增量更新函数，累加模式）
    for shop_domain, data in all_store_data.items():
        if 'error' not in data and data.get('success'):
            success = db.insert_or_update_store_hourly_incremental(
                shop_domain=shop_domain,
                time_hour=time_hour,
                total_gmv=data.get('sales', 0.0),
                total_orders=data.get('orders', 0),
                total_visitors=data.get('visitors', 0)
            )
            
            if not success:
                # 重试一次
                time.sleep(0.3)
                retry_success = db.insert_or_update_store_hourly_incremental(
                    shop_domain=shop_domain,
                    time_hour=time_hour,
                    total_gmv=data.get('sales', 0.0),
                    total_orders=data.get('orders', 0),
                    total_visitors=data.get('visitors', 0)
                )
                
                if retry_success:
                    success = True
                    logger.info(f"店铺 {shop_domain} 数据写入成功（重试后）")
                else:
                    store_write_failures.append(shop_domain)
                    logger.error(
                        f"店铺 {shop_domain} 数据写入失败（重试后仍失败） - "
                        f"time_hour={time_hour.strftime('%Y-%m-%d %H:00')}, "
                        f"订单={data.get('orders', 0)}, 销售额=${data.get('sales', 0.0):.2f}"
                    )
            
            if success:
                store_write_success_count += 1
    
    # 写入汇总数据
    summary_write_success = False
    if hourly_data:
        summary_write_success = db.insert_or_update_hourly_data_incremental(
            time_hour, hourly_data[time_hour]['sales'], 
            hourly_data[time_hour]['orders'], hourly_data[time_hour]['visitors']
        )
        
        if summary_write_success:
            logger.info(
                f"成功更新小时数据: {time_hour}, "
                f"销售额=${hourly_data[time_hour]['sales']:.2f}, "
                f"订单数={hourly_data[time_hour]['orders']}, "
                f"访客数={hourly_data[time_hour]['visitors']}"
            )
        else:
            logger.error(f"更新小时数据失败: {time_hour}")
    
    # ⭐ 修复：只有在汇总数据写入成功，且有店铺数据收集成功时才更新同步状态
    # 如果所有店铺数据收集失败，不应该更新状态，即使汇总数据写入成功
    if summary_write_success and len(successful_stores) > 0:
        # 更新同步状态（使用统一逻辑：存储"已收集段的结束时间"）
        today_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        sync_date = today_start.date()
        db.update_sync_status('ten_minute_realtime', end_time, sync_date, total_visitors)
        logger.info(
            f"同步状态已更新: {end_time} (成功店铺: {len(successful_stores)}/{len(all_store_data)})"
        )
        
        if store_write_failures:
            logger.warning(
                f"有 {len(store_write_failures)} 个店铺数据写入失败，但总数据已更新。"
                f"失败的店铺: {store_write_failures}"
            )
        
        if len(failed_stores) > 0:
            logger.warning(
                f"有 {len(failed_stores)} 个店铺数据收集失败，但已更新同步状态。"
                f"失败的店铺: {[f['shop_domain'] for f in failed_stores[:5]]}"
            )
    elif not summary_write_success:
        logger.error(
            f"汇总数据写入失败，不更新同步状态，等待下次重试。"
            f"时间段: {start_time} - {end_time}, 订单数: {total_orders}, 销售额: ${total_sales:.2f}"
        )
        return False  # 返回False，表示补齐失败
    elif len(successful_stores) == 0:
        logger.error(
            f"所有店铺数据收集失败，不更新同步状态，等待下次重试。"
            f"时间段: {start_time} - {end_time}, 失败店铺数: {len(failed_stores)}"
        )
        return False  # 返回False，表示补齐失败
    else:
        # 这种情况理论上不应该发生
        logger.error(
            f"未知错误，不更新同步状态。"
            f"时间段: {start_time} - {end_time}"
        )
        return False
    
    logger.info(
        f"时间段补全完成: {start_time} - {end_time}, "
        f"销售额=${total_sales:.2f}, 订单数={total_orders}, 访客数={total_visitors}, "
        f"单店铺写入成功: {store_write_success_count}/{len([s for s in all_store_data.values() if s.get('success')])}, "
        f"汇总数据写入: {'成功' if summary_write_success else '失败'}"
    )
    
    return summary_write_success  # 返回写入是否成功


if __name__ == '__main__':
    # 获取进程锁（必须在主逻辑开始前）
    lock_handle = acquire_lock()
    
    try:
        # 自动计算缺失的时间段
        segments = get_missing_time_segments()
        
        if not segments:
            logger.info("没有需要补全的时间段")
            sys.exit(0)
        
        logger.info(f"找到 {len(segments)} 个需要补全的时间段:")
        for i, (start, end) in enumerate(segments, 1):
            logger.info(f"  {i}. {start} - {end}")
        
        # 逐个补全
        success_count = 0
        failed_count = 0
        for i, (start_time, end_time) in enumerate(segments, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"正在补全第 {i}/{len(segments)} 个时间段: {start_time} - {end_time}")
            logger.info(f"{'='*60}")
            result = sync_time_segment(start_time, end_time)
            if result:
                success_count += 1
            else:
                failed_count += 1
                logger.error(f"时间段 {start_time} - {end_time} 补全失败")
        
        logger.info(f"\n{'='*60}")
        if failed_count == 0:
            logger.info(f"✅ 所有缺失时间段补全完成！成功: {success_count}, 失败: {failed_count}")
        else:
            logger.warning(
                f"⚠️  补全完成，但有部分失败。成功: {success_count}, 失败: {failed_count} | "
                f"建议检查日志，确认失败的时段是否需要重新补全"
            )
        logger.info(f"{'='*60}")
        
        # 自动聚合涉及的所有日期的数据（幂等，重复聚合不会出错）
        if segments:
            # 收集所有涉及的日期
            dates_to_aggregate = set()
            for start_time, end_time in segments:
                dates_to_aggregate.add(start_time.date())
                # 如果跨天，也添加结束日期
                if end_time.date() != start_time.date():
                    dates_to_aggregate.add(end_time.date())
            
            if dates_to_aggregate:
                print()
                print("=" * 80)
                print(f"开始聚合涉及的数据（共 {len(dates_to_aggregate)} 个日期）...")
                print("=" * 80)
                db_agg = Database()
                try:
                    conn_agg = db_agg.get_connection()
                    for date in sorted(dates_to_aggregate):
                        try:
                            aggregate_date(conn_agg, date, verbose=True)
                            logger.info(f"✅ 聚合任务完成: {date}")
                        except Exception as e:
                            logger.error(f"聚合任务失败 {date}: {e}", exc_info=True)
                            print(f"❌ 聚合任务失败 {date}: {e}")
                    conn_agg.close()
                    print(f"✅ 所有日期的聚合任务完成")
                except Exception as e:
                    logger.error(f"聚合任务失败: {e}", exc_info=True)
                    print(f"❌ 聚合任务失败: {e}")
    finally:
        # 确保锁被释放
        if lock_handle:
            lock_handle.close()
            logger.info("进程锁已释放")

