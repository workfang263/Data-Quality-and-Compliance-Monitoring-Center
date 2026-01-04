"""
检查同步状态
"""
import sys
import io
from datetime import datetime
from database import Database
from utils import beijing_time

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

db = Database()
now = beijing_time()

print("=" * 80)
print("同步状态检查")
print("=" * 80)
print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 检查旧的同步类型
old_status = db.get_sync_status('five_minute_realtime')
if old_status:
    print("旧的同步类型 (five_minute_realtime):")
    print(f"  最后同步时间: {old_status['last_sync_end_time']}")
    print(f"  同步日期: {old_status.get('sync_date')}")
    time_diff = now - old_status['last_sync_end_time']
    print(f"  距现在: {int(time_diff.total_seconds()/60)} 分钟")
    print()

# 检查新的同步类型
new_status = db.get_sync_status('ten_minute_realtime')
if new_status:
    print("新的同步类型 (ten_minute_realtime):")
    print(f"  最后同步时间: {new_status['last_sync_end_time']}")
    print(f"  同步日期: {new_status.get('sync_date')}")
    time_diff = now - new_status['last_sync_end_time']
    print(f"  距现在: {int(time_diff.total_seconds()/60)} 分钟")
    if time_diff.total_seconds() > 600:  # 超过10分钟
        print(f"  ⚠️  警告：最后同步时间距现在已过去 {int(time_diff.total_seconds()/60)} 分钟")
    else:
        print(f"  ✅ 同步状态正常")
else:
    print("新的同步类型 (ten_minute_realtime): 未找到记录")
    print()

print("=" * 80)
print("结论")
print("=" * 80)
if old_status and not new_status:
    print("⚠️  问题：验证脚本查询的是旧的同步类型 (five_minute_realtime)")
    print("   但实际使用的是新的同步类型 (ten_minute_realtime)")
    print("   需要更新验证脚本")
elif new_status:
    time_diff = now - new_status['last_sync_end_time']
    if time_diff.total_seconds() > 600:
        print("⚠️  警告：同步状态显示最后同步时间距现在已过去超过10分钟")
        print("   可能原因：")
        print("   1. Windows任务程序没有正常执行")
        print("   2. 脚本执行失败")
        print("   3. 同步状态更新失败")
    else:
        print("✅ 同步状态正常")
