"""
回填 shoplazza_store_hourly 表的 owner 字段

使用方式：
  # 回填今天的数据
  python backfill_owner_to_store_hourly.py
  
  # 回填指定日期
  python backfill_owner_to_store_hourly.py --date 2025-12-10
  
  # 回填日期范围
  python backfill_owner_to_store_hourly.py --start 2025-12-08 --end 2025-12-10
  
  # 回填最近N天
  python backfill_owner_to_store_hourly.py --days 7
"""
import argparse
import datetime
import pymysql
from typing import Dict

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


def get_store_owner_mapping(conn) -> Dict[str, str]:
    """获取店铺域名到负责人的映射"""
    sql = "SELECT shop_domain, owner FROM store_owner_mapping"
    mapping = {}
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        for row in rows:
            mapping[row['shop_domain']] = row['owner']
    return mapping


def date_range(start: datetime.date, end: datetime.date) -> list:
    """生成日期范围列表"""
    days = (end - start).days
    return [start + datetime.timedelta(days=i) for i in range(days + 1)]


def backfill_owner_for_date(conn, target_date: datetime.date, mapping: Dict[str, str]) -> int:
    """回填指定日期的 owner 字段"""
    sql = """
        UPDATE shoplazza_store_hourly
        SET owner = %s
        WHERE DATE(time_hour) = %s
          AND shop_domain = %s
          AND (owner IS NULL OR owner = '')
    """
    
    updated_count = 0
    with conn.cursor() as cur:
        for shop_domain, owner in mapping.items():
            cur.execute(sql, (owner, target_date, shop_domain))
            updated_count += cur.rowcount
    
    conn.commit()
    return updated_count


def main():
    parser = argparse.ArgumentParser(description="回填 shoplazza_store_hourly 表的 owner 字段")
    parser.add_argument("--date", help="指定日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--days", type=int, help="最近N天，例如 --days 7 表示最近7天")
    args = parser.parse_args()

    today = datetime.date.today()
    
    # 解析日期范围
    if args.date:
        start_date = end_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    elif args.start and args.end:
        start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
    elif args.days:
        end_date = today
        start_date = end_date - datetime.timedelta(days=args.days - 1)
    else:
        # 默认回填今天
        start_date = end_date = today

    dates = date_range(start_date, end_date)
    print("=" * 80)
    print(f"回填日期范围：{start_date} ~ {end_date} 共 {len(dates)} 天")
    print("=" * 80)

    conn = get_db_conn()
    try:
        # 获取映射关系
        print("加载店铺→负责人映射...")
        mapping = get_store_owner_mapping(conn)
        print(f"共 {len(mapping)} 个店铺映射")
        print()
        
        total_updated = 0
        for d in dates:
            updated = backfill_owner_for_date(conn, d, mapping)
            total_updated += updated
            if updated > 0:
                print(f"[OK] {d} 更新 {updated} 条记录")
            else:
                print(f"[INFO] {d} 无需更新（owner 字段已填充或没有数据）")
        
        print("=" * 80)
        print(f"[DONE] 总更新 {total_updated} 条记录")
    finally:
        conn.close()


if __name__ == "__main__":
    main()



