"""B.3 一次性验证脚本：检查 fb_campaign_spend_daily 落库 + operation_logs 告警。"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pymysql
from config import DB_CONFIG


def main(target_date: str = "2026-04-21") -> None:
    conn = pymysql.connect(
        host=DB_CONFIG["host"], port=DB_CONFIG["port"],
        user=DB_CONFIG["user"], password=DB_CONFIG["password"],
        database=DB_CONFIG["database"], charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        cur = conn.cursor()

        print("===== fb_campaign_spend_daily 落库总览 =====")
        cur.execute(
            "SELECT stat_date, COUNT(*) AS rows_cnt, "
            "COUNT(DISTINCT ad_account_id) AS accts, "
            "SUM(spend) AS total "
            "FROM fb_campaign_spend_daily WHERE stat_date=%s "
            "GROUP BY stat_date",
            (target_date,),
        )
        for r in cur.fetchall():
            print(" ", r)

        print()
        print("===== 按 shop_domain 聚合 =====")
        cur.execute(
            """
            SELECT w.shop_domain,
                   COUNT(DISTINCT c.ad_account_id) AS accounts,
                   COUNT(*) AS rows_cnt,
                   SUM(c.spend) AS total
            FROM fb_campaign_spend_daily c
            JOIN store_ops_shop_ad_whitelist w
              ON w.ad_account_id COLLATE utf8mb4_unicode_ci
               = c.ad_account_id COLLATE utf8mb4_unicode_ci
            WHERE c.stat_date=%s AND w.is_enabled=1
            GROUP BY w.shop_domain
            """,
            (target_date,),
        )
        for r in cur.fetchall():
            print(" ", r)

        print()
        print("===== Top 5 系列花费 =====")
        cur.execute(
            "SELECT ad_account_id, campaign_id, campaign_name, spend, currency "
            "FROM fb_campaign_spend_daily WHERE stat_date=%s "
            "ORDER BY spend DESC LIMIT 5",
            (target_date,),
        )
        for r in cur.fetchall():
            print(" ", r)

        print()
        print("===== 最近 B.3 对账告警（operation_logs）=====")
        cur.execute(
            "SELECT log_type, status, LEFT(message, 200) AS msg, created_at "
            "FROM operation_logs WHERE log_type='fb_campaign_spend_sync' "
            "ORDER BY id DESC LIMIT 5"
        )
        rows = cur.fetchall()
        print(f"  告警数：{len(rows)}")
        for r in rows:
            print(" ", r)
    finally:
        conn.close()


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "2026-04-21"
    main(date_arg)
