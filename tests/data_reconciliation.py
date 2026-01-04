"""
数据对账脚本 - 测开核心技能：数据质量保证

功能：
1. 对比明细表（shoplazza_store_hourly）和汇总表（shoplazza_overview_hourly）的数据是否一致
2. 对比店铺明细汇总和总汇总表的金额是否对得上
3. 自动发现数据不一致问题并告警

这是测开的"后端自动化"核心技能
"""
import pymysql
from datetime import datetime, timedelta
import requests
import json
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG

# 钉钉 Webhook 地址
WEBHOOK_URL = "https://oapi.dingtalk.com/robot/send?access_token=c6b65b8d81265d2fdd3248e5a66ce4974ad4460a11e6ab4e9b303ab4aa1e3a2a"

# 对账日期（默认今天）
RECONCILIATION_DATE = datetime.now().date()

def send_dingtalk_alert(msg):
    """发送钉钉告警消息"""
    try:
        data = {
            "msgtype": "text",
            "text": {"content": f"告警：{msg}"}
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(WEBHOOK_URL, data=json.dumps(data), headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"✅ 告警消息已发送")
        else:
            print(f"❌ 发送告警失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 发送告警异常: {str(e)}")

def reconcile_hourly_data():
    """
    对账：对比明细表和汇总表的小时数据
    
    核心逻辑：
    - 明细表（shoplazza_store_hourly）：按店铺、按小时存储
    - 汇总表（shoplazza_overview_hourly）：按小时汇总所有店铺
    - 验证：SUM(明细表.总销售额) == 汇总表.总销售额
    """
    conn = None
    issues = []
    
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG.get('charset', 'utf8mb4')
        )
        
        print("=" * 80)
        print(f"数据对账 - {RECONCILIATION_DATE}")
        print("=" * 80)
        print()
        
        with conn.cursor() as cursor:
            # 1. 从明细表汇总（按小时）
            detail_sql = """
                SELECT 
                    time_hour,
                    SUM(total_gmv) as detail_total_gmv,
                    SUM(total_orders) as detail_total_orders,
                    MAX(total_visitors) as detail_total_visitors
                FROM shoplazza_store_hourly
                WHERE DATE(time_hour) = %s
                GROUP BY time_hour
                ORDER BY time_hour
            """
            cursor.execute(detail_sql, (RECONCILIATION_DATE,))
            detail_data = {row[0]: {
                'gmv': float(row[1] or 0),
                'orders': int(row[2] or 0),
                'visitors': int(row[3] or 0)
            } for row in cursor.fetchall()}
            
            # 2. 从汇总表查询（按小时）
            summary_sql = """
                SELECT 
                    time_hour,
                    total_gmv,
                    total_orders,
                    total_visitors
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = %s
                ORDER BY time_hour
            """
            cursor.execute(summary_sql, (RECONCILIATION_DATE,))
            summary_data = {row[0]: {
                'gmv': float(row[1] or 0),
                'orders': int(row[2] or 0),
                'visitors': int(row[3] or 0)
            } for row in cursor.fetchall()}
            
            # 3. 对比数据
            all_hours = set(detail_data.keys()) | set(summary_data.keys())
            
            if not all_hours:
                print("⚠️ 没有找到任何数据，可能今天还没有同步")
                return
            
            print(f"找到 {len(all_hours)} 个小时的数据点")
            print()
            
            mismatch_count = 0
            for hour in sorted(all_hours):
                detail = detail_data.get(hour, {'gmv': 0, 'orders': 0, 'visitors': 0})
                summary = summary_data.get(hour, {'gmv': 0, 'orders': 0, 'visitors': 0})
                
                # 允许的误差范围（浮点数精度问题）
                gmv_diff = abs(detail['gmv'] - summary['gmv'])
                orders_diff = abs(detail['orders'] - summary['orders'])
                visitors_diff = abs(detail['visitors'] - summary['visitors'])
                
                # 销售额差异超过 0.01 或订单数差异超过 0，视为不一致
                if gmv_diff > 0.01 or orders_diff > 0:
                    mismatch_count += 1
                    issue = {
                        'hour': hour,
                        'detail_gmv': detail['gmv'],
                        'summary_gmv': summary['gmv'],
                        'gmv_diff': gmv_diff,
                        'detail_orders': detail['orders'],
                        'summary_orders': summary['orders'],
                        'orders_diff': orders_diff
                    }
                    issues.append(issue)
                    
                    print(f"❌ {hour.strftime('%Y-%m-%d %H:00')} 数据不一致:")
                    print(f"   明细表: GMV={detail['gmv']:.2f}, 订单={detail['orders']}")
                    print(f"   汇总表: GMV={summary['gmv']:.2f}, 订单={summary['orders']}")
                    print(f"   差异: GMV={gmv_diff:.2f}, 订单={orders_diff}")
                    print()
            
            # 4. 输出汇总结果
            print("=" * 80)
            if mismatch_count == 0:
                print(f"✅ 数据对账通过！所有 {len(all_hours)} 个小时的数据都一致")
            else:
                print(f"❌ 发现 {mismatch_count} 个小时的数据不一致！")
                print()
                
                # 计算总差异
                total_gmv_diff = sum(abs(issue['gmv_diff']) for issue in issues)
                total_orders_diff = sum(abs(issue['orders_diff']) for issue in issues)
                
                alert_msg = f"🚨 数据对账失败！\n" \
                           f"日期: {RECONCILIATION_DATE}\n" \
                           f"不一致小时数: {mismatch_count}/{len(all_hours)}\n" \
                           f"总销售额差异: {total_gmv_diff:.2f}\n" \
                           f"总订单差异: {total_orders_diff}\n" \
                           f"请立即检查数据同步和聚合逻辑！"
                
                send_dingtalk_alert(alert_msg)
                print(f"已发送钉钉告警")
            
            print("=" * 80)
            
    except Exception as e:
        error_msg = f"数据对账脚本报错: {str(e)}"
        print(f"❌ {error_msg}")
        send_dingtalk_alert(error_msg)
    finally:
        if conn:
            conn.close()

def reconcile_daily_summary():
    """
    对账：对比店铺明细汇总和总汇总表的日数据
    
    核心逻辑：
    - 从明细表按天汇总：SUM(所有店铺的销售额)
    - 从汇总表按天汇总：SUM(所有小时的销售额)
    - 验证：两者应该相等
    """
    conn = None
    
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG.get('charset', 'utf8mb4')
        )
        
        with conn.cursor() as cursor:
            # 从明细表按天汇总
            detail_daily_sql = """
                SELECT 
                    SUM(total_gmv) as total_gmv,
                    SUM(total_orders) as total_orders,
                    MAX(total_visitors) as max_visitors
                FROM shoplazza_store_hourly
                WHERE DATE(time_hour) = %s
            """
            cursor.execute(detail_daily_sql, (RECONCILIATION_DATE,))
            detail_daily = cursor.fetchone()
            
            # 从汇总表按天汇总
            summary_daily_sql = """
                SELECT 
                    SUM(total_gmv) as total_gmv,
                    SUM(total_orders) as total_orders,
                    MAX(total_visitors) as max_visitors
                FROM shoplazza_overview_hourly
                WHERE DATE(time_hour) = %s
            """
            cursor.execute(summary_daily_sql, (RECONCILIATION_DATE,))
            summary_daily = cursor.fetchone()
            
            if detail_daily and summary_daily:
                detail_gmv = float(detail_daily[0] or 0)
                detail_orders = int(detail_daily[1] or 0)
                summary_gmv = float(summary_daily[0] or 0)
                summary_orders = int(summary_daily[1] or 0)
                
                gmv_diff = abs(detail_gmv - summary_gmv)
                orders_diff = abs(detail_orders - summary_orders)
                
                print(f"\n日汇总对账 ({RECONCILIATION_DATE}):")
                print(f"  明细表汇总: GMV={detail_gmv:.2f}, 订单={detail_orders}")
                print(f"  汇总表汇总: GMV={summary_gmv:.2f}, 订单={summary_orders}")
                print(f"  差异: GMV={gmv_diff:.2f}, 订单={orders_diff}")
                
                if gmv_diff > 0.01 or orders_diff > 0:
                    alert_msg = f"🚨 日汇总数据对账失败！\n" \
                               f"日期: {RECONCILIATION_DATE}\n" \
                               f"销售额差异: {gmv_diff:.2f}\n" \
                               f"订单差异: {orders_diff}"
                    send_dingtalk_alert(alert_msg)
                    return False
                else:
                    print(f"  ✅ 日汇总数据一致")
                    return True
            
    except Exception as e:
        print(f"❌ 日汇总对账报错: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # 支持命令行参数指定日期
    if len(sys.argv) > 1:
        try:
            RECONCILIATION_DATE = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
        except:
            print(f"❌ 日期格式错误，使用默认日期: {RECONCILIATION_DATE}")
    
    print(f"开始数据对账，日期: {RECONCILIATION_DATE}")
    print()
    
    # 执行小时级对账
    reconcile_hourly_data()
    
    # 执行日汇总对账
    reconcile_daily_summary()

