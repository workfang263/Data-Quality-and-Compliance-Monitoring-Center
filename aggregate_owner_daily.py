"""
聚合负责人日汇总数据，将 shoplazza_store_hourly、fb_ad_account_spend_hourly 和 tt_ad_account_spend_hourly 的数据
按负责人、按天聚合到 owner_daily_summary 表

支持：
- 店铺数据（销售额、订单、访客）
- Facebook 广告花费
- TikTok 广告花费
- 总广告花费（FB + TikTok）

使用方式：
  # 聚合今天的数据
  python aggregate_owner_daily.py
  
  # 聚合指定日期
  python aggregate_owner_daily.py --date 2025-12-10
  
  # 聚合日期范围
  python aggregate_owner_daily.py --start 2025-12-08 --end 2025-12-10
  
  # 聚合最近N天（例如最近7天）
  python aggregate_owner_daily.py --days 7
"""
import argparse
import datetime
import pymysql
from typing import List, Dict, Optional

from config import DB_CONFIG
from timezone_utils import get_timezone_config


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


def date_range(start: datetime.date, end: datetime.date) -> List[datetime.date]:
    """生成日期范围列表"""
    days = (end - start).days
    return [start + datetime.timedelta(days=i) for i in range(days + 1)]


def aggregate_store_data(conn, target_date: datetime.date) -> Dict[str, Dict]:
    """
    从 shoplazza_store_hourly 聚合店铺数据
    返回: {owner: {total_gmv, total_orders, total_visitors, avg_order_value}}
    
    注意：访客数是按天去重的，同一天所有小时的访客数相同，需要先按店铺取MAX去重24小时，
          然后再按负责人汇总（不同店铺的访客是不同的IP，应该累加）
    """
    sql = """
        SELECT 
            owner,
            SUM(total_gmv) as total_gmv,
            SUM(total_orders) as total_orders,
            SUM(max_visitors_by_shop) as total_visitors
        FROM (
            SELECT 
                owner,
                shop_domain,
                SUM(total_gmv) as total_gmv,
                SUM(total_orders) as total_orders,
                MAX(total_visitors) as max_visitors_by_shop
            FROM shoplazza_store_hourly
            WHERE DATE(time_hour) = %s
              AND owner IS NOT NULL
            GROUP BY owner, shop_domain
        ) t
        GROUP BY owner
    """
    
    result = {}
    with conn.cursor() as cur:
        cur.execute(sql, (target_date,))
        rows = cur.fetchall()
        
        for row in rows:
            owner = row['owner']
            total_gmv = float(row['total_gmv'] or 0)
            total_orders = int(row['total_orders'] or 0)
            total_visitors = int(row['total_visitors'] or 0)
            
            # 计算平均客单价
            avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
            
            result[owner] = {
                'total_gmv': total_gmv,
                'total_orders': total_orders,
                'total_visitors': total_visitors,
                'avg_order_value': avg_order_value
            }
    
    return result


def aggregate_spend_data(conn, target_date: datetime.date) -> Dict[str, float]:
    """
    从 fb_ad_account_spend_hourly 聚合 Facebook 广告花费数据
    根据账户时区配置，正确查询跨天数据
    返回: {owner: total_spend}
    """
    # 1. 获取所有Facebook广告账户及其负责人
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ad_account_id, owner 
            FROM ad_account_owner_mapping
        """)
        accounts = cur.fetchall()
    
    # 2. 按负责人分组，计算每个负责人的总花费
    owner_spend = {}
    
    for acc in accounts:
        ad_account_id = acc['ad_account_id']
        owner = acc['owner']
        
        # 确保有 act_ 前缀
        if not ad_account_id.startswith("act_"):
            ad_account_id = f"act_{ad_account_id}"
        
        try:
            # 获取账户时区配置
            timezone_config = get_timezone_config(conn, ad_account_id, owner, platform="facebook")
            timezone_offset = timezone_config["timezone_offset"]
            
            # 将账户时区的日期转换为北京时间的日期范围
            # 账户时区的开始时间：target_date 00:00:00
            account_date_start = datetime.datetime.combine(target_date, datetime.time.min)
            # 账户时区的结束时间：target_date 23:59:59
            account_date_end = datetime.datetime.combine(target_date, datetime.time.max.replace(microsecond=999999))
            
            # 转换为北京时间
            # 计算需要添加的小时数：8.0 - timezone_offset
            hours_to_add = 8.0 - timezone_offset
            beijing_start = account_date_start + datetime.timedelta(hours=hours_to_add)
            beijing_end = account_date_end + datetime.timedelta(hours=hours_to_add)
            
            # 查询该账户在该时间范围内的花费
            sql = """
                SELECT SUM(spend) as total_spend
                FROM fb_ad_account_spend_hourly
                WHERE ad_account_id = %s
                  AND time_hour >= %s
                  AND time_hour <= %s
            """
            with conn.cursor() as cur:
                cur.execute(sql, (ad_account_id, beijing_start, beijing_end))
                row = cur.fetchone()
                spend = float(row['total_spend'] or 0) if row else 0.0
            
            # 累加到负责人
            if owner not in owner_spend:
                owner_spend[owner] = 0.0
            owner_spend[owner] += spend
            
        except Exception as e:
            # 如果获取时区配置失败，使用默认逻辑（UTC+8，单天查询）
            # 这样可以保证即使出错也不会影响其他账户
            sql = """
                SELECT SUM(spend) as total_spend
                FROM fb_ad_account_spend_hourly
                WHERE ad_account_id = %s
                  AND DATE(time_hour) = %s
            """
            with conn.cursor() as cur:
                cur.execute(sql, (ad_account_id, target_date))
                row = cur.fetchone()
                spend = float(row['total_spend'] or 0) if row else 0.0
            
            if owner not in owner_spend:
                owner_spend[owner] = 0.0
            owner_spend[owner] += spend
    
    return owner_spend


def aggregate_tt_spend_data(conn, target_date: datetime.date) -> Dict[str, float]:
    """
    从 tt_ad_account_spend_hourly 聚合 TikTok 广告花费数据
    返回: {owner: tt_total_spend}
    """
    sql = """
        SELECT 
            owner,
            SUM(spend) as tt_total_spend
        FROM tt_ad_account_spend_hourly
        WHERE DATE(time_hour) = %s
        GROUP BY owner
    """
    
    result = {}
    with conn.cursor() as cur:
        cur.execute(sql, (target_date,))
        rows = cur.fetchall()
        
        for row in rows:
            owner = row['owner']
            tt_total_spend = float(row['tt_total_spend'] or 0)
            result[owner] = tt_total_spend
    
    return result


def upsert_owner_daily_summary(conn, target_date: datetime.date, owner: str, 
                                total_gmv: float, total_orders: int, total_visitors: int,
                                avg_order_value: float, total_spend: float, tt_total_spend: float):
    """
    写入或更新 owner_daily_summary 表
    计算 ROAS：如果 total_spend_all > 0，则 roas = total_gmv / total_spend_all，否则为 NULL
    注意：total_spend_all 是计算字段（FB + TikTok），如果表中有 GENERATED COLUMN 会自动计算
    """
    # 计算总广告花费（FB + TikTok）
    total_spend_all = total_spend + tt_total_spend
    
    # 计算 ROAS（基于总广告花费）
    roas = total_gmv / total_spend_all if total_spend_all > 0 else None
    
    sql = """
        REPLACE INTO owner_daily_summary
          (date, owner, total_gmv, total_orders, total_visitors, 
           avg_order_value, total_spend, tt_total_spend, roas)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    with conn.cursor() as cur:
        cur.execute(sql, (
            target_date, owner, total_gmv, total_orders, total_visitors,
            avg_order_value, total_spend, tt_total_spend, roas
        ))
    conn.commit()


def aggregate_date(conn, target_date: datetime.date, verbose: bool = True) -> int:
    """
    聚合指定日期的数据
    返回写入的记录数
    """
    if verbose:
        print(f"聚合日期：{target_date}")
    
    # 1. 聚合店铺数据
    store_data = aggregate_store_data(conn, target_date)
    
    # 2. 聚合 Facebook 广告花费数据
    spend_data = aggregate_spend_data(conn, target_date)
    
    # 3. 聚合 TikTok 广告花费数据
    tt_spend_data = aggregate_tt_spend_data(conn, target_date)
    
    # 4. 合并数据并写入
    # 获取所有出现过的负责人（店铺数据 + Facebook花费 + TikTok花费）
    all_owners = set(store_data.keys()) | set(spend_data.keys()) | set(tt_spend_data.keys())
    
    if not all_owners:
        if verbose:
            print(f"  [INFO] {target_date} 无数据")
        return 0
    
    count = 0
    for owner in all_owners:
        # 获取店铺数据（如果没有则为0）
        store_info = store_data.get(owner, {
            'total_gmv': 0.0,
            'total_orders': 0,
            'total_visitors': 0,
            'avg_order_value': 0.0
        })
        
        # 获取 Facebook 广告花费数据（如果没有则为0）
        total_spend = spend_data.get(owner, 0.0)
        
        # 获取 TikTok 广告花费数据（如果没有则为0）
        tt_total_spend = tt_spend_data.get(owner, 0.0)
        
        # 写入数据库
        upsert_owner_daily_summary(
            conn, target_date, owner,
            store_info['total_gmv'],
            store_info['total_orders'],
            store_info['total_visitors'],
            store_info['avg_order_value'],
            total_spend,
            tt_total_spend
        )
        count += 1
    
    if verbose:
        print(f"  [OK] {target_date} 写入 {count} 条记录")
    
    return count


def main():
    parser = argparse.ArgumentParser(description="聚合负责人日汇总数据")
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
        # 默认聚合今天
        start_date = end_date = today

    dates = date_range(start_date, end_date)
    print("=" * 80)
    print(f"聚合日期范围：{start_date} ~ {end_date} 共 {len(dates)} 天")
    print("=" * 80)

    conn = get_db_conn()
    try:
        total_count = 0
        for d in dates:
            count = aggregate_date(conn, d, verbose=True)
            total_count += count
        
        print("=" * 80)
        print(f"[DONE] 总写入 {total_count} 条记录")
    finally:
        conn.close()


if __name__ == "__main__":
    main()



