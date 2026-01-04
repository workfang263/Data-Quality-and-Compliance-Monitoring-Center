import pymysql
from datetime import datetime, timezone, timedelta
import requests
import json
import time
import sys
import io

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

# --- 配置区 ---
# 数据库配置（请根据实际情况修改）
DB_CONFIG = {
    "host": "localhost",           # 数据库IP地址
    "port": 3306,                  # 数据库端口
    "user": "shoplazza_user",      # 数据库用户名
    "password": "123456",          # 数据库密码
    "database": "shoplazza_dashboard",  # 数据库名
    "charset": "utf8mb4"
}

# 钉钉 Webhook 地址
WEBHOOK_URL = "https://oapi.dingtalk.com/robot/send?access_token=c6b65b8d81265d2fdd3248e5a66ce4974ad4460a11e6ab4e9b303ab4aa1e3a2a"

# 监控的同步类型（对应 sync_status 表的 sync_type 字段）
SYNC_TYPE = "ten_minute_realtime"  # 10分钟实时同步

# 告警阈值（分钟）
ALERT_THRESHOLD_MINUTES = 20

def send_dingtalk_alert(msg):
    """发送钉钉告警消息"""
    try:
        data = {
            "msgtype": "text",
            "text": {"content": f"告警：{msg}"}  # 必须带"告警"关键词
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(WEBHOOK_URL, data=json.dumps(data), headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"[OK] 告警消息已发送: {msg}")
        else:
            print(f"[ERROR] 发送告警失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] 发送告警异常: {str(e)}")

def check_data_freshness():
    """检查数据同步状态"""
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
            # 1. 查询同步状态表的最后同步时间
            sql = """
                SELECT last_sync_end_time, updated_at 
                FROM sync_status 
                WHERE sync_type = %s
            """
            cursor.execute(sql, (SYNC_TYPE,))
            result = cursor.fetchone()

            if result is None:
                send_dingtalk_alert(f"[WARNING] 同步状态表未找到记录！sync_type={SYNC_TYPE}，请检查同步脚本是否正常运行。")
                print("[ERROR] 同步状态表未找到记录")
                return

            last_sync_time = result[0]
            
            if last_sync_time is None:
                send_dingtalk_alert(f"[WARNING] 同步状态表中 last_sync_end_time 为空！sync_type={SYNC_TYPE}，请检查同步脚本是否正常运行。")
                print("[ERROR] last_sync_end_time 为空")
                return

            # 2. 计算时间差（⚠️ 时区陷阱修复：数据库存储的是北京时间，不是 UTC）
            # 根据项目配置，数据库统一使用北京时间（UTC+8）
            # 所以直接用北京时间比较即可
            now_beijing = datetime.now()  # 本地时间（北京时间）
            
            # 数据库返回的 last_sync_time 是 naive datetime，假设它是北京时间
            # 直接计算时间差
            diff = (now_beijing - last_sync_time).total_seconds()
            diff_minutes = int(diff / 60)
            
            # 显示时间信息
            now_utc = datetime.utcnow()
            print(f"当前时间 (北京时间): {now_beijing.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"当前时间 (UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"最后同步时间 (北京时间): {last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"延迟时间: {diff_minutes} 分钟")

            # 3. 阈值判断：超过 20 分钟则报警
            if diff_minutes > ALERT_THRESHOLD_MINUTES:
                alert_msg = f"[ALERT] 数据同步脚本可能已停止运行！\n" \
                           f"同步类型: {SYNC_TYPE}\n" \
                           f"最后同步时间: {last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                           f"已延迟: {diff_minutes} 分钟（超过阈值 {ALERT_THRESHOLD_MINUTES} 分钟）\n" \
                           f"请立即检查同步脚本运行状态！"
                send_dingtalk_alert(alert_msg)
            else:
                print(f"[OK] 数据同步正常，延迟 {diff_minutes} 分钟（阈值: {ALERT_THRESHOLD_MINUTES} 分钟）")

    except Exception as e:
        error_msg = f"监控脚本自身报错: {str(e)}"
        print(f"[ERROR] {error_msg}")
        send_dingtalk_alert(error_msg)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_data_freshness()