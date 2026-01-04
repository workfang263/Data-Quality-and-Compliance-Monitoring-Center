"""
回填 TikTok 广告花费历史数据
特性：
  - 多线程并发账户
  - 30天内：按小时收集（使用 stat_time_hour）
  - 30-90天：按日收集（使用 stat_time_day，避免API限制）
  - 带重试和代理支持
  - 实时写入，每完成一个账户就写入数据库
  - 进度显示
使用示例：
  python tt_spend_backfill.py --days 90
  python tt_spend_backfill.py --start 2025-09-10 --end 2025-12-08

注意：
  - 请确保 tt_ad_account_owner_mapping 已导入
  - 请确保 tt_ad_account_spend_hourly 表已创建
  - Token 从 config.py 的 TT_CONFIG 读取
  - 代理从 config.py 的 TT_CONFIG 读取
"""
import argparse
import datetime
import time
import requests
import pymysql
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional

from config import DB_CONFIG, TT_CONFIG

MAX_RETRY = 3
RETRY_SLEEP = 3
MAX_WORKERS = 5  # 并发账户数，可视网络情况调整（TikTok API 限制较严格，建议不超过5）


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
        cur.execute("SELECT ad_account_id, owner FROM tt_ad_account_owner_mapping")
        return cur.fetchall()


def get_token_for_account(advertiser_id: str) -> Optional[str]:
    """根据广告账户ID查找对应的 Business Center Token"""
    business_centers = TT_CONFIG.get("business_centers", [])
    for bc in business_centers:
        if advertiser_id in bc.get("advertiser_ids", []):
            return bc.get("access_token")
    return None


def call_tiktok_report(advertiser_id: str, start_date: str, end_date: str, 
                       access_token: str, dimensions: str = '["stat_time_hour"]') -> List[Dict]:
    """
    调用 TikTok Marketing API 获取报表数据
    返回示例：
      [{"dimensions": {"stat_time_hour": "2025-12-08 00:00:00"}, "metrics": {"spend": "12.34"}}]
    """
    url = f"{TT_CONFIG['base_url']}/report/integrated/get/"
    
    params = {
        "advertiser_id": advertiser_id,
        "service_type": "AUCTION",
        "report_type": "BASIC",
        "data_level": "AUCTION_ADVERTISER",
        "dimensions": dimensions,  # 小时级：'["stat_time_hour"]'，日级：'["stat_time_day"]'
        "metrics": '["spend"]',
        "start_date": start_date,
        "end_date": end_date,
        "page_size": 200,
    }
    
    headers = {
        "Access-Token": access_token,
        "Accept": "application/json",
        "User-Agent": "python-requests",
    }
    
    proxies = TT_CONFIG.get("proxies")
    
    for i in range(MAX_RETRY):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=headers,
                proxies=proxies,
                timeout=TT_CONFIG.get("timeout", 20)
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    result = data.get("data", {}).get("list", [])
                    return result
                else:
                    print(f"[WARN] {advertiser_id} {start_date} API错误: {data.get('message')}")
                    return []
            else:
                print(f"[WARN] {advertiser_id} {start_date}~{end_date} status={resp.status_code} resp={resp.text[:200]}")
        except Exception as e:
            print(f"[ERR ] {advertiser_id} {start_date}~{end_date} error={e}")
        
        if i < MAX_RETRY - 1:
            time.sleep(RETRY_SLEEP)
    
    return []


def upsert_spend(conn, rows: List[Tuple]):
    """
    写入 tt_ad_account_spend_hourly
    使用 REPLACE INTO 自动处理重复数据（先删除旧数据，再插入新数据）
    添加死锁重试机制，避免多线程并发写入时的死锁问题
    """
    if not rows:
        return
    
    sql = """
    REPLACE INTO tt_ad_account_spend_hourly
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
        DELETE FROM tt_ad_account_spend_hourly
        WHERE DATE(time_hour) >= %s AND DATE(time_hour) <= %s
    """
    
    try:
        with conn.cursor() as cur:
            # 先查询有多少条数据
            count_sql = """
                SELECT COUNT(*) as count FROM tt_ad_account_spend_hourly
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


def process_account(account: Dict, dates: List[datetime.date]) -> int:
    """
    处理单个账户的所有日期，收集完所有数据后一次性批量写入数据库
    优化策略：
    1. API调用保持并发（快速）
    2. 数据库写入改为批量（每个账户处理完所有日期后一次性写入）
    3. 大幅减少数据库写入次数，降低死锁概率
    返回写入的记录数
    """
    advertiser_id = account["ad_account_id"]
    owner = account["owner"]
    
    # 获取该账户对应的 Token
    access_token = get_token_for_account(advertiser_id)
    if not access_token:
        print(f"[WARN] {advertiser_id} 未找到对应的 Token，跳过")
        return 0
    
    print(f"[开始] {advertiser_id} 处理 {len(dates)} 天数据...")
    
    # 先收集所有数据到内存，不立即写入数据库
    all_rows = []
    today = datetime.date.today()
    processed_dates = 0
    
    try:
        # 第一步：收集所有日期的数据（API调用）
        for idx, d in enumerate(dates, 1):
            date_str = d.strftime("%Y-%m-%d")
            # 判断使用小时数据还是日数据
            days_ago = (today - d).days
            use_hourly = days_ago <= 30  # 只对最近30天的数据使用小时维度
            
            if idx % 10 == 0 or idx == 1:
                mode = "小时数据" if use_hourly else "日数据"
                print(f"[进度] {advertiser_id} 处理日期 {idx}/{len(dates)}: {date_str} ({mode})")
            
            # 根据天数选择维度
            dimensions = '["stat_time_hour"]' if use_hourly else '["stat_time_day"]'
            data = call_tiktok_report(advertiser_id, date_str, date_str, access_token, dimensions)
            
            if not data:
                continue
            
            # 使用字典去重，避免重复数据累加
            seen = {}  # key: (time_hour, ad_account_id)
            
            for r in data:
                spend = float(r.get("metrics", {}).get("spend", 0) or 0)
                currency = None  # TikTok API 可能不返回货币，使用默认值
                
                # 解析时间字段
                dimensions_data = r.get("dimensions", {})
                time_str = dimensions_data.get("stat_time_hour") or dimensions_data.get("stat_time_day")
                
                if time_str:
                    # 解析时间字符串，例如 "2025-12-08 00:00:00" 或 "2025-12-08"
                    try:
                        time_hour = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                    except:
                        # 如果解析失败，尝试只解析日期（日数据格式）
                        try:
                            time_hour = datetime.datetime.strptime(time_str.split()[0], "%Y-%m-%d")
                            # 如果是日数据，需要将花费平均分配到24小时
                            if not use_hourly:
                                hourly_spend = spend / 24.0 if spend > 0 else 0.0
                                for hour in range(24):
                                    hour_time = time_hour.replace(hour=hour, minute=0, second=0)
                                    # 只保留请求日期当天的数据
                                    if hour_time.date() == d:
                                        key = (hour_time, advertiser_id)
                                        if key not in seen:
                                            seen[key] = (hour_time, advertiser_id, owner, hourly_spend, currency)
                                continue
                        except:
                            print(f"[WARN] {advertiser_id} {date_str} 无法解析时间: {time_str}")
                            continue
                    
                    # 关键修复：只保留请求日期当天的数据，过滤掉跨天数据
                    if time_hour.date() != d:
                        # 跳过不属于请求日期的数据（可能是跨天数据）
                        continue
                    
                    # 去重：如果同一小时已存在，使用最新的数据（覆盖）
                    key = (time_hour, advertiser_id)
                    if key not in seen:
                        seen[key] = (time_hour, advertiser_id, owner, spend, currency)
                    else:
                        # 如果已存在，更新为最新的（覆盖旧数据）
                        print(f"[DEBUG] {advertiser_id} {date_str} 发现重复的小时 {time_hour}，使用最新数据 spend={spend}")
                        seen[key] = (time_hour, advertiser_id, owner, spend, currency)
                else:
                    print(f"[WARN] {advertiser_id} {date_str} 数据缺少时间字段，跳过")
            
            # 将去重后的数据添加到rows
            if seen:
                all_rows.extend(seen.values())
                processed_dates += 1
        
        # 第二步：所有数据收集完成后，一次性批量写入数据库
        if all_rows:
            print(f"[写入] {advertiser_id} 开始批量写入 {len(all_rows)} 条数据到数据库...")
            conn = get_db_conn()
            try:
                upsert_spend(conn, all_rows)
                print(f"[完成] {advertiser_id} 处理完成，写入 {len(all_rows)} 条数据（{processed_dates} 天有数据）")
                return len(all_rows)
            finally:
                conn.close()
        else:
            print(f"[完成] {advertiser_id} 处理完成，无数据写入")
            return 0
            
    except Exception as e:
        print(f"[异常] {advertiser_id} 处理出错: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="回填天数，默认30天")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    args = parser.parse_args()

    today = datetime.date.today()
    if args.start and args.end:
        start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        end_date = today
        start_date = end_date - datetime.timedelta(days=args.days - 1)

    dates = date_range(start_date, end_date)
    print(f"回填日期范围：{start_date} ~ {end_date} 共 {len(dates)} 天")
    print(f"策略：最近30天使用小时数据，30-90天使用日数据（平均分配到24小时）")
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
            print("映射表 tt_ad_account_owner_mapping 为空，先导入映射数据")
            return

        print("步骤2：开始回填新数据")
        print("=" * 80)
        print(f"共 {len(accounts)} 个账户，开始回填...")
        total_written = 0
        
        # 注意：每个线程会创建自己的数据库连接，不需要主连接
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_account, acc, dates): acc for acc in accounts}
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




