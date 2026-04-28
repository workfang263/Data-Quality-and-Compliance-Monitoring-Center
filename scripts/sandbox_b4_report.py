"""
端到端演练 M2：沙盒运行 B.4 报表链路。

核心手法：
  - 不修改数据库里的 campaign_keyword
  - 通过 monkey-patch `store_ops_attribution.get_active_operators` 注入
    一套"假如配置已生效"的虚拟运营列表
  - 调用真正的 fetch_store_ops_fb_spend_by_shop_slug + build_store_ops_report_payload
    + merge_fb_spend_into_payload，观察花费分流效果

对照项：
  - SANDBOX_OFF = 使用 DB 真实 operators（全 __unset_*）→ 全部落到 _unattributed
  - SANDBOX_ON  = 使用虚拟 operators（真实 keyword）   → 按员工分流
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
for p in (_ROOT, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services import store_ops_attribution as attr_mod  # type: ignore
from app.services.database_new import Database  # type: ignore
from app.services.store_ops_report import (  # type: ignore
    build_store_ops_report_payload,
    merge_fb_spend_into_payload,
)


TARGET_DATE = date(2026, 4, 21)

VIRTUAL_OPERATORS: List[Dict[str, Any]] = [
    {"id": 1, "employee_slug": "xiaoyang",  "display_name": "小杨",   "utm_keyword": "xiaoyang",  "campaign_keyword": "xiaoyang",  "sort_order": 10},
    {"id": 2, "employee_slug": "kiki",      "display_name": "kiki",   "utm_keyword": "kiki",      "campaign_keyword": "__unset_kiki", "sort_order": 20},
    {"id": 3, "employee_slug": "jieni",     "display_name": "洁妮",   "utm_keyword": "jieni",     "campaign_keyword": "jieni",     "sort_order": 30},
    {"id": 4, "employee_slug": "amao",      "display_name": "阿毛",   "utm_keyword": "amao",      "campaign_keyword": "amao",      "sort_order": 40},
    {"id": 5, "employee_slug": "jimi",      "display_name": "吉米",   "utm_keyword": "jimi",      "campaign_keyword": "jimi",      "sort_order": 50},
    {"id": 6, "employee_slug": "xiaozhang", "display_name": "校长",   "utm_keyword": "xiaozhang", "campaign_keyword": "xiaozhang", "sort_order": 60},
    {"id": 7, "employee_slug": "wanqiu",    "display_name": "万秋",   "utm_keyword": "wanqiu",    "campaign_keyword": "wanqiu",    "sort_order": 70},
    {"id": 8, "employee_slug": "quqi",      "display_name": "曲奇",   "utm_keyword": "cookie",    "campaign_keyword": "cookie",    "sort_order": 80},
]


def _invalidate_cache() -> None:
    with attr_mod._cache_lock:
        attr_mod._cached_operators = None
        attr_mod._cache_expires_at = 0.0


def _run_spend_fetch(db: Database, shop: str) -> Dict[str, Decimal]:
    return db.fetch_store_ops_fb_spend_by_shop_slug(shop, TARGET_DATE, TARGET_DATE)


def _format_spend(d: Dict[str, Decimal]) -> str:
    items = sorted(d.items(), key=lambda x: float(x[1]), reverse=True)
    return ", ".join(f"{k}={float(v):.2f}" for k, v in items) or "(empty)"


def _fetch_shops(db: Database) -> List[str]:
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT shop_domain FROM store_ops_shop_whitelist "
                "WHERE is_enabled=1 ORDER BY id"
            )
            return [r["shop_domain"] for r in (cur.fetchall() or [])]


def _compare(before: Dict[str, Decimal], after: Dict[str, Decimal]) -> None:
    keys = sorted(set(before.keys()) | set(after.keys()))
    print(f"    {'slug':<15} {'SANDBOX_OFF':>14} {'SANDBOX_ON':>14} {'Δ':>10}")
    for k in keys:
        b = float(before.get(k, Decimal("0")))
        a = float(after.get(k, Decimal("0")))
        if b == 0 and a == 0:
            continue
        delta = a - b
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
        print(f"    {k:<15} {b:>14.2f} {a:>14.2f} {arrow}{abs(delta):>9.2f}")
    print(f"    {'-' * 60}")
    print(f"    {'合计':<15} {float(sum(before.values())):>14.2f} "
          f"{float(sum(after.values())):>14.2f}")


def main() -> int:
    db = Database()
    shops = _fetch_shops(db)
    print(f"[沙盒演练] {TARGET_DATE}  shops={shops}\n")

    print("=" * 80)
    print("  场景 A: SANDBOX_OFF （使用 DB 真实 operators，全 __unset_*）")
    print("=" * 80)
    _invalidate_cache()
    before_by_shop: Dict[str, Dict[str, Decimal]] = {}
    for shop in shops:
        before_by_shop[shop] = _run_spend_fetch(db, shop)
        print(f"  [{shop}] {_format_spend(before_by_shop[shop])}")

    print()
    print("=" * 80)
    print("  场景 B: SANDBOX_ON （monkey-patch 注入 8 个真实 keyword）")
    print("=" * 80)

    orig_fn = attr_mod.get_active_operators

    def fake_get_active_operators() -> List[Dict[str, Any]]:
        return list(VIRTUAL_OPERATORS)

    attr_mod.get_active_operators = fake_get_active_operators  # type: ignore
    _invalidate_cache()

    try:
        after_by_shop: Dict[str, Dict[str, Decimal]] = {}
        for shop in shops:
            after_by_shop[shop] = _run_spend_fetch(db, shop)
            print(f"\n  [{shop}]")
            _compare(before_by_shop[shop], after_by_shop[shop])

        print("\n" + "=" * 80)
        print("  完整 B.4 报表生成 (SANDBOX_ON)")
        print("=" * 80)

        buckets = db.fetch_store_ops_daily_buckets(
            shop_domains=shops, date_start=TARGET_DATE, date_end=TARGET_DATE
        ) or []
        print(f"  销售 buckets 行数: {len(buckets)}")

        payload = build_store_ops_report_payload(
            shop_domains=shops,
            date_start=TARGET_DATE,
            date_end=TARGET_DATE,
            buckets=buckets,
            active_operators=VIRTUAL_OPERATORS,
        )
        merge_fb_spend_into_payload(payload, after_by_shop)

        for shop in payload.get("shops", []):
            print(f"\n  === {shop['shop_domain']} ===")
            print(f"    unattributed_fb_spend = {shop.get('unattributed_fb_spend', 0):.2f}")
            print(f"    {'slug':<15} {'fb_spend':>10} {'total_sales':>12} "
                  f"{'roas':>8} {'employee_sales':>14} {'public_pool_share':>18}")
            for row in shop.get("employee_rows", []):
                print(
                    f"    {row['employee_slug']:<15} "
                    f"{float(row.get('fb_spend') or 0):>10.2f} "
                    f"{float(row.get('total_sales') or 0):>12.2f} "
                    f"{(float(row['roas']) if row.get('roas') is not None else 0.0):>8.2f} "
                    f"{float(row.get('employee_sales') or 0):>14.2f} "
                    f"{float(row.get('public_pool_share') or 0):>18.2f}"
                )

        print("\n" + "=" * 80)
        print("  守恒性检查")
        print("=" * 80)

        total_raw = Decimal("0")
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(c.spend), 0) AS total
                    FROM fb_campaign_spend_daily c
                    INNER JOIN store_ops_shop_ad_whitelist w
                            ON w.ad_account_id COLLATE utf8mb4_unicode_ci
                             = c.ad_account_id COLLATE utf8mb4_unicode_ci
                           AND w.is_enabled = 1
                    WHERE c.stat_date = %s
                    """,
                    (TARGET_DATE,),
                )
                row = cur.fetchone()
                total_raw = Decimal(str(row["total"] or 0))

        total_distributed = sum(
            float(v) for shop_d in after_by_shop.values() for v in shop_d.values()
        )
        print(f"  DB 原始合计（2026-04-21 已启用账户）: {float(total_raw):.2f}")
        print(f"  分流后合计 (含 _unattributed)     : {total_distributed:.2f}")
        diff = abs(float(total_raw) - total_distributed)
        print(f"  差异: {diff:.6f}  {'[PASS]' if diff < 0.01 else '[FAIL]'}")

        total_attributed = sum(
            float(v) for shop_d in after_by_shop.values()
            for k, v in shop_d.items() if k != "_unattributed"
        )
        total_unattr = sum(
            float(v) for shop_d in after_by_shop.values()
            for k, v in shop_d.items() if k == "_unattributed"
        )
        print(f"  归属员工: {total_attributed:.2f}  "
              f"({100 * total_attributed / float(total_raw):.1f}%)")
        print(f"  未归属:   {total_unattr:.2f}  "
              f"({100 * total_unattr / float(total_raw):.1f}%)")

    finally:
        attr_mod.get_active_operators = orig_fn  # type: ignore
        _invalidate_cache()
        print("\n  [cleanup] monkey-patch 已还原，缓存已清。DB 未被修改。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
