"""
验证广告花费写库是否正确：
 1) 按日期、账户，直接调用 Graph API 获取 spend
 2) 对比数据库 fb_ad_account_spend_hourly 的存量
使用示例：
  python verify_fb_spend_data.py --date 2025-12-08
"""
import os
import argparse
import datetime
import time
import requests
import pymysql
from config import DB_CONFIG
from timezone_utils import get_timezone_config

API_VERSION = "v19.0"
MAX_RETRY = 2
RETRY_SLEEP = 2


def get_db_conn():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def call_insights(account_id: str, date: str, token: str) -> float:
    """
    调用 Graph API 获取日汇总 spend（用于验证，不需要breakdowns）
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{account_id}/insights"
    # 使用GET请求，参数放在URL中
    params = {
        "fields": "spend,date_start,date_stop",
        "time_range": f'{{"since":"{date}","until":"{date}"}}',
        "level": "account",
        "access_token": token,
    }
    # 获取代理设置（从环境变量）
    proxies = None
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    
    if http_proxy or https_proxy:
        # 如果使用SOCKS5代理，确保格式正确
        proxy_url = https_proxy or http_proxy
        if proxy_url and (proxy_url.startswith("socks5h://") or proxy_url.startswith("socks5://")):
            # requests库支持socks5://格式（需要安装requests[socks]）
            proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }
        elif proxy_url:
            # HTTP代理
            proxies = {
                "http": http_proxy or proxy_url,
                "https": https_proxy or http_proxy or proxy_url,
            }
    
    for i in range(MAX_RETRY):
        try:
            resp = requests.get(url, params=params, timeout=30, proxies=proxies)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    spend = float(data[0].get("spend", 0) or 0)
                    return spend
                else:
                    # 返回空数组，可能是当天没有花费
                    return 0.0
            else:
                print(f"[WARN] {account_id} {date} status={resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"[ERR ] {account_id} {date} {e}")
        time.sleep(RETRY_SLEEP)
    return 0.0


def fetch_db_spend(conn, account_id: str, date: str, owner: str = None, timezone_offset: float = None) -> float:
    """
    根据账户时区配置，查询数据库中对应账户时区日期的花费数据
    
    参数:
        account_id: 广告账户ID
        date: 账户时区的日期 (YYYY-MM-DD)
        owner: 负责人名称（用于获取时区配置）
        timezone_offset: 时区偏移量（如果已获取，直接传入）
    
    返回:
        该账户时区日期对应的总花费
    """
    # 如果没有传入时区偏移量，从数据库获取
    if timezone_offset is None:
        timezone_config = get_timezone_config(conn, account_id, owner, platform="facebook")
        timezone_offset = timezone_config["timezone_offset"]
    
    # 将账户时区的日期转换为北京时间的日期范围
    # 账户时区的开始时间：date 00:00:00
    account_date_start = datetime.datetime.strptime(f"{date} 00:00:00", "%Y-%m-%d %H:%M:%S")
    # 账户时区的结束时间：date 23:59:59
    account_date_end = datetime.datetime.strptime(f"{date} 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    # 转换为北京时间
    # 计算需要添加的小时数：8.0 - timezone_offset
    hours_to_add = 8.0 - timezone_offset
    beijing_start = account_date_start + datetime.timedelta(hours=hours_to_add)
    beijing_end = account_date_end + datetime.timedelta(hours=hours_to_add)
    
    # 查询数据库（数据库中的time_hour是北京时间）
    sql = """
    SELECT SUM(spend) AS s
    FROM fb_ad_account_spend_hourly
    WHERE ad_account_id=%s 
      AND time_hour >= %s 
      AND time_hour <= %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (account_id, beijing_start, beijing_end))
        row = cur.fetchone()
        return float(row["s"] or 0)


def fetch_accounts_with_owner(conn):
    """获取账户ID和负责人"""
    with conn.cursor() as cur:
        cur.execute("SELECT ad_account_id, owner FROM ad_account_owner_mapping")
        return cur.fetchall()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="日期 YYYY-MM-DD")
    args = parser.parse_args()

    # 默认使用本机代理（socks5h），便于在任务计划中也能走代理
    # 如果环境变量已设置，则使用环境变量的值；否则使用默认值
    os.environ.setdefault("HTTP_PROXY", "socks5h://127.0.0.1:10808")
    os.environ.setdefault("HTTPS_PROXY", "socks5h://127.0.0.1:10808")

    token = os.getenv("FB_LONG_LIVED_TOKEN")
    if not token:
        print("缺少环境变量 FB_LONG_LIVED_TOKEN")
        return

    conn = get_db_conn()
    try:
        accounts = fetch_accounts_with_owner(conn)
        if not accounts:
            print("映射表 ad_account_owner_mapping 为空")
            return

        date = args.date
        print(f"验证日期：{date}（账户时区）")
        print("=" * 100)
        print(f"{'广告账户ID':<25} {'负责人':<15} {'时区':<10} {'API花费':<15} {'数据库花费':<15} {'差异':<15} {'状态':<10}")
        print("-" * 100)
        
        ok_count = 0
        diff_count = 0
        
        for acc in accounts:
            act_id = acc["ad_account_id"]
            owner = acc["owner"]
            
            # 确保有 act_ 前缀
            if not act_id.startswith("act_"):
                act_id = f"act_{act_id}"
            
            # 获取账户时区配置
            timezone_config = get_timezone_config(conn, act_id, owner, platform="facebook")
            timezone_offset = timezone_config["timezone_offset"]
            timezone_str = f"UTC{timezone_offset:+.0f}"
            
            # 调用API获取花费（API返回的是账户时区的日汇总）
            api_spend = call_insights(act_id, date, token)
            
            # 查询数据库（根据时区配置转换日期范围）
            db_spend = fetch_db_spend(conn, act_id, date, owner, timezone_offset)
            
            diff = db_spend - api_spend
            if abs(diff) > 0.01:
                status = "[DIFF]"
                diff_count += 1
            else:
                status = "[OK]"
                ok_count += 1
            
            print(f"{act_id:<25} {owner:<15} {timezone_str:<10} {api_spend:>14.2f} {db_spend:>14.2f} {diff:>14.2f} {status:<10}")
        
        print("-" * 100)
        print(f"验证结果：✅ 一致 {ok_count} 个账户，⚠️  差异 {diff_count} 个账户")
        print("=" * 100)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

