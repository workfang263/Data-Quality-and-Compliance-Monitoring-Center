"""
数据库监控守护进程 - 持续运行，定期检查

这是"守护进程"的经典实现：
1. 持续运行（while True）
2. 定期执行检查（每5分钟）
3. 异常自动恢复（try-except）
4. 优雅退出（Ctrl+C）

学习点：
- 如何写一个 Python 守护进程
- 如何定期检查数据库 updated_at 时间
- 如何实现优雅退出
"""
import pymysql
from datetime import datetime
import requests
import json
import time
import signal
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG

# 钉钉 Webhook 地址
WEBHOOK_URL = "https://oapi.dingtalk.com/robot/send?access_token=c6b65b8d81265d2fdd3248e5a66ce4974ad4460a11e6ab4e9b303ab4aa1e3a2a"

# 监控的同步类型
SYNC_TYPE = "ten_minute_realtime"

# 告警阈值（分钟）
ALERT_THRESHOLD_MINUTES = 20

# 检查间隔（秒）
CHECK_INTERVAL = 300  # 5分钟检查一次

# 全局标志，用于优雅退出
running = True

def signal_handler(sig, frame):
    """处理 Ctrl+C 信号，实现优雅退出"""
    global running
    print("\n收到退出信号，正在优雅退出...")
    running = False

def send_dingtalk_alert(msg):
    """发送钉钉告警消息"""
    try:
        data = {
            "msgtype": "text",
            "text": {"content": f"告警：{msg}"}
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(WEBHOOK_URL, data=json.dumps(data), headers=headers, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 发送告警异常: {str(e)}")
        return False

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
            sql = """
                SELECT last_sync_end_time, updated_at 
                FROM sync_status 
                WHERE sync_type = %s
            """
            cursor.execute(sql, (SYNC_TYPE,))
            result = cursor.fetchone()

            if result is None:
                send_dingtalk_alert(f"⚠️ 同步状态表未找到记录！sync_type={SYNC_TYPE}")
                return False

            last_sync_time = result[0]
            
            if last_sync_time is None:
                send_dingtalk_alert(f"⚠️ 同步状态表中 last_sync_end_time 为空！sync_type={SYNC_TYPE}")
                return False

            # 计算时间差（数据库存储的是北京时间）
            now_beijing = datetime.now()
            diff = (now_beijing - last_sync_time).total_seconds()
            diff_minutes = int(diff / 60)

            # 阈值判断
            if diff_minutes > ALERT_THRESHOLD_MINUTES:
                alert_msg = f"🚨 数据同步脚本可能已停止运行！\n" \
                           f"同步类型: {SYNC_TYPE}\n" \
                           f"最后同步时间: {last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                           f"已延迟: {diff_minutes} 分钟（超过阈值 {ALERT_THRESHOLD_MINUTES} 分钟）\n" \
                           f"请立即检查同步脚本运行状态！"
                send_dingtalk_alert(alert_msg)
                return False
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 数据同步正常，延迟 {diff_minutes} 分钟")
                return True

    except Exception as e:
        error_msg = f"监控脚本自身报错: {str(e)}"
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ {error_msg}")
        send_dingtalk_alert(error_msg)
        return False
    finally:
        if conn:
            conn.close()

def main():
    """主函数：守护进程循环"""
    global running
    
    # 注册信号处理器（优雅退出）
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 80)
    print("数据库监控守护进程启动")
    print("=" * 80)
    print(f"监控类型: {SYNC_TYPE}")
    print(f"告警阈值: {ALERT_THRESHOLD_MINUTES} 分钟")
    print(f"检查间隔: {CHECK_INTERVAL} 秒")
    print("按 Ctrl+C 退出")
    print("=" * 80)
    print()
    
    check_count = 0
    
    while running:
        try:
            check_count += 1
            print(f"[检查 #{check_count}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            check_data_freshness()
            
            # 等待下一次检查
            # 使用分段等待，以便能够响应退出信号
            wait_time = 0
            while wait_time < CHECK_INTERVAL and running:
                time.sleep(1)
                wait_time += 1
            
            if running:
                print()  # 空行分隔
            
        except KeyboardInterrupt:
            # 这个应该不会触发，因为信号处理器已经处理了
            break
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 守护进程异常: {str(e)}")
            time.sleep(60)  # 异常后等待1分钟再继续
    
    print()
    print("=" * 80)
    print("守护进程已退出")
    print("=" * 80)

if __name__ == "__main__":
    main()

