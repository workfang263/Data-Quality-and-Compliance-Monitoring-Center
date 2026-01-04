"""
模拟数据生成脚本
使用随机游动算法（Random Walk）生成 90 天连续模拟数据

使用方法：
    python generate_mock_data.py

输出文件：
    db/seeds.sql - 追加模拟数据到现有 seeds.sql 文件

特点：
    - 日期范围：包含今天在内的过去 90 天
    - 数据算法：随机游动（Random Walk），确保数据有涨有跌
    - 时间连续性：每小时一个数据点，确保折线图平滑
    - 数据真实性：模拟真实的广告投放数据波动
"""
import os
import sys
import random
import math
from datetime import datetime, timedelta
from config import DB_CONFIG

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# 设置随机种子（确保每次生成的数据一致，便于演示）
random.seed(42)

# 输出文件
DB_DIR = 'db'
SEEDS_FILE = os.path.join(DB_DIR, 'seeds.sql')

def ensure_db_dir():
    """确保 db 目录存在"""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        print(f"✅ 创建目录: {DB_DIR}")

def random_walk(current_value, min_value, max_value, volatility=0.1):
    """
    随机游动算法（Random Walk）
    
    Args:
        current_value: 当前值
        min_value: 最小值
        max_value: 最大值
        volatility: 波动率（0.1 表示每次变化不超过 10%）
    
    Returns:
        新的值（在合理范围内）
    """
    # 计算变化幅度（基于当前值的百分比）
    change_percent = random.uniform(-volatility, volatility)
    new_value = current_value * (1 + change_percent)
    
    # 确保在合理范围内
    new_value = max(min_value, min(max_value, new_value))
    
    return new_value

def generate_hourly_data(start_date, days=90):
    """
    生成 90 天的小时级数据（使用随机游动算法）
    
    Args:
        start_date: 开始日期（90天前）
        days: 生成天数（默认90天）
    
    Returns:
        (overview_data, store_data) - 总店铺数据和单店铺数据
    """
    print(f"正在生成 {days} 天的模拟数据...")
    print(f"日期范围: {start_date.strftime('%Y-%m-%d')} 到 {(start_date + timedelta(days=days-1)).strftime('%Y-%m-%d')}")
    
    # 初始值（基准值）
    base_gmv = 5000.0  # 基准销售额（美元）
    base_orders = 50  # 基准订单数
    base_visitors = 200  # 基准访客数
    
    # 店铺数量
    num_stores = 10
    
    overview_data = []  # 总店铺小时数据
    store_data = []  # 单店铺小时数据
    
    # 为每个店铺维护独立的状态
    store_states = {}
    for i in range(num_stores):
        store_states[i] = {
            'gmv': base_gmv / num_stores * random.uniform(0.8, 1.2),
            'orders': base_orders / num_stores * random.uniform(0.8, 1.2),
            'visitors': base_visitors / num_stores * random.uniform(0.8, 1.2),
        }
    
    # 总店铺状态
    total_gmv = base_gmv
    total_orders = base_orders
    total_visitors = base_visitors
    
    # 遍历每一天
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        
        # 遍历每一小时（0-23）
        for hour in range(24):
            time_hour = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            # 模拟一天中的波动（白天高，夜间低）
            hour_factor = 0.3 + 0.7 * (1 - abs(hour - 12) / 12)  # 中午12点最高，凌晨最低
            
            # 模拟周末效应（周末数据略低）
            weekday_factor = 1.0 if current_date.weekday() < 5 else 0.85
            
            # 使用随机游动更新总店铺数据
            total_gmv = random_walk(total_gmv, 1000, 20000, volatility=0.15)
            total_orders = random_walk(total_orders, 10, 200, volatility=0.12)
            total_visitors = random_walk(total_visitors, 50, 1000, volatility=0.1)
            
            # 应用小时和周末因子
            final_gmv = total_gmv * hour_factor * weekday_factor
            final_orders = max(1, int(total_orders * hour_factor * weekday_factor))
            final_visitors = max(1, int(total_visitors * hour_factor * weekday_factor))
            
            # 计算客单价
            avg_order_value = final_gmv / final_orders if final_orders > 0 else 0
            
            # 总店铺数据
            overview_data.append({
                'time_hour': time_hour,
                'total_gmv': round(final_gmv, 2),
                'total_orders': final_orders,
                'total_visitors': final_visitors,
                'avg_order_value': round(avg_order_value, 2)
            })
            
            # 为每个店铺生成数据
            for store_idx in range(num_stores):
                store_domain = f'store_{["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa"][store_idx]}.myshoplaza.com'
                owner = f'Owner_{["A", "B", "C", "A", "B", "C", "A", "B", "C", "A"][store_idx]}'
                
                # 使用随机游动更新店铺数据
                state = store_states[store_idx]
                state['gmv'] = random_walk(state['gmv'], 100, 3000, volatility=0.2)
                state['orders'] = random_walk(state['orders'], 1, 30, volatility=0.18)
                state['visitors'] = random_walk(state['visitors'], 5, 150, volatility=0.15)
                
                # 应用小时和周末因子
                store_gmv = state['gmv'] * hour_factor * weekday_factor
                store_orders = max(0, int(state['orders'] * hour_factor * weekday_factor))
                store_visitors = max(0, int(state['visitors'] * hour_factor * weekday_factor))
                
                # 计算客单价
                store_avg_order_value = store_gmv / store_orders if store_orders > 0 else 0
                
                # 单店铺数据
                store_data.append({
                    'shop_domain': store_domain,
                    'time_hour': time_hour,
                    'owner': owner,
                    'total_gmv': round(store_gmv, 2),
                    'total_orders': store_orders,
                    'total_visitors': store_visitors,
                    'avg_order_value': round(store_avg_order_value, 2)
                })
    
    print(f"✅ 生成完成: {len(overview_data)} 条总店铺数据, {len(store_data)} 条单店铺数据")
    return overview_data, store_data

def generate_daily_summary_data(start_date, days=90):
    """
    生成 90 天的日汇总数据（owner_daily_summary）
    """
    print(f"正在生成 {days} 天的日汇总数据...")
    
    owners = ['Owner_A', 'Owner_B', 'Owner_C', 'Manager_01', 'Manager_02']
    daily_data = []
    
    # 为每个负责人维护独立的状态
    owner_states = {}
    for owner in owners:
        owner_states[owner] = {
            'gmv': random.uniform(2000, 8000),
            'orders': random.uniform(20, 80),
            'visitors': random.uniform(100, 400),
            'spend': random.uniform(500, 2000),
        }
    
    # 遍历每一天
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        
        # 模拟周末效应
        weekday_factor = 1.0 if current_date.weekday() < 5 else 0.85
        
        # 为每个负责人生成数据
        for owner in owners:
            state = owner_states[owner]
            
            # 使用随机游动更新
            state['gmv'] = random_walk(state['gmv'], 500, 15000, volatility=0.12)
            state['orders'] = random_walk(state['orders'], 5, 150, volatility=0.1)
            state['visitors'] = random_walk(state['visitors'], 50, 800, volatility=0.08)
            state['spend'] = random_walk(state['spend'], 100, 3000, volatility=0.15)
            
            # 应用周末因子
            final_gmv = state['gmv'] * weekday_factor
            final_orders = max(1, int(state['orders'] * weekday_factor))
            final_visitors = max(1, int(state['visitors'] * weekday_factor))
            final_spend = state['spend'] * weekday_factor
            
            # 计算客单价和 ROAS
            avg_order_value = final_gmv / final_orders if final_orders > 0 else 0
            roas = final_gmv / final_spend if final_spend > 0 else 0
            
            daily_data.append({
                'date': current_date.date(),
                'owner': owner,
                'total_gmv': round(final_gmv, 2),
                'total_orders': final_orders,
                'total_visitors': final_visitors,
                'avg_order_value': round(avg_order_value, 2),
                'total_spend': round(final_spend, 2),
                'roas': round(roas, 2)
            })
    
    print(f"✅ 生成完成: {len(daily_data)} 条日汇总数据")
    return daily_data

def write_sql_data(overview_data, store_data, daily_data):
    """
    将生成的数据写入 SQL 文件
    """
    print(f"\n正在写入数据到: {SEEDS_FILE}")
    
    # 读取现有文件（如果存在）
    existing_content = ""
    if os.path.exists(SEEDS_FILE):
        with open(SEEDS_FILE, 'r', encoding='utf-8') as f:
            existing_content = f.read()
    
    # 追加新数据
    with open(SEEDS_FILE, 'a', encoding='utf-8') as f:
        # 如果文件为空或没有数据部分，添加注释
        if '-- ==================== 模拟小时数据' not in existing_content:
            f.write("\n\n-- ==================== 模拟小时数据 ====================\n")
            f.write(f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- 数据范围: {overview_data[0]['time_hour'].strftime('%Y-%m-%d')} 到 {overview_data[-1]['time_hour'].strftime('%Y-%m-%d')}\n")
            f.write(f"-- 数据量: {len(overview_data)} 条总店铺数据, {len(store_data)} 条单店铺数据\n")
            f.write("-- ============================================\n\n")
        
        # 写入总店铺小时数据
        f.write("-- 总店铺小时汇总数据\n")
        f.write("INSERT INTO shoplazza_overview_hourly (time_hour, total_gmv, total_orders, total_visitors, avg_order_value) VALUES\n")
        
        overview_values = []
        for data in overview_data:
            overview_values.append(
                f"    ('{data['time_hour'].strftime('%Y-%m-%d %H:%M:%S')}', "
                f"{data['total_gmv']}, {data['total_orders']}, {data['total_visitors']}, {data['avg_order_value']})"
            )
        
        # 分批写入（每批1000条，避免SQL语句过长）
        batch_size = 1000
        for i in range(0, len(overview_values), batch_size):
            batch = overview_values[i:i+batch_size]
            f.write(",\n".join(batch))
            if i + batch_size < len(overview_values):
                f.write(",\n")
            else:
                f.write(";\n\n")
        
        # 写入单店铺小时数据
        f.write("-- 单店铺小时明细数据\n")
        f.write("INSERT INTO shoplazza_store_hourly (shop_domain, time_hour, owner, total_gmv, total_orders, total_visitors, avg_order_value) VALUES\n")
        
        store_values = []
        for data in store_data:
            store_values.append(
                f"    ('{data['shop_domain']}', "
                f"'{data['time_hour'].strftime('%Y-%m-%d %H:%M:%S')}', "
                f"'{data['owner']}', "
                f"{data['total_gmv']}, {data['total_orders']}, {data['total_visitors']}, {data['avg_order_value']})"
            )
        
        # 分批写入
        for i in range(0, len(store_values), batch_size):
            batch = store_values[i:i+batch_size]
            f.write(",\n".join(batch))
            if i + batch_size < len(store_values):
                f.write(",\n")
            else:
                f.write(";\n\n")
        
        # 写入日汇总数据
        f.write("-- 负责人日汇总数据\n")
        f.write("INSERT INTO owner_daily_summary (date, owner, total_gmv, total_orders, total_visitors, avg_order_value, total_spend, roas) VALUES\n")
        
        daily_values = []
        for data in daily_data:
            daily_values.append(
                f"    ('{data['date']}', "
                f"'{data['owner']}', "
                f"{data['total_gmv']}, {data['total_orders']}, {data['total_visitors']}, "
                f"{data['avg_order_value']}, {data['total_spend']}, {data['roas']})"
            )
        
        # 分批写入
        for i in range(0, len(daily_values), batch_size):
            batch = daily_values[i:i+batch_size]
            f.write(",\n".join(batch))
            if i + batch_size < len(daily_values):
                f.write(",\n")
            else:
                f.write(";\n\n")
    
    file_size = os.path.getsize(SEEDS_FILE)
    print(f"✅ 写入完成: {SEEDS_FILE} ({file_size:,} 字节)")

def main():
    """主函数"""
    print("="*60)
    print("模拟数据生成脚本（随机游动算法）")
    print("="*60)
    
    # 确保目录存在
    ensure_db_dir()
    
    # 计算日期范围：包含今天在内的过去 90 天
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = today - timedelta(days=89)  # 89天前到今天 = 90天
    
    print(f"📅 日期范围: {start_date.strftime('%Y-%m-%d')} 到 {today.strftime('%Y-%m-%d')} (共 90 天)")
    print(f"📊 数据点: 90 天 × 24 小时 = 2,160 个数据点")
    print("="*60)
    
    # 生成小时级数据
    overview_data, store_data = generate_hourly_data(start_date, days=90)
    
    # 生成日汇总数据
    daily_data = generate_daily_summary_data(start_date, days=90)
    
    # 写入 SQL 文件
    write_sql_data(overview_data, store_data, daily_data)
    
    print("\n" + "="*60)
    print("✅ 生成完成！")
    print("="*60)
    print(f"📄 数据文件: {SEEDS_FILE}")
    print(f"📊 总店铺数据: {len(overview_data)} 条")
    print(f"📊 单店铺数据: {len(store_data)} 条")
    print(f"📊 日汇总数据: {len(daily_data)} 条")
    print("\n💡 提示: 数据使用随机游动算法生成，具有真实的波动感")
    print("   折线图将显示平滑的曲线，有涨有跌，非常适合演示")
    print("="*60)

if __name__ == '__main__':
    main()

