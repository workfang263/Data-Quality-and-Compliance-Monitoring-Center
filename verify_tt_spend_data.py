"""
验证 TikTok 广告花费数据准确性：
1) 按日期、账户，直接调用 TikTok API 获取 spend
2) 对比数据库 tt_ad_account_spend_hourly 的存量
3) 显示汇总信息，方便与 TikTok 后台对比

使用示例：
  # 验证单个日期
  python verify_tt_spend_data.py --date 2025-12-10
  
  # 验证日期范围
  python verify_tt_spend_data.py --start 2025-12-10 --end 2025-12-16
  
  # 只显示汇总（不对比API，更快）
  python verify_tt_spend_data.py --start 2025-12-10 --end 2025-12-16 --summary-only
"""
import argparse
import datetime
import time
import requests
import pymysql
from typing import List, Dict, Optional

from config import DB_CONFIG, TT_CONFIG

MAX_RETRY = 3
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


def get_token_for_account(advertiser_id: str) -> Optional[str]:
    """根据广告账户ID查找对应的 Business Center Token"""
    business_centers = TT_CONFIG.get("business_centers", [])
    for bc in business_centers:
        if advertiser_id in bc.get("advertiser_ids", []):
            return bc.get("access_token")
    return None


def call_tiktok_api(advertiser_id: str, date: str, access_token: str) -> float:
    """
    调用 TikTok Marketing API 获取指定日期的总花费
    使用日维度查询，返回该日期的总花费
    """
    url = f"{TT_CONFIG['base_url']}/report/integrated/get/"
    
    params = {
        "advertiser_id": advertiser_id,
        "service_type": "AUCTION",
        "report_type": "BASIC",
        "data_level": "AUCTION_ADVERTISER",
        "dimensions": '["stat_time_day"]',  # 使用日维度
        "metrics": '["spend"]',
        "start_date": date,
        "end_date": date,
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
                    if result:
                        # 日维度数据，应该只有一条
                        spend = float(result[0].get("metrics", {}).get("spend", 0) or 0)
                        return spend
                    else:
                        # 没有数据，返回0
                        return 0.0
                else:
                    error_msg = data.get("message", "未知错误")
                    print(f"[WARN] {advertiser_id} {date} API错误: {error_msg}")
                    return 0.0
            else:
                print(f"[WARN] {advertiser_id} {date} HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[ERR ] {advertiser_id} {date} 异常: {e}")
        
        if i < MAX_RETRY - 1:
            time.sleep(RETRY_SLEEP)
    
    return 0.0


def fetch_db_spend(conn, advertiser_id: str, date: str) -> float:
    """从数据库查询指定账户和日期的总花费"""
    sql = """
    SELECT SUM(spend) AS total_spend
    FROM tt_ad_account_spend_hourly
    WHERE ad_account_id = %s AND DATE(time_hour) = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (advertiser_id, date))
        row = cur.fetchone()
        return float(row["total_spend"] or 0) if row else 0.0


def fetch_accounts_with_owner(conn) -> List[Dict]:
    """从映射表读取广告账户ID与负责人"""
    with conn.cursor() as cur:
        cur.execute("SELECT ad_account_id, owner FROM tt_ad_account_owner_mapping ORDER BY ad_account_id")
        return cur.fetchall()


def get_spend_summary(conn, start_date: datetime.date, end_date: datetime.date) -> Dict[str, Dict]:
    """
    查询指定日期范围内每个广告账户的总花费
    返回: {ad_account_id: {'total_spend': float, 'record_count': int, 'owner': str}}
    """
    sql = """
        SELECT 
            t.ad_account_id,
            m.owner,
            SUM(t.spend) as total_spend,
            COUNT(*) as record_count
        FROM tt_ad_account_spend_hourly t
        LEFT JOIN tt_ad_account_owner_mapping m ON t.ad_account_id = m.ad_account_id
        WHERE DATE(t.time_hour) >= %s AND DATE(t.time_hour) <= %s
        GROUP BY t.ad_account_id, m.owner
        ORDER BY t.ad_account_id
    """
    
    with conn.cursor() as cur:
        cur.execute(sql, (start_date, end_date))
        results = cur.fetchall()
        
        summary = {}
        for row in results:
            summary[row['ad_account_id']] = {
                'total_spend': float(row['total_spend'] or 0),
                'record_count': row['record_count'],
                'owner': row['owner'] or '未知'
            }
        return summary


def verify_single_date(conn, accounts: List[Dict], date: str, summary_only: bool = False):
    """验证单个日期的数据"""
    print(f"\n{'='*100}")
    print(f"验证日期：{date}")
    print(f"{'='*100}")
    
    if summary_only:
        print(f"{'广告账户ID':<25} {'负责人':<15} {'数据库花费':<15} {'记录数':<10}")
        print("-" * 100)
    else:
        print(f"{'广告账户ID':<25} {'负责人':<15} {'API花费':<15} {'数据库花费':<15} {'差异':<15} {'状态':<10}")
        print("-" * 100)
    
    total_api_spend = 0.0
    total_db_spend = 0.0
    total_diff = 0.0
    ok_count = 0
    diff_count = 0
    
    for acc in accounts:
        advertiser_id = acc['ad_account_id']
        owner = acc['owner']
        
        db_spend = fetch_db_spend(conn, advertiser_id, date)
        total_db_spend += db_spend
        
        if summary_only:
            # 只显示数据库数据
            record_count_sql = """
                SELECT COUNT(*) as cnt FROM tt_ad_account_spend_hourly
                WHERE ad_account_id = %s AND DATE(time_hour) = %s
            """
            with conn.cursor() as cur:
                cur.execute(record_count_sql, (advertiser_id, date))
                row = cur.fetchone()
                record_count = row['cnt'] if row else 0
            print(f"{advertiser_id:<25} {owner:<15} {db_spend:>14.2f} {record_count:>10}")
        else:
            # 对比 API 和数据库
            access_token = get_token_for_account(advertiser_id)
            if not access_token:
                print(f"{advertiser_id:<25} {owner:<15} {'Token未找到':<15} {db_spend:>14.2f} {'-':<15} {'跳过':<10}")
                continue
            
            api_spend = call_tiktok_api(advertiser_id, date, access_token)
            total_api_spend += api_spend
            
            diff = db_spend - api_spend
            total_diff += diff
            
            if abs(diff) <= 0.01:  # 允许0.01的误差
                status = "[OK]"
                ok_count += 1
            else:
                status = "[DIFF]"
                diff_count += 1
            
            print(f"{advertiser_id:<25} {owner:<15} {api_spend:>14.2f} {db_spend:>14.2f} {diff:>14.2f} {status:<10}")
    
    print("-" * 100)
    if summary_only:
        print(f"{'总计':<25} {'':<15} {total_db_spend:>14.2f}")
    else:
        print(f"{'总计':<25} {'':<15} {total_api_spend:>14.2f} {total_db_spend:>14.2f} {total_diff:>14.2f}")
        print(f"\n验证结果：✅ 一致 {ok_count} 个账户，⚠️  差异 {diff_count} 个账户")
    print(f"{'='*100}")


def show_summary(conn, start_date: datetime.date, end_date: datetime.date):
    """显示日期范围内的汇总信息"""
    summary = get_spend_summary(conn, start_date, end_date)
    accounts = fetch_accounts_with_owner(conn)
    
    print(f"\n{'='*100}")
    print(f"TikTok 广告花费汇总（{start_date} ~ {end_date}）")
    print(f"{'='*100}")
    print(f"{'广告账户ID':<25} {'负责人':<15} {'总花费':<15} {'记录数':<10}")
    print("-" * 100)
    
    total_spend_all = 0.0
    total_records = 0
    
    for acc in accounts:
        advertiser_id = acc['ad_account_id']
        owner = acc['owner']
        
        if advertiser_id in summary:
            total_spend = summary[advertiser_id]['total_spend']
            record_count = summary[advertiser_id]['record_count']
            total_spend_all += total_spend
            total_records += record_count
            print(f"{advertiser_id:<25} {owner:<15} {total_spend:>14.2f} {record_count:>10}")
        else:
            # 没有数据的账户
            print(f"{advertiser_id:<25} {owner:<15} {'0.00':>14} {'0':>10}")
    
    print("-" * 100)
    print(f"{'总计':<25} {'':<15} {total_spend_all:>14.2f} {total_records:>10}")
    print(f"{'='*100}")
    print()
    print("提示：")
    print("1. 请前往 TikTok Ads Manager 后台")
    print("2. 选择对应的广告账户")
    print("3. 设置日期范围为上述日期范围")
    print("4. 查看 'Spend' 列，与上表中的 '总花费' 对比")
    print("5. 如果数据一致，说明数据准确")


def main():
    parser = argparse.ArgumentParser(description="验证 TikTok 广告花费数据准确性")
    parser.add_argument("--date", help="验证单个日期 YYYY-MM-DD")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--summary-only", action="store_true", 
                       help="只显示汇总信息，不对比API（更快）")
    args = parser.parse_args()
    
    conn = get_db_conn()
    try:
        accounts = fetch_accounts_with_owner(conn)
        if not accounts:
            print("映射表 tt_ad_account_owner_mapping 为空，请先导入映射数据")
            return
        
        if args.date:
            # 验证单个日期
            verify_single_date(conn, accounts, args.date, args.summary_only)
        elif args.start and args.end:
            # 验证日期范围
            start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
            
            if args.summary_only:
                # 只显示汇总
                show_summary(conn, start_date, end_date)
            else:
                # 逐日验证
                current_date = start_date
                while current_date <= end_date:
                    verify_single_date(conn, accounts, current_date.strftime("%Y-%m-%d"), False)
                    current_date += datetime.timedelta(days=1)
                
                # 最后显示汇总
                print("\n")
                show_summary(conn, start_date, end_date)
        else:
            print("错误：请指定日期（--date）或日期范围（--start 和 --end）")
            print("示例：")
            print("  python verify_tt_spend_data.py --date 2025-12-10")
            print("  python verify_tt_spend_data.py --start 2025-12-10 --end 2025-12-16")
            print("  python verify_tt_spend_data.py --start 2025-12-10 --end 2025-12-16 --summary-only")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

