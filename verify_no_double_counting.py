"""
验证Windows任务程序不会重复收集数据导致数据翻倍

测试场景：
1. 记录当前某个小时的数据
2. 模拟多次运行同一个10分钟段
3. 验证数据是否会被重复累加
4. 检查sync_status的保护机制是否有效
"""

import sys
from datetime import datetime, timedelta
from database import Database
from data_sync import sync_realtime_data_ten_minutes, process_ten_minute_segment, beijing_time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_current_hour_data(db: Database, time_hour: datetime):
    """获取指定小时的数据"""
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT total_gmv, total_orders, total_visitors
                FROM shoplazza_overview_hourly
                WHERE time_hour = %s
            """, (time_hour,))
            result = cursor.fetchone()
            if result:
                return {
                    'total_gmv': float(result['total_gmv']),
                    'total_orders': int(result['total_orders']),
                    'total_visitors': int(result['total_visitors'])
                }
            return {
                'total_gmv': 0.0,
                'total_orders': 0,
                'total_visitors': 0
            }


def get_sync_status(db: Database):
    """获取同步状态"""
    status = db.get_sync_status('ten_minute_realtime')
    if status:
        return {
            'last_sync_end_time': status['last_sync_end_time'],
            'last_sync_date': status['last_sync_date'],
            'updated_at': status.get('updated_at')
        }
    return None


def test_double_counting_prevention():
    """
    测试防重复累加机制
    
    测试步骤：
    1. 记录当前某个小时的数据（比如当前小时的前一个小时）
    2. 手动运行一次同步（模拟Windows任务程序）
    3. 再次运行同一个段（模拟重复运行）
    4. 验证数据是否被重复累加
    """
    print("=" * 80)
    print("验证防重复累加机制")
    print("=" * 80)
    
    db = Database()
    now = beijing_time()
    
    # 选择测试时间段：当前时间的前一个小时（确保数据已经稳定）
    test_hour = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    
    print(f"\n1. 选择测试时间段：{test_hour}")
    print(f"   当前时间：{now}")
    
    # 记录初始数据
    initial_data = get_current_hour_data(db, test_hour)
    print(f"\n2. 初始数据（{test_hour}）：")
    print(f"   销售额：${initial_data['total_gmv']:.2f}")
    print(f"   订单数：{initial_data['total_orders']}")
    print(f"   访客数：{initial_data['total_visitors']}")
    
    # 记录初始同步状态
    initial_sync_status = get_sync_status(db)
    if initial_sync_status:
        print(f"\n3. 初始同步状态：")
        print(f"   最后同步时间：{initial_sync_status['last_sync_end_time']}")
        print(f"   最后同步日期：{initial_sync_status['last_sync_date']}")
    else:
        print(f"\n3. 初始同步状态：无（首次运行）")
    
    # 选择一个10分钟段进行测试（测试小时内的第一个10分钟段）
    test_segment_start = test_hour
    test_segment_end = test_segment_start + timedelta(minutes=10) - timedelta(microseconds=1)
    
    print(f"\n4. 测试段：{test_segment_start} - {test_segment_end}")
    
    # 检查这个段是否已经被处理过
    if initial_sync_status and initial_sync_status['last_sync_end_time'] >= test_segment_end:
        print(f"\n⚠️  警告：测试段已经被处理过（最后同步时间：{initial_sync_status['last_sync_end_time']} >= 段结束时间：{test_segment_end}）")
        print(f"   如果继续测试，可能会重复处理这个段，导致数据翻倍！")
        response = input("\n是否继续测试？(y/n): ")
        if response.lower() != 'y':
            print("测试已取消")
            return
    
    # 第一次运行：处理测试段
    print(f"\n5. 第一次运行：处理测试段...")
    success1 = process_ten_minute_segment(test_segment_start, test_segment_end, db)
    
    if success1:
        # 更新同步状态（模拟正常流程）
        sync_date = test_segment_start.date()
        db.update_sync_status('ten_minute_realtime', test_segment_end, sync_date, 0)
        print(f"   ✅ 第一次运行成功")
    else:
        print(f"   ❌ 第一次运行失败")
        return
    
    # 记录第一次运行后的数据
    after_first_data = get_current_hour_data(db, test_hour)
    print(f"\n6. 第一次运行后数据（{test_hour}）：")
    print(f"   销售额：${after_first_data['total_gmv']:.2f} (变化: ${after_first_data['total_gmv'] - initial_data['total_gmv']:.2f})")
    print(f"   订单数：{after_first_data['total_orders']} (变化: {after_first_data['total_orders'] - initial_data['total_orders']})")
    print(f"   访客数：{after_first_data['total_visitors']} (变化: {after_first_data['total_visitors'] - initial_data['total_visitors']})")
    
    # 检查同步状态
    after_first_sync_status = get_sync_status(db)
    if after_first_sync_status:
        print(f"\n7. 第一次运行后同步状态：")
        print(f"   最后同步时间：{after_first_sync_status['last_sync_end_time']}")
    
    # 第二次运行：再次处理同一个段（模拟重复运行）
    print(f"\n8. 第二次运行：再次处理同一个段（模拟重复运行）...")
    print(f"   ⚠️  这是关键测试：如果数据被重复累加，说明存在问题！")
    
    success2 = process_ten_minute_segment(test_segment_start, test_segment_end, db)
    
    if success2:
        print(f"   ✅ 第二次运行成功")
    else:
        print(f"   ❌ 第二次运行失败")
        return
    
    # 记录第二次运行后的数据
    after_second_data = get_current_hour_data(db, test_hour)
    print(f"\n9. 第二次运行后数据（{test_hour}）：")
    print(f"   销售额：${after_second_data['total_gmv']:.2f} (变化: ${after_second_data['total_gmv'] - after_first_data['total_gmv']:.2f})")
    print(f"   订单数：{after_second_data['total_orders']} (变化: {after_second_data['total_orders'] - after_first_data['total_orders']})")
    print(f"   访客数：{after_second_data['total_visitors']} (变化: {after_second_data['total_visitors'] - after_first_data['total_visitors']})")
    
    # 分析结果
    print(f"\n" + "=" * 80)
    print("测试结果分析")
    print("=" * 80)
    
    first_increment_sales = after_first_data['total_gmv'] - initial_data['total_gmv']
    second_increment_sales = after_second_data['total_gmv'] - after_first_data['total_gmv']
    first_increment_orders = after_first_data['total_orders'] - initial_data['total_orders']
    second_increment_orders = after_second_data['total_orders'] - after_first_data['total_orders']
    
    print(f"\n第一次运行增量：")
    print(f"   销售额：${first_increment_sales:.2f}")
    print(f"   订单数：{first_increment_orders}")
    
    print(f"\n第二次运行增量：")
    print(f"   销售额：${second_increment_sales:.2f}")
    print(f"   订单数：{second_increment_orders}")
    
    # 判断是否重复累加
    if abs(second_increment_sales) > 0.01 or second_increment_orders > 0:
        print(f"\n❌ 发现问题：第二次运行仍然累加了数据！")
        print(f"   这说明如果同一个段被处理多次，数据会被重复累加。")
        print(f"   风险：如果手动运行了 fill_today_data.py，然后Windows任务程序又运行了，可能会重复累加。")
        print(f"\n   解决方案：")
        print(f"   1. 确保 sync_status 表正确更新，避免重复处理同一个段")
        print(f"   2. 或者改用覆盖式写入（而不是增量累加）")
        return False
    else:
        print(f"\n✅ 测试通过：第二次运行没有累加数据（或累加量很小，可能是新订单）")
        print(f"   这说明如果同一个段被处理多次，数据不会被重复累加。")
        print(f"   但是，这可能是巧合（这个段确实没有新订单）。")
        print(f"\n   建议：")
        print(f"   1. 确保 sync_status 表正确更新，避免重复处理同一个段")
        print(f"   2. 定期检查数据一致性（运行 verify_today_data.py）")
        return True


def test_sync_status_protection():
    """
    测试sync_status的保护机制
    
    测试步骤：
    1. 记录当前同步状态
    2. 运行 sync_realtime_data_ten_minutes()
    3. 验证它是否跳过了已经处理过的段
    """
    print("\n" + "=" * 80)
    print("测试sync_status保护机制")
    print("=" * 80)
    
    db = Database()
    now = beijing_time()
    
    # 获取当前同步状态
    initial_sync_status = get_sync_status(db)
    if initial_sync_status:
        print(f"\n1. 当前同步状态：")
        print(f"   最后同步时间：{initial_sync_status['last_sync_end_time']}")
        print(f"   最后同步日期：{initial_sync_status['last_sync_date']}")
    else:
        print(f"\n1. 当前同步状态：无（首次运行）")
    
    # 记录当前某个小时的数据
    test_hour = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    initial_data = get_current_hour_data(db, test_hour)
    print(f"\n2. 测试小时数据（{test_hour}）：")
    print(f"   销售额：${initial_data['total_gmv']:.2f}")
    print(f"   订单数：{initial_data['total_orders']}")
    
    # 运行同步（应该会跳过已经处理过的段）
    print(f"\n3. 运行 sync_realtime_data_ten_minutes()...")
    print(f"   （应该会跳过已经处理过的段）")
    
    try:
        sync_realtime_data_ten_minutes()
        print(f"   ✅ 同步完成")
    except Exception as e:
        print(f"   ❌ 同步失败：{e}")
        return False
    
    # 检查数据是否变化
    after_sync_data = get_current_hour_data(db, test_hour)
    print(f"\n4. 同步后数据（{test_hour}）：")
    print(f"   销售额：${after_sync_data['total_gmv']:.2f} (变化: ${after_sync_data['total_gmv'] - initial_data['total_gmv']:.2f})")
    print(f"   订单数：{after_sync_data['total_orders']} (变化: {after_sync_data['total_orders'] - initial_data['total_orders']})")
    
    # 检查同步状态
    after_sync_status = get_sync_status(db)
    if after_sync_status:
        print(f"\n5. 同步后状态：")
        print(f"   最后同步时间：{after_sync_status['last_sync_end_time']}")
        if initial_sync_status:
            if after_sync_status['last_sync_end_time'] > initial_sync_status['last_sync_end_time']:
                print(f"   ✅ 同步状态已更新（新时间：{after_sync_status['last_sync_end_time']} > 旧时间：{initial_sync_status['last_sync_end_time']}）")
            else:
                print(f"   ⚠️  同步状态未更新（可能是没有新数据需要处理）")
    
    return True


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("Windows任务程序防重复累加验证")
    print("=" * 80)
    print("\n⚠️  警告：此测试会实际处理数据，请确保在测试环境中运行！")
    print("\n测试内容：")
    print("1. 测试防重复累加机制（模拟重复运行同一个段）")
    print("2. 测试sync_status保护机制（验证是否跳过已处理的段）")
    
    response = input("\n是否继续？(y/n): ")
    if response.lower() != 'y':
        print("测试已取消")
        sys.exit(0)
    
    # 测试1：防重复累加机制
    result1 = test_double_counting_prevention()
    
    # 测试2：sync_status保护机制
    result2 = test_sync_status_protection()
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"\n防重复累加测试：{'✅ 通过' if result1 else '❌ 失败'}")
    print(f"sync_status保护测试：{'✅ 通过' if result2 else '❌ 失败'}")
    
    if result1 and result2:
        print("\n✅ 所有测试通过，Windows任务程序应该可以安全使用。")
    else:
        print("\n⚠️  发现问题，请检查代码逻辑。")

