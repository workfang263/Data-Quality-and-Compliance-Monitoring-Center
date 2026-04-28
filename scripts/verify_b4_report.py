"""
B.4 活体验证：用真实库的数据跑一次端到端聚合，验收 3 个要点：
  1. `fetch_store_ops_fb_spend_by_shop_slug` 新口径返回值结构正确
     （含 `_unattributed` key）；
  2. 每店的 sum(by_slug) + _unattributed == fb_campaign_spend_daily 该店
     启用白名单账户当日总和（**总额守恒**）；
  3. merge 后 payload 中：
      - employee_rows.fb_spend 总和 + unattributed_fb_spend == 步骤 2 的店总额
      - 员工行未出现 `_unattributed` slug
      - 运营名单顺序跟 store_ops_employee_config.sort_order 一致
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from decimal import Decimal
from typing import Any, Dict, List

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
for p in (_ROOT, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.database_new import Database  # type: ignore
from app.services.store_ops_attribution import get_active_operators  # type: ignore
from app.services.store_ops_report import (  # type: ignore
    build_store_ops_report_payload,
    merge_fb_spend_into_payload,
)


def _d(x) -> Decimal:
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _fetch_ground_truth_total(db: Database, shop: str, d0: dt.date, d1: dt.date) -> Decimal:
    """店铺在区间内、所有"启用"的广告账户花费总额——作为对照基准。"""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(c.spend), 0) AS s
                FROM fb_campaign_spend_daily c
                INNER JOIN store_ops_shop_ad_whitelist w
                        ON w.ad_account_id COLLATE utf8mb4_unicode_ci
                         = c.ad_account_id COLLATE utf8mb4_unicode_ci
                       AND w.is_enabled = 1
                       AND w.shop_domain COLLATE utf8mb4_unicode_ci = %s
                WHERE c.stat_date >= %s AND c.stat_date <= %s
                """,
                (shop, d0, d1),
            )
            row = cur.fetchone() or {}
            return _d(row.get("s"))


def _fetch_shops(db: Database) -> List[str]:
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT shop_domain FROM store_ops_shop_whitelist "
                "WHERE is_enabled = 1 ORDER BY id"
            )
            rows = cur.fetchall() or []
    return [r["shop_domain"] for r in rows]


def main() -> int:
    d0 = dt.date(2026, 4, 21)
    d1 = dt.date(2026, 4, 21)
    print(f"\n===== B.4 活体验证 区间 [{d0} ~ {d1}] =====\n")

    db = Database()

    ops = get_active_operators()
    print(f"[运营] active 数量 = {len(ops)}，排序如下：")
    for i, op in enumerate(ops, 1):
        print(
            f"  {i}. slug={op.get('employee_slug'):<10} "
            f"sort_order={op.get('sort_order')} "
            f"utm_keyword={op.get('utm_keyword')!r}  "
            f"campaign_keyword={op.get('campaign_keyword')!r}"
        )

    shops = _fetch_shops(db)
    print(f"\n[店铺] 启用中共 {len(shops)} 家：{shops}")
    if not shops:
        print("  !! 子系统未配置任何启用店铺，结束。")
        return 0

    overall_ok = True
    buckets = db.fetch_store_ops_daily_buckets(shops, d0, d1)
    print(f"\n[订单分摊] fetch_store_ops_daily_buckets 返回 {len(buckets)} 行")

    payload = build_store_ops_report_payload(shops, d0, d1, buckets)

    spend_by_shop: Dict[str, Dict[str, Decimal]] = {}
    for s in shops:
        spend_by_shop[s] = db.fetch_store_ops_fb_spend_by_shop_slug(s, d0, d1)
    merge_fb_spend_into_payload(payload, spend_by_shop)

    for shop_payload in payload["shops"]:
        shop = shop_payload["shop_domain"]
        ground = _fetch_ground_truth_total(db, shop, d0, d1).quantize(Decimal("0.01"))

        spend_map = spend_by_shop.get(shop, {}) or {}
        slug_sum = sum(
            (_d(v) for k, v in spend_map.items() if k != "_unattributed"),
            Decimal("0"),
        )
        unattr = _d(spend_map.get("_unattributed", 0))
        summed = (slug_sum + unattr).quantize(Decimal("0.01"))

        rows = shop_payload.get("employee_rows") or []
        payload_fb_sum = Decimal("0")
        for r in rows:
            payload_fb_sum += _d(r.get("fb_spend"))
        payload_unattr = _d(shop_payload.get("unattributed_fb_spend"))
        payload_total = (payload_fb_sum + payload_unattr).quantize(Decimal("0.01"))

        slugs_in_rows = [r["employee_slug"] for r in rows]
        has_underscore = "_unattributed" in slugs_in_rows

        diff1 = abs(summed - ground)
        diff2 = abs(payload_total - ground)
        ok_conservation = diff1 < Decimal("0.01") and diff2 < Decimal("0.01")
        ok_no_leak = not has_underscore

        status = "OK" if (ok_conservation and ok_no_leak) else "FAIL"
        print(f"\n--- [{status}] {shop} ---")
        print(f"  ground truth (启用账户总花费)       = {ground}")
        print(f"  fetch_..._by_shop_slug 求和        = {summed}")
        print(f"      其中 slug 命中           = {slug_sum.quantize(Decimal('0.01'))}")
        print(f"      其中 _unattributed       = {unattr.quantize(Decimal('0.01'))}")
        print(f"  payload employee_rows.fb_spend 和 = {payload_fb_sum.quantize(Decimal('0.01'))}")
        print(f"  payload unattributed_fb_spend     = {payload_unattr.quantize(Decimal('0.01'))}")
        print(f"  payload 合计                       = {payload_total}")
        print(f"  差额 (fetch 层)  = {diff1}")
        print(f"  差额 (payload)   = {diff2}")
        print(f"  rows 未含 _unattributed slug = {ok_no_leak}")
        print(f"  rows 名单 = {slugs_in_rows}")

        expected_active = [op["employee_slug"] for op in ops]
        head = slugs_in_rows[: len(expected_active)]
        if head != expected_active:
            print(f"  !! 前 {len(expected_active)} 项顺序与 active 不一致")
            overall_ok = False

        top_rows = sorted(rows, key=lambda r: r.get("fb_spend") or 0, reverse=True)[:5]
        print(f"  Top 5 fb_spend:")
        for r in top_rows:
            print(
                f"    - {r['employee_slug']:<10}  fb_spend={r.get('fb_spend')}"
                f"  total_sales={r.get('total_sales')}  roas={r.get('roas')}"
            )

        if not (ok_conservation and ok_no_leak):
            overall_ok = False

    print("\n==========================================")
    print("  结论: ", "全部通过" if overall_ok else "存在异常，请排查")
    print("==========================================\n")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
