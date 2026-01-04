"""
拉取指定日期的 Facebook 广告花费，写入 fb_ad_account_spend_hourly

使用方式（示例）：
  # 默认拉取今天
  python fb_spend_sync.py
  # 拉取指定日期
  python fb_spend_sync.py --date 2025-12-08
  # 传入开始/结束日期（闭区间），按天循环
  python fb_spend_sync.py --start 2025-12-06 --end 2025-12-08

前置要求：
  1) 环境变量 FB_LONG_LIVED_TOKEN 已配置（不要把 token 写死到代码里）
  2) 数据库表已创建：
     - fb_ad_account_spend_hourly
     - ad_account_owner_mapping
  3) 已导入广告账户 -> 负责人映射
"""
import os
import argparse
import datetime
import time
import requests
import pymysql
from typing import List, Dict, Optional, Tuple

# 聚合
from aggregate_owner_daily import aggregate_date

from config import DB_CONFIG  # 复用项目现有数据库配置
from timezone_utils import get_timezone_config, convert_to_beijing_time

# Graph API 版本
API_VERSION = "v19.0"
# 重试配置
MAX_RETRY = 3
RETRY_SLEEP = 3


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


def fetch_accounts_with_owner(conn) -> List[Dict]:
    """从映射表读取广告账户ID与负责人"""
    with conn.cursor() as cur:
        cur.execute("SELECT ad_account_id, owner FROM ad_account_owner_mapping")
        return cur.fetchall()


def call_insights(account_id: str, since: str, until: str, token: str) -> List[Dict]:
    """
    调用 Graph API insights，按小时返回 spend（使用 breakdowns）
    返回示例：
      [{"date_start":"2025-12-08","date_stop":"2025-12-08","account_id":"123","spend":"12.34","hourly_stats_aggregated_by_advertiser_time_zone":"00:00:00 - 00:59:59"}]
    
    注意：使用breakdowns时，Facebook可能返回异步报告，需要轮询获取结果
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{account_id}/insights"
    # 使用GET请求，参数放在URL中（Facebook推荐方式）
    params = {
        "fields": "spend,account_id,account_name,date_start,date_stop",
        "time_range": f'{{"since":"{since}","until":"{until}"}}',
        "level": "account",
        "breakdowns": "hourly_stats_aggregated_by_advertiser_time_zone",
        "access_token": token,
    }
    # 获取代理设置（从环境变量）
    proxies = None
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if http_proxy or https_proxy:
        proxies = {
            "http": http_proxy,
            "https": https_proxy or http_proxy,
        }
    
    for i in range(MAX_RETRY):
        try:
            # 使用GET请求
            resp = requests.get(url, params=params, timeout=60, proxies=proxies)
            if resp.status_code == 200:
                data = resp.json()
                # 检查是否是异步报告
                if "report_run_id" in data:
                    report_run_id = data["report_run_id"]
                    print(f"[INFO] {account_id} {since} 异步报告 {report_run_id} 开始轮询...")
                    # 轮询获取报告结果
                    return poll_report_result(account_id, report_run_id, token, proxies)
                result = data.get("data", [])
                if not result:
                    print(f"[DEBUG] {account_id} {since} API返回空数组，完整响应: {data}")
                return result
            else:
                print(f"[WARN] {account_id} {since}~{until} status={resp.status_code} resp={resp.text}")
        except Exception as e:
            print(f"[ERR ] {account_id} {since}~{until} error={e}")
        time.sleep(RETRY_SLEEP)
    return []


def poll_report_result(account_id: str, report_run_id: str, token: str, proxies: Optional[Dict]) -> List[Dict]:
    """
    轮询异步报告结果
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{report_run_id}"
    params = {"access_token": token}
    max_polls = 30  # 最多轮询30次
    poll_interval = 5  # 每次间隔5秒
    
    for i in range(max_polls):
        try:
            time.sleep(poll_interval)
            resp = requests.get(url, params=params, timeout=30, proxies=proxies)
            resp.raise_for_status()
            data = resp.json()
            
            # 检查报告状态
            async_percent = data.get("async_percent_completion", 0)
            status = data.get("async_status") or data.get("status")
            
            if status == "Job Completed" and async_percent == 100:
                # 报告完成，获取结果
                result_url = f"https://graph.facebook.com/{API_VERSION}/{report_run_id}/insights"
                result_resp = requests.get(result_url, params={"access_token": token}, timeout=30, proxies=proxies)
                result_resp.raise_for_status()
                result_data = result_resp.json()
                return result_data.get("data", [])
            elif status in ["Job Skipped", "Job Failed"]:
                print(f"[WARN] {account_id} 报告状态: {status}")
                return []
            # 还在处理中，继续等待
        except requests.exceptions.RequestException as e:
            print(f"[WARN] {account_id} 轮询报告失败 (尝试 {i+1}/{max_polls}): {e}")
        except Exception as e:
            print(f"[ERR ] {account_id} 轮询报告异常 (尝试 {i+1}/{max_polls}): {e}")
    
    print(f"[WARN] {account_id} 报告轮询超时")
    return []


def upsert_spend(conn, rows: List[Tuple]):
    """
    写入 fb_ad_account_spend_hourly
    使用 REPLACE INTO 自动处理重复数据（先删除旧数据，再插入新数据）
    rows: list of (time_hour, ad_account_id, owner, spend, currency)
    """
    if not rows:
        return
    sql = """
    REPLACE INTO fb_ad_account_spend_hourly
      (time_hour, ad_account_id, owner, spend, currency)
    VALUES (%s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()


def date_range(start: datetime.date, end: datetime.date) -> List[datetime.date]:
    days = (end - start).days
    return [start + datetime.timedelta(days=i) for i in range(days + 1)]


def clean_old_data(conn, start_date: datetime.date, end_date: datetime.date) -> int:
    """
    清理指定日期范围内的旧数据（先删除再写入，确保数据完全覆盖）
    返回删除的记录数
    """
    delete_sql = """
        DELETE FROM fb_ad_account_spend_hourly
        WHERE DATE(time_hour) >= %s AND DATE(time_hour) <= %s
    """
    
    try:
        with conn.cursor() as cur:
            # 先查询有多少条数据
            count_sql = """
                SELECT COUNT(*) as count FROM fb_ad_account_spend_hourly
                WHERE DATE(time_hour) >= %s AND DATE(time_hour) <= %s
            """
            cur.execute(count_sql, (start_date, end_date))
            count_result = cur.fetchone()
            old_count = count_result['count'] if count_result else 0
            
            # 删除旧数据
            cur.execute(delete_sql, (start_date, end_date))
            deleted_count = cur.rowcount
            
            conn.commit()
            
            print(f"[清理] 已删除 {start_date} ~ {end_date} 范围内的旧数据：{deleted_count} 条")
            return deleted_count
    except Exception as e:
        conn.rollback()
        print(f"[ERR ] 清理旧数据失败: {e}")
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="指定日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--incremental", action="store_true",
                        help="增量模式：不清理旧数据，只覆盖写入（定时任务推荐）")
    args = parser.parse_args()

    # 默认使用本机代理（socks5h），便于在任务计划中也能走代理
    os.environ.setdefault("HTTP_PROXY", "socks5h://127.0.0.1:10808")
    os.environ.setdefault("HTTPS_PROXY", "socks5h://127.0.0.1:10808")

    # 读取 Token
    token = os.getenv("FB_LONG_LIVED_TOKEN")
    if not token:
        print("缺少环境变量 FB_LONG_LIVED_TOKEN")
        return

    today = datetime.date.today()
    if args.date:
        start_date = end_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    elif args.start and args.end:
        start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        start_date = end_date = today

    dates = date_range(start_date, end_date)
    print(f"同步日期范围：{start_date} ~ {end_date} 共 {len(dates)} 天")
    print("=" * 80)

    conn = get_db_conn()
    try:
        # 步骤1：先清理指定日期范围内的旧数据（确保完全覆盖）
        if args.incremental:
            print("步骤1：增量模式（跳过清理，直接覆盖写入）")
            print("=" * 80)
        else:
            print("步骤1：清理旧数据（避免残留错误数据）")
            print("=" * 80)
            clean_old_data(conn, start_date, end_date)
            print()
        
        accounts = fetch_accounts_with_owner(conn)
        if not accounts:
            print("映射表 ad_account_owner_mapping 为空，先导入映射数据")
            return

        print("步骤2：开始同步新数据")
        print("=" * 80)
        for d in dates:
            since = until = d.strftime("%Y-%m-%d")
            rows = []
            for item in accounts:
                act_id = item["ad_account_id"]
                owner = item["owner"]
                # 确保有 act_ 前缀
                if not act_id.startswith("act_"):
                    act_id = f"act_{act_id}"
                
                # 获取账户时区配置（在循环外获取一次，避免重复查询）
                timezone_config = get_timezone_config(conn, act_id, owner, platform="facebook")
                timezone_offset = timezone_config["timezone_offset"]
                
                data = call_insights(act_id, since, until, token)
                if not data:
                    print(f"[DEBUG] {act_id} {since} 返回空数据")
                else:
                    print(f"[DEBUG] {act_id} {since} 返回 {len(data)} 条数据 (时区: UTC{timezone_offset:+.1f})")
                    
                    # 调试：检查是否有重复的小时数据
                    hour_counts = {}
                    for r in data:
                        hour_str = r.get("hourly_stats_aggregated_by_advertiser_time_zone", "")
                        if hour_str:
                            hour_counts[hour_str] = hour_counts.get(hour_str, 0) + 1
                    duplicates = {h: c for h, c in hour_counts.items() if c > 1}
                    if duplicates:
                        print(f"[WARN] {act_id} {since} 发现重复的小时数据: {duplicates}")
                
                # 使用字典去重，避免重复数据累加
                seen = {}  # key: (time_hour, ad_account_id)
                
                for r in data:
                    spend = float(r.get("spend", 0) or 0)
                    currency = r.get("account_currency") or None
                    # 解析小时字段：hourly_stats_aggregated_by_advertiser_time_zone = "00:00:00 - 00:59:59"
                    hour_str = r.get("hourly_stats_aggregated_by_advertiser_time_zone", "")
                    if hour_str:
                        # 提取开始小时，例如 "00:00:00 - 00:59:59" -> "00:00:00"
                        hour_start = hour_str.split(" - ")[0] if " - " in hour_str else hour_str
                        # 构建 time_hour：日期 + 小时（账户时区），例如 2025-12-08 00:00:00
                        time_hour_account_tz = datetime.datetime.strptime(
                            f"{r['date_start']} {hour_start}",
                            "%Y-%m-%d %H:%M:%S"
                        )
                        # 转换为北京时间
                        time_hour = convert_to_beijing_time(time_hour_account_tz, timezone_offset)
                        # 关键修复：使用账户时区的日期判断，而不是北京时间的日期
                        # 因为我们要同步的是账户时区d这一天的所有数据，不管转换后是北京时间哪一天
                        # Facebook API返回的date_start已经是账户时区的日期
                        if r['date_start'] != since:
                            # 跳过不属于请求日期（账户时区）的数据
                            continue
                        # 去重：如果同一小时已存在，使用最新的数据（覆盖）
                        key = (time_hour, act_id)
                        if key not in seen:
                            seen[key] = (time_hour, act_id, owner, spend, currency)
                        else:
                            # 如果已存在，更新为最新的（覆盖旧数据）
                            print(f"[DEBUG] {act_id} {since} 发现重复的小时 {time_hour}，使用最新数据 spend={spend}")
                            seen[key] = (time_hour, act_id, owner, spend, currency)
                    else:
                        # 如果没有小时字段（不应该发生，因为使用了breakdowns），使用当天 00:00:00
                        time_hour_account_tz = datetime.datetime.strptime(r["date_start"], "%Y-%m-%d")
                        # 转换为北京时间
                        time_hour = convert_to_beijing_time(time_hour_account_tz, timezone_offset)
                        key = (time_hour, act_id)
                        if key not in seen:
                            seen[key] = (time_hour, act_id, owner, spend, currency)
                        else:
                            print(f"[WARN] {act_id} {since} 发现重复的日汇总数据，跳过 spend={spend}")
                
                # 将去重后的数据添加到rows
                rows.extend(seen.values())

            upsert_spend(conn, rows)
            print(f"[OK ] {since} 写入 {len(rows)} 条")

            # 聚合：同步完成后立即聚合当前日期（幂等，重复聚合不会出错）
            try:
                aggregate_date(conn, d, verbose=False)
                print(f"[聚合] {since} 聚合完成")
            except Exception as e:
                print(f"[ERR] {since} 聚合失败: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

