"""
阶段二：按店、按北京日汇总明细行，再按公共池规则做虚拟分摊；多日范围按日累加。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List

from app.services.store_ops_constants import EMPLOYEE_SLUGS_ORDERED


def build_store_ops_report_payload(
    shop_domains: List[str],
    date_start: date,
    date_end: date,
    buckets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    buckets: fetch_store_ops_daily_buckets 的原始行列表。
    返回前端可用的 JSON 友好结构（金额用 float，保留两位小数思想在序列化时处理）。
    """
    # (shop, biz_date) -> 当日可归因金额按 slug、公共池金额与单数
    day_keys: Dict[tuple, Dict[str, Any]] = {}

    for r in buckets:
        shop = r["shop_domain"]
        if shop not in shop_domains:
            continue
        bd = r["biz_date"]
        key = (shop, bd)
        if key not in day_keys:
            day_keys[key] = {
                "emp": defaultdict(lambda: Decimal(0)),
                "emp_cnt": defaultdict(int),
                "pub_amt": Decimal(0),
                "pub_cnt": 0,
            }
        amt = Decimal(str(r["sum_price"]))
        cnt = int(r["order_count"])
        if r["attribution_type"] == "public_pool":
            day_keys[key]["pub_amt"] += amt
            day_keys[key]["pub_cnt"] += cnt
        else:
            slug = (r["employee_slug"] or "").strip()
            day_keys[key]["emp"][slug] += amt
            day_keys[key]["emp_cnt"][slug] += cnt

    shop_acc = {
        s: {
            "public_pool_sales": Decimal(0),
            "public_pool_orders": 0,
            "by_slug": {
                slug: {
                    "direct_sales": Decimal(0),
                    "allocated_from_pool": Decimal(0),
                    "direct_orders": 0,
                }
                for slug in EMPLOYEE_SLUGS_ORDERED
            },
        }
        for s in shop_domains
    }

    for (shop, _bd), data in day_keys.items():
        if shop not in shop_acc:
            continue
        P = data["pub_amt"]
        pub_cnt = data["pub_cnt"]
        emp: Dict[str, Decimal] = data["emp"]
        emp_cnt: Dict[str, int] = data["emp_cnt"]
        S = sum(emp.values(), Decimal(0))

        shop_acc[shop]["public_pool_sales"] += P
        shop_acc[shop]["public_pool_orders"] += pub_cnt

        for slug in EMPLOYEE_SLUGS_ORDERED:
            direct = emp.get(slug, Decimal(0))
            d_orders = emp_cnt.get(slug, 0)
            if S > 0:
                allocated = P * (direct / S)
            else:
                allocated = P / Decimal(7)
            shop_acc[shop]["by_slug"][slug]["direct_sales"] += direct
            shop_acc[shop]["by_slug"][slug]["allocated_from_pool"] += allocated
            shop_acc[shop]["by_slug"][slug]["direct_orders"] += d_orders

    shops_out: List[Dict[str, Any]] = []
    for s in shop_domains:
        acc = shop_acc[s]
        rows: List[Dict[str, Any]] = []
        for slug in EMPLOYEE_SLUGS_ORDERED:
            b = acc["by_slug"][slug]
            d = b["direct_sales"]
            a = b["allocated_from_pool"]
            rows.append(
                {
                    "employee_slug": slug,
                    "direct_sales": _d(d),
                    "allocated_from_public_pool": _d(a),
                    "total_sales": _d(d + a),
                    "direct_order_count": b["direct_orders"],
                }
            )
        shops_out.append(
            {
                "shop_domain": s,
                "public_pool_sales_total": _d(acc["public_pool_sales"]),
                "public_pool_order_count": acc["public_pool_orders"],
                "employee_rows": rows,
            }
        )

    return {
        "date_start": date_start.isoformat(),
        "date_end": date_end.isoformat(),
        "shops": shops_out,
    }


def merge_fb_spend_into_payload(
    payload: Dict[str, Any],
    spend_by_shop_slug: Dict[str, Dict[str, Decimal]],
) -> None:
    """
    为 payload['shops'][].employee_rows 增加 fb_spend、roas（就地修改）。
    spend_by_shop_slug: shop_domain -> employee_slug -> 区间内 SUM(spend)。
    ROAS：倍数 = total_sales / spend；spend==0 -> roas None；spend>0 且销售额 0 -> roas 0。
    """
    for shop in payload.get("shops") or []:
        domain = shop.get("shop_domain") or ""
        spend_map = spend_by_shop_slug.get(domain, {})
        for row in shop.get("employee_rows") or []:
            slug = row.get("employee_slug") or ""
            total_sales_f = float(row.get("total_sales") or 0)
            spend_dec = spend_map.get(slug, Decimal("0"))
            if spend_dec < 0:
                spend_dec = Decimal("0")
            row["fb_spend"] = float(spend_dec.quantize(Decimal("0.01")))
            if spend_dec == 0:
                row["roas"] = None
            elif total_sales_f == 0:
                row["roas"] = 0.0
            else:
                q = (Decimal(str(total_sales_f)) / spend_dec).quantize(Decimal("0.01"))
                row["roas"] = float(q)


def _d(x: Decimal) -> float:
    return float(x.quantize(Decimal("0.0001")))
