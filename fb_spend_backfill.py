"""
回填 Facebook 广告花费历史（默认近 90 天），写入 fb_ad_account_spend_hourly
特性：
  - 多线程并发账户
  - 批量按天请求 insights（使用 breakdowns 获取24小时数据）
  - 带重试和代理支持
  - 实时写入，每完成一个账户就写入数据库
  - 进度显示
使用示例：
  python fb_spend_backfill.py --days 90
  python fb_spend_backfill.py --start 2025-09-10 --end 2025-12-08

注意：
  - 请确保 ad_account_owner_mapping 已导入
  - 请确保 fb_ad_account_spend_hourly 表已创建
  - Token 从环境变量 FB_LONG_LIVED_TOKEN 读取
  - 代理从环境变量 HTTP_PROXY/HTTPS_PROXY 读取
"""
import os
import argparse
import datetime
import time
import requests
import pymysql
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional

from config import DB_CONFIG
from timezone_utils import get_timezone_config, convert_to_beijing_time

API_VERSION = "v19.0"
MAX_RETRY = 3
RETRY_SLEEP = 3
MAX_WORKERS = 8  # 并发账户数，可视网络情况调整（API调用并发，写入已优化为批量）
MAX_POLL_ATTEMPTS = 30  # 异步报告最大轮询次数
POLL_INTERVAL = 5  # 轮询间隔（秒）


def get_proxy_settings() -> Optional[Dict]:
    """获取代理设置"""
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if http_proxy or https_proxy:
        return {
            "http": http_proxy,
            "https": https_proxy or http_proxy,
        }
    return None


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
    with conn.cursor() as cur:
        cur.execute("SELECT ad_account_id, owner FROM ad_account_owner_mapping")
        return cur.fetchall()


def call_insights(account_id: str, since: str, until: str, token: str, use_breakdowns: bool = True) -> List[Dict]:
    """
    调用 Graph API insights，按小时返回 spend（使用 breakdowns）
    注意：使用breakdowns时，Facebook可能返回异步报告，需要轮询获取结果
    对于历史数据，如果breakdowns失败，会降级到日汇总数据
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{account_id}/insights"
    
    if use_breakdowns:
        params = {
            "fields": "spend,account_id,account_name,date_start,date_stop",
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "level": "account",
            "breakdowns": "hourly_stats_aggregated_by_advertiser_time_zone",
            "access_token": token,
        }
    else:
        # 降级：不使用breakdowns，只获取日汇总数据
        params = {
            "fields": "spend,account_id,account_name,date_start,date_stop",
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "level": "account",
            "access_token": token,
        }
    
    proxies = get_proxy_settings()
    
    for i in range(MAX_RETRY):
        try:
            resp = requests.get(url, params=params, timeout=60, proxies=proxies)
            
            # 如果返回400错误，打印详细错误信息
            if resp.status_code == 400:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("error", {}).get("message", "未知错误")
                    error_code = error_data.get("error", {}).get("code", "")
                    print(f"[WARN] {account_id} {since}~{until} API错误 (code={error_code}): {error_msg}")
                    # 如果是breakdowns相关错误，尝试降级（但只有use_breakdowns=True时才降级）
                    if use_breakdowns and ("breakdowns" in error_msg.lower() or error_code in [100, 190]):
                        print(f"[INFO] {account_id} {since} breakdowns不支持，降级到日汇总数据")
                        return call_insights(account_id, since, until, token, use_breakdowns=False)
                except:
                    print(f"[WARN] {account_id} {since}~{until} 响应内容: {resp.text[:500]}")
                # 如果是breakdowns请求失败，尝试降级（但只有use_breakdowns=True时才降级）
                if use_breakdowns:
                    print(f"[INFO] {account_id} {since} 尝试降级到日汇总数据")
                    return call_insights(account_id, since, until, token, use_breakdowns=False)
                # 如果已经是日汇总模式还失败，直接返回空
                return []
            
            resp.raise_for_status()
            data = resp.json()

            # 检查是否是异步报告
            if "report_run_id" in data:
                report_run_id = data["report_run_id"]
                print(f"[INFO] {account_id} {since} 异步报告 {report_run_id} 开始轮询...")
                return poll_report_result(account_id, report_run_id, token, proxies)
            else:
                return data.get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"[ERR ] {account_id} {since}~{until} 请求失败 (尝试 {i+1}/{MAX_RETRY}): {e}")
            # 如果是breakdowns请求失败，尝试降级（但只有最后一次重试时才降级）
            if use_breakdowns and i == MAX_RETRY - 1:
                print(f"[INFO] {account_id} {since} 所有重试失败，尝试降级到日汇总数据")
                return call_insights(account_id, since, until, token, use_breakdowns=False)
        except Exception as e:
            print(f"[ERR ] {account_id} {since}~{until} 发生未知错误 (尝试 {i+1}/{MAX_RETRY}): {e}")
        time.sleep(RETRY_SLEEP)
    return []


def poll_report_result(account_id: str, report_run_id: str, token: str, proxies: Optional[Dict]) -> List[Dict]:
    """轮询异步报告结果"""
    url = f"https://graph.facebook.com/{API_VERSION}/{report_run_id}"
    params = {"access_token": token}
    
    for i in range(MAX_POLL_ATTEMPTS):
        try:
            time.sleep(POLL_INTERVAL)
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
            print(f"[WARN] {account_id} 轮询报告失败 (尝试 {i+1}/{MAX_POLL_ATTEMPTS}): {e}")
        except Exception as e:
            print(f"[ERR ] {account_id} 轮询报告异常 (尝试 {i+1}/{MAX_POLL_ATTEMPTS}): {e}")
    
    print(f"[WARN] {account_id} 报告轮询超时")
    return []


def upsert_spend(conn, rows: List[Tuple]):
    """
    写入 fb_ad_account_spend_hourly
    使用 REPLACE INTO 自动处理重复数据（先删除旧数据，再插入新数据）
    添加死锁重试机制，避免多线程并发写入时的死锁问题
    """
    if not rows:
        return
    
    sql = """
    REPLACE INTO fb_ad_account_spend_hourly
      (time_hour, ad_account_id, owner, spend, currency)
    VALUES (%s, %s, %s, %s, %s)
    """
    
    max_retries = 5
    retry_delay = 0.1  # 100毫秒
    
    for attempt in range(max_retries):
        try:
            with conn.cursor() as cur:
                # 分批写入，每批100条，减少死锁概率
                batch_size = 100
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]
                    cur.executemany(sql, batch)
            conn.commit()
            return  # 成功写入，退出
        except pymysql.err.OperationalError as e:
            error_code = e.args[0] if e.args else 0
            if error_code == 1213:  # Deadlock
                if attempt < max_retries - 1:
                    # 回滚事务
                    conn.rollback()
                    # 等待随机时间后重试（避免所有线程同时重试）
                    wait_time = retry_delay * (2 ** attempt) + (time.time() % 0.01)
                    time.sleep(wait_time)
                    continue
                else:
                    # 最后一次重试失败，抛出异常
                    print(f"[WARN] 写入数据时发生死锁，已重试 {max_retries} 次仍失败")
                    raise
            else:
                # 其他数据库错误，直接抛出
                raise
        except Exception as e:
            conn.rollback()
            raise


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


def process_account(account: Dict, dates: List[datetime.date], token: str) -> int:
    """
    处理单个账户的所有日期，收集完所有数据后一次性批量写入数据库
    优化策略：
    1. API调用保持并发（快速）
    2. 数据库写入改为批量（每个账户处理完所有日期后一次性写入）
    3. 大幅减少数据库写入次数，降低死锁概率（从90次/账户 → 1次/账户）
    返回写入的记录数
    """
    act_id = account["ad_account_id"]
    owner = account["owner"]
    if not act_id.startswith("act_"):
        act_id = f"act_{act_id}"
    
    # 获取账户时区配置（在函数开始时获取一次，避免重复查询）
    conn_for_tz = get_db_conn()
    try:
        timezone_config = get_timezone_config(conn_for_tz, act_id, owner, platform="facebook")
        timezone_offset = timezone_config["timezone_offset"]
    finally:
        conn_for_tz.close()
    
    print(f"[开始] {act_id} 处理 {len(dates)} 天数据... (时区: UTC{timezone_offset:+.1f})")
    
    # 先收集所有数据到内存，不立即写入数据库
    all_rows = []
    today = datetime.date.today()
    processed_dates = 0
    
    try:
        # 第一步：并发收集所有日期的数据（API调用）
        for idx, d in enumerate(dates, 1):
            since = until = d.strftime("%Y-%m-%d")
            # 对于超过30天的历史数据，直接使用日汇总（不尝试breakdowns，避免API错误）
            days_ago = (today - d).days
            use_breakdowns = days_ago <= 30  # 只对最近30天的数据使用breakdowns
            
            if idx % 10 == 0 or idx == 1:
                mode = "小时数据(breakdowns)" if use_breakdowns else "日汇总数据"
                print(f"[进度] {act_id} 处理日期 {idx}/{len(dates)}: {since} ({mode})")
            
            # 超过30天的数据，直接使用日汇总，不尝试breakdowns
            data = call_insights(act_id, since, until, token, use_breakdowns=use_breakdowns)
            
            # 调试：检查API返回的数据
            if data:
                print(f"[DEBUG] {act_id} {since} API返回 {len(data)} 条记录")
                if use_breakdowns:
                    # breakdowns数据：检查是否有重复的小时
                    hour_counts = {}
                    for r in data:
                        hour_str = r.get("hourly_stats_aggregated_by_advertiser_time_zone", "")
                        if hour_str:
                            hour_counts[hour_str] = hour_counts.get(hour_str, 0) + 1
                    duplicates = {h: c for h, c in hour_counts.items() if c > 1}
                    if duplicates:
                        print(f"[WARN] {act_id} {since} 发现重复的小时数据: {duplicates}")
                else:
                    # 日汇总数据：检查是否有多条记录
                    if len(data) > 1:
                        print(f"[WARN] {act_id} {since} 日汇总返回 {len(data)} 条记录（可能重复）")
                        for i, r in enumerate(data):
                            print(f"[DEBUG] {act_id} {since} 记录{i+1}: spend={r.get('spend')}, date_start={r.get('date_start')}, date_stop={r.get('date_stop')}")
            
            # 使用字典去重，避免重复数据累加
            seen_breakdowns = {}  # key: (time_hour, ad_account_id) for breakdowns数据
            seen_daily = set()  # key: (date_start, ad_account_id) for 日汇总数据
            
            rows = []
            for r in data:
                spend = float(r.get("spend", 0) or 0)
                currency = r.get("account_currency") or None
                # 解析小时字段：hourly_stats_aggregated_by_advertiser_time_zone = "00:00:00 - 00:59:59"
                hour_str = r.get("hourly_stats_aggregated_by_advertiser_time_zone", "")
                if hour_str:
                    # 有小时数据（breakdowns）：提取开始小时，例如 "00:00:00 - 00:59:59" -> "00:00:00"
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
                    if key not in seen_breakdowns:
                        seen_breakdowns[key] = (time_hour, act_id, owner, spend, currency)
                    else:
                        # 如果已存在，更新为最新的（覆盖旧数据）
                        print(f"[DEBUG] {act_id} {since} 发现重复的小时 {time_hour}，使用最新数据 spend={spend}")
                        seen_breakdowns[key] = (time_hour, act_id, owner, spend, currency)
                else:
                    # 没有小时数据（日汇总）：将总花费平均分配到24小时
                    # 去重：如果同一日期已处理过，跳过（只处理第一条记录）
                    date_start = r.get("date_start")
                    date_key = (date_start, act_id)
                    if date_key in seen_daily:
                        print(f"[WARN] {act_id} {since} 日汇总数据重复，跳过 spend={spend}")
                        continue
                    seen_daily.add(date_key)
                    
                    # 这是降级处理，虽然不够精确，但总比没有数据好
                    daily_spend = spend
                    hourly_spend = daily_spend / 24.0 if daily_spend > 0 else 0.0
                    # 构建账户时区的日期对象
                    date_obj_account_tz = datetime.datetime.strptime(date_start, "%Y-%m-%d")
                    for hour in range(24):
                        # 构建账户时区的小时时间
                        time_hour_account_tz = date_obj_account_tz.replace(hour=hour, minute=0, second=0)
                        # 转换为北京时间
                        time_hour = convert_to_beijing_time(time_hour_account_tz, timezone_offset)
                        rows.append((time_hour, act_id, owner, hourly_spend, currency))
            
            # 将去重后的breakdowns数据添加到rows
            rows.extend(seen_breakdowns.values())
            
            if rows:
                all_rows.extend(rows)
                processed_dates += 1
        
        # 第二步：所有数据收集完成后，一次性批量写入数据库
        if all_rows:
            print(f"[写入] {act_id} 开始批量写入 {len(all_rows)} 条数据到数据库...")
            conn = get_db_conn()
            try:
                upsert_spend(conn, all_rows)
                print(f"[完成] {act_id} 处理完成，写入 {len(all_rows)} 条数据（{processed_dates} 天有数据）")
                return len(all_rows)
            finally:
                conn.close()
        else:
            print(f"[完成] {act_id} 处理完成，无数据写入")
            return 0
            
    except Exception as e:
        print(f"[异常] {act_id} 处理出错: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90, help="回填天数，默认90天")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    args = parser.parse_args()

    token = os.getenv("FB_LONG_LIVED_TOKEN")
    if not token:
        print("缺少环境变量 FB_LONG_LIVED_TOKEN")
        return

    today = datetime.date.today()
    if args.start and args.end:
        start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        end_date = today
        start_date = end_date - datetime.timedelta(days=args.days - 1)

    dates = date_range(start_date, end_date)
    print(f"回填日期范围：{start_date} ~ {end_date} 共 {len(dates)} 天")
    print("=" * 80)

    conn = get_db_conn()
    try:
        # 步骤1：先清理指定日期范围内的旧数据（确保完全覆盖）
        print("步骤1：清理旧数据（避免残留错误数据）")
        print("=" * 80)
        clean_old_data(conn, start_date, end_date)
        print()
        
        accounts = fetch_accounts_with_owner(conn)
        if not accounts:
            print("映射表 ad_account_owner_mapping 为空，先导入映射数据")
            return

        print("步骤2：开始回填新数据")
        print("=" * 80)
        print(f"共 {len(accounts)} 个账户，开始回填...")
        total_written = 0
        
        # 注意：每个线程会创建自己的数据库连接，不需要主连接
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_account, acc, dates, token): acc for acc in accounts}
            for fut in as_completed(futures):
                acc = futures[fut]
                try:
                    count = fut.result()
                    total_written += count
                    print(f"[OK ] {acc['ad_account_id']} 完成 {count} 条")
                except Exception as e:
                    print(f"[ERR] {acc['ad_account_id']} error={e}")

        print(f"[DONE] 总写入 {total_written} 条")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

