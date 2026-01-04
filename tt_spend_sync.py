"""
拉取指定日期的 TikTok 广告花费，写入 tt_ad_account_spend_hourly

使用方式（示例）：
  # 默认拉取今天
  python tt_spend_sync.py
  # 拉取指定日期
  python tt_spend_sync.py --date 2025-12-08
  # 传入开始/结束日期（闭区间），按天循环
  python tt_spend_sync.py --start 2025-12-06 --end 2025-12-08
  # 增量模式（定时任务推荐，不清理旧数据）
  python tt_spend_sync.py --incremental

前置要求：
  1) config.py 中已配置 TT_CONFIG（包含两个 BC 的 token 和 advertiser_ids）
  2) 数据库表已创建：
     - tt_ad_account_spend_hourly
     - tt_ad_account_owner_mapping
  3) 已导入广告账户 -> 负责人映射
"""
import argparse
import datetime
import time
import requests
import pymysql
from typing import List, Dict, Optional, Tuple

# 聚合
from aggregate_owner_daily import aggregate_date

from config import DB_CONFIG, TT_CONFIG

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
        cur.execute("SELECT ad_account_id, owner FROM tt_ad_account_owner_mapping")
        return cur.fetchall()


def call_tiktok_report(advertiser_id: str, start_date: str, end_date: str, 
                       access_token: str, dimensions: str = '["stat_time_hour"]') -> List[Dict]:
    """
    调用 TikTok Marketing API 获取报表数据（按小时）
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
    rows: list of (time_hour, ad_account_id, owner, spend, currency)
    """
    if not rows:
        return
    sql = """
    REPLACE INTO tt_ad_account_spend_hourly
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


def get_owner_for_account(conn, advertiser_id: str) -> Optional[str]:
    """从映射表获取广告账户对应的负责人"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT owner FROM tt_ad_account_owner_mapping WHERE ad_account_id = %s",
            (advertiser_id,)
        )
        result = cur.fetchone()
        return result['owner'] if result else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="指定日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--incremental", action="store_true",
                        help="增量模式：不清理旧数据，只覆盖写入（定时任务推荐）")
    args = parser.parse_args()

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

        # 获取所有 BC 配置
        business_centers = TT_CONFIG.get("business_centers", [])
        if not business_centers:
            print("❌ config.py 中 TT_CONFIG.business_centers 为空，请先配置")
            return

        print("步骤2：开始同步新数据")
        print("=" * 80)
        
        for d in dates:
            date_str = d.strftime("%Y-%m-%d")
            rows = []
            
            # 遍历所有 Business Center
            for bc in business_centers:
                bc_name = bc["name"]
                access_token = bc["access_token"]
                advertiser_ids = bc["advertiser_ids"]
                
                print(f"\n[BC] {bc_name} ({len(advertiser_ids)} 个账户)")
                
                # 遍历该 BC 下的所有广告账户
                for advertiser_id in advertiser_ids:
                    # 从映射表获取负责人
                    owner = get_owner_for_account(conn, advertiser_id)
                    if not owner:
                        print(f"[WARN] {advertiser_id} 未找到负责人映射，跳过")
                        continue
                    
                    # 调用 API 获取数据
                    data = call_tiktok_report(advertiser_id, date_str, date_str, access_token)
                    
                    if not data:
                        print(f"[DEBUG] {advertiser_id} {date_str} 返回空数据")
                    else:
                        print(f"[DEBUG] {advertiser_id} {date_str} 返回 {len(data)} 条数据")
                    
                    # 使用字典去重，避免重复数据累加
                    seen = {}  # key: (time_hour, ad_account_id)
                    
                    for r in data:
                        spend = float(r.get("metrics", {}).get("spend", 0) or 0)
                        currency = None  # TikTok API 可能不返回货币，使用默认值
                        
                        # 解析时间字段
                        dimensions = r.get("dimensions", {})
                        time_str = dimensions.get("stat_time_hour") or dimensions.get("stat_time_day")
                        
                        if time_str:
                            # 解析时间字符串，例如 "2025-12-08 00:00:00"
                            try:
                                time_hour = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                            except:
                                # 如果解析失败，尝试只解析日期
                                try:
                                    time_hour = datetime.datetime.strptime(time_str.split()[0], "%Y-%m-%d")
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
                    rows.extend(seen.values())

            if rows:
                upsert_spend(conn, rows)
                print(f"\n[OK ] {date_str} 写入 {len(rows)} 条")
            else:
                print(f"\n[WARN] {date_str} 没有数据写入")

            # 聚合：同步完成后立即聚合当前日期（幂等，重复聚合不会出错）
            try:
                aggregate_date(conn, d, verbose=False)
                print(f"[聚合] {date_str} 聚合完成")
            except Exception as e:
                print(f"[ERR] {date_str} 聚合失败: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()




