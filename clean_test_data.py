"""
清理测试数据和异常数据
"""
import sys
import io
from datetime import datetime
from database import Database

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

db = Database()

print("=" * 80)
print("清理测试数据和异常数据")
print("=" * 80)
print()

# 1. 删除测试店铺的数据
print("1. 删除测试店铺的数据...")
try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            # 删除单店铺数据
            sql_store = """
                DELETE FROM shoplazza_store_hourly 
                WHERE shop_domain LIKE '%test%'
            """
            cursor.execute(sql_store)
            deleted_store = cursor.rowcount
            
            # 删除汇总数据中的测试店铺数据（需要重新计算）
            # 先删除16:00的异常数据
            sql_overview = """
                DELETE FROM shoplazza_overview_hourly 
                WHERE time_hour = '2025-12-31 16:00:00'
            """
            cursor.execute(sql_overview)
            deleted_overview = cursor.rowcount
            
            conn.commit()
            print(f"✅ 已删除测试店铺的单店铺数据: {deleted_store} 条")
            print(f"✅ 已删除16:00的异常汇总数据: {deleted_overview} 条")
except Exception as e:
    print(f"❌ 清理失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 80)
print("清理完成")
print("=" * 80)
print()
print("下一步操作:")
print("1. 重新收集今天的数据: python fill_today_data.py")
print("2. 运行聚合: python aggregate_owner_daily.py --date 2025-12-31")
print("3. 验证数据: python verify_today_data.py")

