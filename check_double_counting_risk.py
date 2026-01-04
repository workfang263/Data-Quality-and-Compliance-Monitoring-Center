"""
检查Windows任务程序是否存在重复累加数据的风险

分析：
1. fill_today_data.py 使用覆盖模式（不会重复累加）
2. sync_realtime_data_ten_minutes() 使用增量累加模式（可能重复累加）
3. 如果两个脚本处理了同一个段，可能会导致数据翻倍

检查点：
1. sync_status 的更新逻辑是否一致
2. 是否存在时间格式不一致的问题
3. 是否有保护机制防止重复处理
"""

import sys
from datetime import datetime, timedelta
from database import Database
from data_sync import beijing_time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_sync_status_consistency():
    """检查sync_status的一致性"""
    print("=" * 80)
    print("检查sync_status一致性")
    print("=" * 80)
    
    db = Database()
    sync_status = db.get_sync_status('ten_minute_realtime')
    
    if not sync_status:
        print("\n⚠️  警告：sync_status不存在，这是首次运行")
        print("   建议：先运行一次 fill_today_data.py 或 sync_realtime_data_ten_minutes()")
        return False
    
    last_sync_end_time = sync_status['last_sync_end_time']
    last_sync_date = sync_status['last_sync_date']
    updated_at = sync_status.get('updated_at')
    
    print(f"\n当前sync_status：")
    print(f"   最后同步时间：{last_sync_end_time}")
    print(f"   最后同步日期：{last_sync_date}")
    print(f"   更新时间：{updated_at}")
    
    # 检查时间格式
    now = beijing_time()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 检查是否是旧格式（整点格式）
    if last_sync_end_time.second == 0 and last_sync_end_time.microsecond == 0:
        print(f"\n⚠️  警告：检测到旧格式同步状态（整点格式）")
        print(f"   这可能导致重复处理。")
        print(f"   建议：运行 sync_realtime_data_ten_minutes() 会自动转换格式")
        return False
    
    # 检查是否是今天的
    if last_sync_date != today_start.date():
        print(f"\n⚠️  警告：最后同步日期不是今天")
        print(f"   这可能导致重复处理今天的数据。")
        return False
    
    # 检查时间是否合理（不应该超过当前时间）
    if last_sync_end_time > now:
        print(f"\n❌ 错误：最后同步时间超过当前时间！")
        print(f"   这可能导致数据问题。")
        return False
    
    # 检查时间是否太旧（超过1小时）
    time_diff = now - last_sync_end_time
    if time_diff > timedelta(hours=1):
        print(f"\n⚠️  警告：最后同步时间距现在已过去 {time_diff}")
        print(f"   这可能说明Windows任务程序没有正常运行。")
        return False
    
    print(f"\n✅ sync_status检查通过")
    return True


def check_data_consistency():
    """检查数据一致性（对比API和数据库）"""
    print("\n" + "=" * 80)
    print("检查数据一致性")
    print("=" * 80)
    
    print("\n建议运行以下命令来检查数据一致性：")
    print("   python verify_today_data.py")
    print("\n如果数据一致，说明没有重复累加问题。")
    print("如果数据不一致（数据库 > API），可能存在重复累加问题。")


def check_writing_mode():
    """检查写入模式"""
    print("\n" + "=" * 80)
    print("检查写入模式")
    print("=" * 80)
    
    print("\n当前写入模式：")
    print("   1. fill_today_data.py：覆盖模式（insert_or_update_hourly_data）")
    print("      ✅ 不会重复累加（因为会覆盖）")
    print("   2. sync_realtime_data_ten_minutes()：增量累加模式（insert_or_update_hourly_data_incremental）")
    print("      ⚠️  可能重复累加（如果同一个段被处理多次）")
    
    print("\n风险分析：")
    print("   如果手动运行了 fill_today_data.py，然后Windows任务程序又运行了，")
    print("   可能会重复处理某些段，导致数据被重复累加。")
    
    print("\n保护机制：")
    print("   1. sync_status 表记录最后同步时间，避免重复处理")
    print("   2. 进程锁防止多个进程同时运行")
    print("   3. 时间验证确保只处理时间范围内的订单")
    
    print("\n⚠️  潜在风险：")
    print("   如果 fill_today_data.py 更新 sync_status 的时间格式不一致，")
    print("   可能导致 sync_realtime_data_ten_minutes() 认为某些段还没有被处理，")
    print("   从而重复处理，导致数据被重复累加。")


def check_sync_status_format():
    """检查sync_status的时间格式"""
    print("\n" + "=" * 80)
    print("检查sync_status时间格式")
    print("=" * 80)
    
    db = Database()
    sync_status = db.get_sync_status('ten_minute_realtime')
    
    if not sync_status:
        print("\n⚠️  警告：sync_status不存在")
        return
    
    last_sync_end_time = sync_status['last_sync_end_time']
    
    print(f"\n当前sync_status时间：{last_sync_end_time}")
    print(f"   秒数：{last_sync_end_time.second}")
    print(f"   微秒数：{last_sync_end_time.microsecond}")
    
    # 检查格式
    if last_sync_end_time.second == 0 and last_sync_end_time.microsecond == 0:
        print(f"\n❌ 问题：检测到旧格式（整点格式）")
        print(f"   fill_today_data.py 使用的是段的开始时间（整点），")
        print(f"   而 sync_realtime_data_ten_minutes() 期望的是段的结束时间（带秒和微秒）。")
        print(f"   这可能导致重复处理。")
        print(f"\n   解决方案：")
        print(f"   1. 运行 sync_realtime_data_ten_minutes() 会自动转换格式")
        print(f"   2. 或者修改 fill_today_data.py 使用段的结束时间")
    else:
        print(f"\n✅ 格式正确（段的结束时间格式）")


def provide_recommendations():
    """提供建议"""
    print("\n" + "=" * 80)
    print("建议")
    print("=" * 80)
    
    print("\n1. 启用Windows任务程序前，确保：")
    print("   ✅ sync_status 存在且格式正确")
    print("   ✅ 数据一致性验证通过（运行 verify_today_data.py）")
    print("   ✅ 进程锁机制正常工作")
    
    print("\n2. 启用Windows任务程序后，定期检查：")
    print("   ✅ 运行 verify_today_data.py 检查数据一致性")
    print("   ✅ 检查日志文件，确认没有重复处理的警告")
    print("   ✅ 检查 sync_status 是否正常更新")
    
    print("\n3. 如果发现数据翻倍问题：")
    print("   ✅ 立即停止Windows任务程序")
    print("   ✅ 运行 fill_today_data.py 重新收集今天的数据（覆盖模式）")
    print("   ✅ 检查 sync_status 的时间格式是否正确")
    print("   ✅ 修复问题后，重新启用Windows任务程序")
    
    print("\n4. 最佳实践：")
    print("   ✅ 避免手动运行 fill_today_data.py 和 Windows任务程序同时运行")
    print("   ✅ 如果手动运行了 fill_today_data.py，等待它完成后再启用Windows任务程序")
    print("   ✅ 定期检查数据一致性（每天至少一次）")


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("Windows任务程序重复累加风险检查")
    print("=" * 80)
    
    # 检查1：sync_status一致性
    status_ok = check_sync_status_consistency()
    
    # 检查2：sync_status格式
    check_sync_status_format()
    
    # 检查3：写入模式
    check_writing_mode()
    
    # 检查4：数据一致性
    check_data_consistency()
    
    # 建议
    provide_recommendations()
    
    # 总结
    print("\n" + "=" * 80)
    print("检查总结")
    print("=" * 80)
    
    if status_ok:
        print("\n✅ 基本检查通过，但建议：")
        print("   1. 运行 verify_today_data.py 验证数据一致性")
        print("   2. 启用Windows任务程序后，定期检查数据")
    else:
        print("\n⚠️  发现问题，请先修复后再启用Windows任务程序")

