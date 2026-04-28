"""
阶段二：按店、按北京日汇总明细行，再按公共池规则做虚拟分摊；多日范围按日累加。

B.4 重构点：
  - 员工行（employee_rows）不再依赖硬编码 `EMPLOYEE_SLUGS_ORDERED`，
    改由 `store_ops_employee_config` 表驱动（`get_active_operators()`），
    按 `sort_order` 排序；DB 读取失败时回退到常量名单做保命兜底。
  - 对历史数据中出现、但当前已不在 active 名单里的 slug（例如某运营离职被停用），
    仍保留其行，避免历史销售额"凭空消失"，按字母序追加在动态名单之后。
  - 分摊分母使用「当日实际参与分摊的 slug 数」，而不是硬编码 8。
  - `merge_fb_spend_into_payload` 识别特殊 key `_unattributed`，
    写入到 shop 级别字段 `unattributed_fb_spend`，前端目前不渲染但已可观测。
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.services.store_ops_constants import EMPLOYEE_SLUGS_ORDERED

logger = logging.getLogger(__name__)


# ========== 内部工具 ==========

def _resolve_active_slugs(
    active_operators: Optional[List[Dict[str, Any]]],
) -> List[str]:
    """返回按顺序排列的 active 运营 slug 列表。
    优先用传入参数；否则调 `get_active_operators()`；再不行用常量兜底。
    """
    ops = active_operators
    if ops is None:
        try:
            from app.services.store_ops_attribution import get_active_operators
            ops = get_active_operators()
        except Exception as e:
            logger.warning("build_store_ops_report_payload 无法加载 active 运营: %s", e)
            ops = []

    slugs = [
        (op.get("employee_slug") or "").strip()
        for op in (ops or [])
        if op.get("employee_slug")
    ]
    slugs = [s for s in slugs if s]

    if not slugs:
        # 极端兜底：直接用常量名单，保证报表不至于整表空掉
        logger.warning("active 运营名单为空，回退 EMPLOYEE_SLUGS_ORDERED 常量")
        slugs = list(EMPLOYEE_SLUGS_ORDERED)
    return slugs


def _collect_all_slugs(
    active_slugs: List[str],
    day_keys: Dict[tuple, Dict[str, Any]],
) -> List[str]:
    """最终报表 slug 顺序：active 名单优先，历史 slug（非 active）按字母序追加。
    用于确保历史销售额不被吞没。
    """
    seen_in_buckets: set = set()
    for data in day_keys.values():
        for slug in (data["emp"].keys() or []):
            if slug:
                seen_in_buckets.add(slug)
    extras = sorted(s for s in seen_in_buckets if s not in active_slugs)
    return list(active_slugs) + extras


# ========== 主流程 ==========

def build_store_ops_report_payload(
    shop_domains: List[str],
    date_start: date,
    date_end: date,
    buckets: List[Dict[str, Any]],
    active_operators: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """buckets: fetch_store_ops_daily_buckets 的原始行列表。

    返回前端可用的 JSON 友好结构；金额用 float（保留 4 位，前端再格式化）。
    """
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

    active_slugs = _resolve_active_slugs(active_operators)
    all_slugs = _collect_all_slugs(active_slugs, day_keys)

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
                for slug in all_slugs
            },
        }
        for s in shop_domains
    }

    # 分摊分母：优先用 active 名单长度（当日无直销时用于均摊）
    allocation_divisor = Decimal(max(1, len(active_slugs)))

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

        for slug in all_slugs:
            direct = emp.get(slug, Decimal(0))
            d_orders = emp_cnt.get(slug, 0)
            if S > 0:
                allocated = P * (direct / S) if direct > 0 else Decimal(0)
            else:
                # 当日无任何直销：公共池按 active 名单均摊
                # 历史/离职 slug 不参与均摊（divisor 只算 active）
                allocated = (P / allocation_divisor) if slug in active_slugs else Decimal(0)
            shop_acc[shop]["by_slug"][slug]["direct_sales"] += direct
            shop_acc[shop]["by_slug"][slug]["allocated_from_pool"] += allocated
            shop_acc[shop]["by_slug"][slug]["direct_orders"] += d_orders

    shops_out: List[Dict[str, Any]] = []
    for s in shop_domains:
        acc = shop_acc[s]
        rows: List[Dict[str, Any]] = []
        for slug in all_slugs:
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
                # 先占位，随后在 merge_fb_spend_into_payload 里填真实值
                "unattributed_fb_spend": 0.0,
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
    """为 payload['shops'][].employee_rows 增加 fb_spend、roas（就地修改）。

    spend_by_shop_slug: shop_domain -> {employee_slug: Decimal, "_unattributed": Decimal}
      - 命中运营的花费写到对应 employee_rows.fb_spend
      - 特殊 key `_unattributed` 汇总到 shop 级字段 `unattributed_fb_spend`
    ROAS：倍数 = total_sales / spend；spend==0 -> roas None；spend>0 且销售额 0 -> roas 0。
    """
    for shop in payload.get("shops") or []:
        domain = shop.get("shop_domain") or ""
        spend_map = spend_by_shop_slug.get(domain, {}) or {}

        unattributed_raw = spend_map.get("_unattributed", Decimal("0"))
        try:
            unattributed_dec = (
                unattributed_raw if isinstance(unattributed_raw, Decimal)
                else Decimal(str(unattributed_raw or 0))
            )
        except Exception:
            unattributed_dec = Decimal("0")
        if unattributed_dec < 0:
            unattributed_dec = Decimal("0")
        shop["unattributed_fb_spend"] = float(unattributed_dec.quantize(Decimal("0.01")))

        for row in shop.get("employee_rows") or []:
            slug = row.get("employee_slug") or ""
            total_sales_f = float(row.get("total_sales") or 0)
            spend_dec = spend_map.get(slug, Decimal("0"))
            if not isinstance(spend_dec, Decimal):
                try:
                    spend_dec = Decimal(str(spend_dec or 0))
                except Exception:
                    spend_dec = Decimal("0")
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
