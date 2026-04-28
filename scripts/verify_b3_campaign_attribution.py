"""B.3 端到端：用真实系列名跑 match_employee_by_campaign 归因演练。

两组场景：
  A. 使用现有 DB（占位符 __unset_*）：应全部为"未归属"
  B. 临时注入"前缀即关键词"的运营列表：印证系列名前缀 amao-/wanqiu- 等能被正确归因

不改 DB，只读。
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from decimal import Decimal

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import pymysql
from config import DB_CONFIG
from app.services.store_ops_attribution import (
    get_active_operators,
    match_employee_by_campaign,
    reset_cache_for_tests,
)


def fetch_campaigns(stat_date: str):
    conn = pymysql.connect(
        host=DB_CONFIG["host"], port=DB_CONFIG["port"],
        user=DB_CONFIG["user"], password=DB_CONFIG["password"],
        database=DB_CONFIG["database"], charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ad_account_id, campaign_id, campaign_name, spend "
                "FROM fb_campaign_spend_daily WHERE stat_date=%s",
                (stat_date,),
            )
            return cur.fetchall() or []
    finally:
        conn.close()


def _summarize(label, rows, operators):
    bucket = Counter()
    bucket_spend = {}
    for r in rows:
        slug = match_employee_by_campaign(r["campaign_name"], operators=operators)
        key = slug or "_unattributed"
        bucket[key] += 1
        bucket_spend[key] = bucket_spend.get(key, Decimal("0")) + Decimal(str(r["spend"]))
    total = sum(bucket_spend.values(), Decimal("0"))

    print(f"\n===== {label} =====")
    for key, cnt in sorted(bucket.items(), key=lambda kv: -bucket_spend[kv[0]]):
        print(f"  {key:<14} 系列={cnt:<4} 花费={bucket_spend[key]}")
    print(f"  {'合计':<14} 系列={sum(bucket.values()):<4} 花费={total}")


def main():
    stat_date = sys.argv[1] if len(sys.argv) > 1 else "2026-04-21"
    rows = fetch_campaigns(stat_date)
    print(f"[INFO] 读取 {stat_date} 系列 {len(rows)} 条")

    reset_cache_for_tests()
    active = get_active_operators()
    print("\n[当前 store_ops_employee_config 运营配置]")
    for op in active:
        print(f"  sort_order={op['sort_order']:<4} "
              f"slug={op['employee_slug']:<12} "
              f"campaign_keyword={op['campaign_keyword']}")

    _summarize("场景 A：使用当前 DB（占位符 __unset_*）", rows, active)

    slug_as_keyword = [
        {**op, "campaign_keyword": op["employee_slug"]} for op in active
    ]
    _summarize(
        "场景 B：临时把 campaign_keyword 设为 slug 本身（演练未来前端配置后的效果）",
        rows, slug_as_keyword,
    )


if __name__ == "__main__":
    main()
