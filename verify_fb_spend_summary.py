"""
查询指定日期范围内每个广告账户的总花费，用于与Facebook官方后台对比验证

使用方式：
  python verify_fb_spend_summary.py --start 2025-09-11 --end 2025-11-09
  python verify_fb_spend_summary.py --date 2025-10-15
"""
import argparse
import datetime
import pymysql
from typing import List, Dict

from config import DB_CONFIG


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
        cur.execute("SELECT ad_account_id, owner FROM ad_account_owner_mapping ORDER BY ad_account_id")
        return cur.fetchall()


def get_spend_summary(conn, start_date: datetime.date, end_date: datetime.date) -> Dict[str, float]:
    """
    查询指定日期范围内每个广告账户的总花费
    返回: {ad_account_id: total_spend}
    """
    sql = """
        SELECT 
            ad_account_id,
            SUM(spend) as total_spend,
            COUNT(*) as record_count
        FROM fb_ad_account_spend_hourly
        WHERE DATE(time_hour) >= %s AND DATE(time_hour) <= %s
        GROUP BY ad_account_id
        ORDER BY ad_account_id
    """
    
    with conn.cursor() as cur:
        cur.execute(sql, (start_date, end_date))
        results = cur.fetchall()
        
        summary = {}
        for row in results:
            summary[row['ad_account_id']] = {
                'total_spend': float(row['total_spend'] or 0),
                'record_count': row['record_count']
            }
        return summary


def main():
    parser = argparse.ArgumentParser(description="查询指定日期范围内每个广告账户的总花费")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--date", help="指定日期 YYYY-MM-DD（等同于 --start 和 --end 都设为该日期）")
    args = parser.parse_args()

    # 解析日期
    if args.date:
        start_date = end_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    elif args.start and args.end:
        start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        print("错误：请指定日期范围（--start 和 --end）或单个日期（--date）")
        return

    conn = get_db_conn()
    try:
        accounts = fetch_accounts_with_owner(conn)
        if not accounts:
            print("映射表 ad_account_owner_mapping 为空")
            return

        summary = get_spend_summary(conn, start_date, end_date)
        
        print("=" * 100)
        print(f"广告账户花费汇总（{start_date} ~ {end_date}）")
        print("=" * 100)
        print(f"{'广告账户ID':<25} {'负责人':<15} {'总花费':<15} {'记录数':<10}")
        print("-" * 100)
        
        total_spend_all = 0
        total_records = 0
        
        for acc in accounts:
            act_id = acc['ad_account_id']
            owner = acc['owner']
            
            if act_id in summary:
                total_spend = summary[act_id]['total_spend']
                record_count = summary[act_id]['record_count']
                total_spend_all += total_spend
                total_records += record_count
                print(f"{act_id:<25} {owner:<15} {total_spend:>14.2f} {record_count:>10}")
            else:
                # 没有数据的账户
                print(f"{act_id:<25} {owner:<15} {'0.00':>14} {'0':>10}")
        
        print("-" * 100)
        print(f"{'总计':<25} {'':<15} {total_spend_all:>14.2f} {total_records:>10}")
        print("=" * 100)
        print()
        print("提示：")
        print("1. 请前往 Facebook Ads Manager 后台")
        print("2. 选择对应的广告账户")
        print("3. 设置日期范围为上述日期范围")
        print("4. 查看 '已花费金额' 列，与上表中的 '总花费' 对比")
        print("5. 如果数据一致，说明数据准确")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()



