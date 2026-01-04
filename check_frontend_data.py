"""
检查前端显示的数据来源
"""
import sys
import io
from datetime import datetime
from database import Database

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

db = Database()

# 查询今天的数据
today = datetime(2025, 12, 31, 0, 0, 0)
today_end = datetime(2025, 12, 31, 23, 59, 59)
today_data = db.get_hourly_data(today, today_end)
today_gmv = sum(float(d['total_gmv']) for d in today_data)
today_orders = sum(int(d['total_orders']) for d in today_data)
print(f"今天(2025-12-31)数据库数据: 订单数={today_orders}, 销售额=${today_gmv:.2f}")

# 查询昨天的数据
yesterday = datetime(2025, 12, 30, 0, 0, 0)
yesterday_end = datetime(2025, 12, 30, 23, 59, 59)
yesterday_data = db.get_hourly_data(yesterday, yesterday_end)
yesterday_gmv = sum(float(d['total_gmv']) for d in yesterday_data)
yesterday_orders = sum(int(d['total_orders']) for d in yesterday_data)
print(f"昨天(2025-12-30)数据库数据: 订单数={yesterday_orders}, 销售额=${yesterday_gmv:.2f}")

# 查询昨天+今天的数据
both_days_gmv = today_gmv + yesterday_gmv
both_days_orders = today_orders + yesterday_orders
print(f"昨天+今天(2025-12-30到2025-12-31)数据库数据: 订单数={both_days_orders}, 销售额=${both_days_gmv:.2f}")

# 前端显示的数据
frontend_gmv = 14084.66
frontend_orders = 232
print(f"\n前端显示的数据: 订单数={frontend_orders}, 销售额=${frontend_gmv:.2f}")

# 计算差异
print(f"\n差异分析:")
print(f"前端 - 今天: 订单数差异={frontend_orders - today_orders}, 销售额差异=${frontend_gmv - today_gmv:.2f}")
print(f"前端 - (昨天+今天): 订单数差异={frontend_orders - both_days_orders}, 销售额差异=${frontend_gmv - both_days_gmv:.2f}")

