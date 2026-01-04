"""
并发写入测试脚本

测试目标：
1. 模拟多个线程同时写入同一个小时的数据
2. 验证数据库的原子累加是否生效
3. 验证是否有数据丢失
"""
import sys
import os
from datetime import datetime, timedelta
from threading import Thread
import time
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from data_sync import process_ten_minute_segment, beijing_time
from unittest.mock import patch, MagicMock


def mock_sync_store_data(shop_domain: str, access_token: str, start_time: datetime, end_time: datetime):
    """模拟店铺数据收集（使用固定种子确保可重复）"""
    # 使用店铺域名作为种子，确保同一个店铺每次返回相同的数据
    random.seed(hash(shop_domain) % 10000)
    sales = random.uniform(50.0, 200.0)
    orders = random.randint(1, 10)
    visitors = random.randint(10, 100)
    
    return {
        'success': True,
        'sales': sales,
        'orders': orders,
        'visitors': visitors,
        'error': None
    }


def process_segment_concurrently(segment_start: datetime, segment_end: datetime, 
                                 thread_id: int, db: Database, results: list):
    """
    并发处理同一个10分钟段
    
    Args:
        segment_start: 段开始时间
        segment_end: 段结束时间
        thread_id: 线程ID
        db: 数据库实例
        results: 结果列表（用于收集每个线程的数据）
    """
    try:
        # 模拟店铺数据
        stores = [
            {'shop_domain': f'test_shop_{thread_id}_1.myshoplaza.com', 'access_token': 'token1'},
            {'shop_domain': f'test_shop_{thread_id}_2.myshoplaza.com', 'access_token': 'token2'},
        ]
        
        # 预先计算每个店铺的数据（使用固定种子确保可重复）
        store_data_map = {}
        thread_total_sales = 0.0
        thread_total_orders = 0
        thread_total_visitors = 0
        
        for store in stores:
            data = mock_sync_store_data(store['shop_domain'], store['access_token'], 
                                       segment_start, segment_end)
            store_data_map[store['shop_domain']] = data
            thread_total_sales += data['sales']
            thread_total_orders += data['orders']
            thread_total_visitors += data['visitors']
        
        # 记录线程的数据
        results.append({
            'thread_id': thread_id,
            'sales': thread_total_sales,
            'orders': thread_total_orders,
            'visitors': thread_total_visitors
        })
        
        # 创建固定的 mock 函数，返回预先计算的数据
        def fixed_mock_sync(shop_domain, access_token, start_time, end_time):
            return store_data_map.get(shop_domain, {
                'success': True,
                'sales': 0.0,
                'orders': 0,
                'visitors': 0,
                'error': None
            })
        
        # 使用 mock 处理段
        with patch('data_sync.sync_store_data_for_ten_minutes', side_effect=fixed_mock_sync):
            with patch.object(db, 'get_active_stores', return_value=stores):
                success = process_ten_minute_segment(segment_start, segment_end, db)
                
                if not success:
                    print(f"❌ 线程 {thread_id} 处理失败")
                    results.append({'thread_id': thread_id, 'error': '处理失败'})
        
    except Exception as e:
        print(f"❌ 线程 {thread_id} 发生异常: {e}")
        import traceback
        traceback.print_exc()
        results.append({'thread_id': thread_id, 'error': str(e)})


def test_concurrent_write():
    """测试并发写入"""
    print("=" * 80)
    print("并发写入测试")
    print("=" * 80)
    
    db = Database()
    test_time_hour = datetime(2025, 12, 31, 16, 0, 0)  # 测试用的小时：16:00:00
    segment_start = test_time_hour
    segment_end = segment_start + timedelta(minutes=10) - timedelta(microseconds=1)
    
    # 清理测试数据
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM shoplazza_overview_hourly WHERE time_hour = %s",
                    (test_time_hour,)
                )
                cursor.execute(
                    "DELETE FROM shoplazza_store_hourly WHERE time_hour = %s",
                    (test_time_hour,)
                )
                conn.commit()
    except Exception as e:
        print(f"清理测试数据失败: {e}")
    
    # 创建多个线程同时写入
    num_threads = 5
    threads = []
    results = []
    
    print(f"\n创建 {num_threads} 个线程，同时写入同一个小时的数据...")
    
    # 启动所有线程
    for i in range(num_threads):
        thread = Thread(
            target=process_segment_concurrently,
            args=(segment_start, segment_end, i, db, results)
        )
        threads.append(thread)
        thread.start()
        # 稍微延迟，增加并发冲突的可能性
        time.sleep(0.1)
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    print(f"\n所有线程执行完成")
    
    # 等待一下，确保数据库操作完成
    time.sleep(1)
    
    # 验证数据库中的数据
    existing_data = db.get_hourly_data_by_time(test_time_hour)
    
    if existing_data is None:
        print("❌ 数据库中没有找到汇总数据")
        return False
    
    actual_total_sales = float(existing_data['total_gmv'])
    actual_total_orders = int(existing_data['total_orders'])
    actual_total_visitors = int(existing_data['total_visitors'])
    
    # 计算所有线程的数据总和
    thread_data = [r for r in results if 'error' not in r]
    expected_total_sales = sum(r['sales'] for r in thread_data)
    expected_total_orders = sum(r['orders'] for r in thread_data)
    expected_total_visitors = sum(r['visitors'] for r in thread_data)
    
    print(f"\n{'='*80}")
    print("测试结果")
    print(f"{'='*80}")
    print(f"线程数量: {num_threads}")
    print(f"成功线程: {len(thread_data)}")
    print(f"\n期望值（所有线程数据总和）:")
    print(f"  销售额: ${expected_total_sales:.2f}")
    print(f"  订单数: {expected_total_orders}")
    print(f"  访客数: {expected_total_visitors}")
    print(f"\n实际值（数据库中的值）:")
    print(f"  销售额: ${actual_total_sales:.2f}")
    print(f"  订单数: {actual_total_orders}")
    print(f"  访客数: {actual_total_visitors}")
    
    # 验证数据一致性
    sales_diff = abs(actual_total_sales - expected_total_sales)
    orders_diff = abs(actual_total_orders - expected_total_orders)
    
    print(f"\n差异:")
    print(f"  销售额差异: ${sales_diff:.2f}")
    print(f"  订单数差异: {orders_diff}")
    
    # 允许小的浮点数误差（0.01）
    if sales_diff < 0.01 and orders_diff == 0:
        print(f"\n✅ 并发写入测试通过！")
        print(f"   数据库的原子累加正常工作，没有数据丢失")
        return True
    else:
        print(f"\n❌ 并发写入测试失败！")
        print(f"   数据不一致，可能存在数据丢失或重复累加问题")
        return False


if __name__ == '__main__':
    success = test_concurrent_write()
    sys.exit(0 if success else 1)

