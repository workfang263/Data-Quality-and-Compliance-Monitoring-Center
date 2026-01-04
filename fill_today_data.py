"""
补全今天缺失的数据
专门用于补全今天从00:00:00到当前时间的所有10分钟段数据

使用方法：
python fill_today_data.py [并行时间段数量]

参数：
  并行时间段数量：同时处理的时间段数量，默认6（建议4-8）
  例如：python fill_today_data.py 8  # 同时处理8个时间段

优化说明：
  - 每个时间段内，35个店铺并行处理（10个线程）
  - 多个时间段并行处理，大大加快补全速度
  - 默认6个时间段并行，总时间约为原来的1/6
"""
import sys
import io
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


def fill_today_data():
    """补全今天缺失的数据"""
    db = Database()
    now = beijing_time()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    print("=" * 80)
    print("补全今天的数据")
    print("=" * 80)
    print(f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"今天开始：{today_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 计算今天的所有10分钟段
    # 当前时间往前推10分钟（确保不包含正在进行的段）
    current_minute = now.minute
    current_segment_start_minute = (current_minute // 10) * 10
    latest_completed_segment_end = now.replace(
        minute=current_segment_start_minute,
        second=0,
        microsecond=0
    ) - timedelta(microseconds=1)
    
    # 从今天00:00:00开始，每10分钟一个段，到最近完成的段结束
    segments = []
    current_segment_start = today_start
    
    while current_segment_start < latest_completed_segment_end:
        current_segment_end = current_segment_start + timedelta(minutes=10) - timedelta(microseconds=1)
        segments.append((current_segment_start, current_segment_end))
        current_segment_start = current_segment_start + timedelta(minutes=10)
    
    print(f"需要补全的时间段数量：{len(segments)}")
    print(f"时间段范围：{segments[0][0].strftime('%H:%M:%S') if segments else '无'} - {segments[-1][1].strftime('%H:%M:%S') if segments else '无'}")
    print()
    
    if not segments:
        print("没有需要补全的数据（当前时间太早或没有完整的10分钟段）")
        return
    
    # 获取所有启用的店铺
    stores = db.get_active_stores()
    if not stores:
        print("没有启用的店铺")
        return
    
    print(f"活跃店铺数量：{len(stores)}")
    print()
    
    # ⚠️ 重要：先清空今天的数据，避免重复累加
    print("=" * 80)
    print("步骤1：清空今天的数据（避免重复累加）")
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
                count_sql = """
                    SELECT COUNT(*) as count FROM shoplazza_overview_hourly
                    WHERE DATE(time_hour) = DATE(%s)
                """
                cursor.execute(count_sql, (today_start,))
                count_result = cursor.fetchone()
                old_count = count_result['count'] if count_result else 0
                
                # 删除总店铺数据
                cursor.execute(delete_sql, (today_start,))
                deleted_overview = cursor.rowcount
                
                # 删除单店铺数据
                cursor.execute(delete_store_sql, (today_start,))
                deleted_store = cursor.rowcount
                
                conn.commit()
                print(f"已删除总店铺数据：{deleted_overview} 条")
                print(f"已删除单店铺数据：{deleted_store} 条")
                print()
    except Exception as e:
        logger.error(f"清空今天的数据失败: {e}")
        print(f"⚠️  清空数据失败: {e}")
        print("继续执行补全，但可能存在重复累加问题")
        print()
    
    # 优化：并行处理多个时间段，每个时间段内并行处理所有店铺
    # 设置并行时间段数量（可以根据实际情况调整）
    # 建议值：4-8个时间段并行，每个时间段内38个店铺并行
    # 总并发数 = PARALLEL_SEGMENTS * 38，建议不超过200
    if len(sys.argv) > 1:
        try:
            PARALLEL_SEGMENTS = int(sys.argv[1])
            if PARALLEL_SEGMENTS < 1:
                PARALLEL_SEGMENTS = 1
            elif PARALLEL_SEGMENTS > 10:
                PARALLEL_SEGMENTS = 10
                print(f"⚠️  并行数量超过限制，已调整为10")
        except ValueError:
            PARALLEL_SEGMENTS = 6
            print(f"⚠️  无效的并行数量参数，使用默认值6")
    else:
        PARALLEL_SEGMENTS = 6  # 默认同时处理6个时间段
    
    print(f"并行处理配置：同时处理 {PARALLEL_SEGMENTS} 个时间段")
    print(f"每个时间段内：38个店铺并行处理（10个线程）")
    print()
    total_segments = len(segments)
    completed_segments = 0
    
    def process_segment(segment_idx, start_time, end_time):
        """处理单个时间段的数据"""
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
    
    # 收集所有时间段的数据（分批并行处理）
    all_results = []
    segment_idx = 0
    
    print("=" * 80)
    print("步骤2：收集所有时间段的数据")
    print("=" * 80)
    
    while segment_idx < total_segments:
        # 获取当前批次的时间段（最多PARALLEL_SEGMENTS个）
        batch_segments = segments[segment_idx:segment_idx + PARALLEL_SEGMENTS]
        batch_size = len(batch_segments)
        
        print(f"正在并行处理 {batch_size} 个时间段: [{segment_idx+1}-{segment_idx+batch_size}]/{total_segments}")
        
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
        print(f"  进度: {segment_idx}/{total_segments} ({progress}%)")
    
    print()
    print("=" * 80)
    print("步骤3：按小时汇总所有数据并写入数据库")
    print("=" * 80)
    
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
        print(f"⚠️  有 {len(failed_segments)} 个时间段处理失败")
        print()
    
    # 计算每个小时的总访客数（所有店铺累加）
    for hour_start in all_hourly_data.keys():
        total_visitors = 0
        if hour_start in all_hourly_shop_visitors:
            # 累加所有店铺的访客数（不同店铺的访客是不同的IP）
            for shop_domain, visitors in all_hourly_shop_visitors[hour_start].items():
                total_visitors += visitors
        all_hourly_data[hour_start]['visitors'] = total_visitors
    
    # 一次性写入所有小时的数据（覆盖模式，因为已经清空了）
    print(f"正在写入总店铺数据：{len(all_hourly_data)} 个小时...")
    success_count = 0
    fail_count = 0
    
    # 写入总店铺数据
    for hour_start, data in sorted(all_hourly_data.items()):
        total_gmv = data['sales']
        total_orders = data['orders']
        total_visitors = data['visitors']
        avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
        
        # 使用覆盖模式（因为已经清空了今天的数据）
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
    
    print(f"总店铺数据写入完成：成功 {success_count} 条，失败 {fail_count} 条")
    print()
    
    # 写入单店铺数据
    print(f"正在写入单店铺数据...")
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
                gmv_from_analysis=0.0,  # 补全脚本不收集分析接口数据
                orders_from_analysis=0
            )
            
            if success:
                store_success_count += 1
            else:
                store_fail_count += 1
                logger.error(f"补全单店铺数据失败: {shop_domain} - {hour_start}")
    
    print(f"单店铺数据写入完成：成功 {store_success_count} 条，失败 {store_fail_count} 条")
    print()
    
    print()
    print("=" * 80)
    print("补全完成")
    print("=" * 80)
    print(f"共处理 {len(segments)} 个时间段")
    print(f"成功写入 {success_count} 个小时的数据")
    if fail_count > 0:
        print(f"⚠️  失败 {fail_count} 个小时的数据")
    if failed_segments:
        print(f"⚠️  有 {len(failed_segments)} 个时间段处理失败")
    
    # 更新同步状态
    # ⭐ 修复：使用最后一段的结束时间（而不是下一个段的开始时间）
    # 这样 sync_realtime_data_ten_minutes() 就能正确识别哪些段已经被处理过
    if segments:
        last_segment_end = segments[-1][1]  # 最后一段的结束时间（例如：10:09:59.999999）
        db.update_sync_status('ten_minute_realtime', last_segment_end, today_start.date())
        print(f"同步状态已更新，最后同步时间：{last_segment_end.strftime('%Y-%m-%d %H:%M:%S.%f')}")
    
    # 自动聚合今天的数据（幂等，重复聚合不会出错）
    print()
    print("=" * 80)
    print("开始聚合今天的数据...")
    print("=" * 80)
    try:
        conn_agg = db.get_connection()
        aggregate_date(conn_agg, today_start.date(), verbose=True)
        conn_agg.close()
        print(f"✅ 聚合任务完成: {today_start.date()}")
    except Exception as e:
        logger.error(f"聚合任务失败: {e}", exc_info=True)
        print(f"❌ 聚合任务失败: {e}")


if __name__ == '__main__':
    # 获取进程锁（必须在主逻辑开始前）
    lock_handle = acquire_lock()
    
    try:
        try:
            fill_today_data()
        except KeyboardInterrupt:
            print("\n用户中断操作")
        except Exception as e:
            logger.error(f"补全数据失败: {e}", exc_info=True)
            print(f"\n错误: {e}")
    finally:
        # 确保锁被释放
        if lock_handle:
            lock_handle.close()
            logger.info("进程锁已释放")

