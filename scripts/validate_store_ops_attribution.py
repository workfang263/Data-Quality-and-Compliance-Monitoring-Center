"""
店铺运营归因：只读校验（最近 N 个自然日，默认 7 天，含当天）。

1) 一致性：用 source_url + last_landing_url 重放 resolve_attribution，与库中
   attribution_type / employee_slug / utm_decision 比对。
2) 口径提示：末次归因(last)且首次 utm 子串命中某员工、但归因员工不同——与店匠
   「来源含某活动名」报表可能不一致（非错误，仅清单）。

用法（项目根目录）：
  python scripts/validate_store_ops_attribution.py
  python scripts/validate_store_ops_attribution.py --days 7
  python scripts/validate_store_ops_attribution.py --csv out/validate_store_ops.csv
  python scripts/validate_store_ops_attribution.py --examples
  python scripts/validate_store_ops_attribution.py --examples --example-each 5

依赖：根目录 .env 中数据库配置（与后端相同）。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.services.database_new import Database  # noqa: E402
from app.services.store_ops_attribution import (  # noqa: E402
    extract_utm,
    landing_has_utm_source_param,
    match_employee_slug,
    resolve_attribution,
)


def _norm_slug(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _norm_decision(v: Any) -> str:
    return (v or "").strip() or ""


def _price_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return str(v)
    return str(v)


def _utm_prefix(utm: Optional[str], max_len: int = 80) -> str:
    if not utm:
        return ""
    u = utm.strip()
    return u if len(u) <= max_len else u[: max_len - 3] + "..."


def row_utm_slugs(row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str, str]:
    """(首次 utm 命中的员工 slug, 末次 utm 命中的 slug, 首次串前缀, 末次串前缀)"""
    src = row.get("source_url")
    last = row.get("last_landing_url")
    u_f = extract_utm(src if isinstance(src, str) else None)
    u_l = extract_utm(last if isinstance(last, str) else None)
    return (
        match_employee_slug(u_f),
        match_employee_slug(u_l),
        _utm_prefix(u_f),
        _utm_prefix(u_l),
    )


def fetch_rows(db: Database, d_start: date, d_end: date) -> List[Dict[str, Any]]:
    sql = """
        SELECT shop_domain, order_id, biz_date, total_price, currency,
               attribution_type, employee_slug, utm_decision,
               source_url, last_landing_url
        FROM store_ops_order_attributions
        WHERE biz_date >= %s AND biz_date <= %s
        ORDER BY shop_domain, biz_date, order_id
    """
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (d_start, d_end))
            return list(cursor.fetchall())


def analyze_row(row: Dict[str, Any]) -> Tuple[bool, bool, Tuple[str, Optional[str], str]]:
    """返回 (与库一致, 口径提示行, 重放三元组)。"""
    src = row.get("source_url")
    last = row.get("last_landing_url")
    rec_type, rec_slug, rec_decision = resolve_attribution(src, last)

    db_type = (row.get("attribution_type") or "").strip()
    db_slug = _norm_slug(row.get("employee_slug"))
    db_dec = _norm_decision(row.get("utm_decision"))

    consistent = (
        db_type == rec_type
        and db_slug == _norm_slug(rec_slug)
        and db_dec == rec_decision
    )

    # 与店匠「首次活动名含某员工」可能不一致：末次决策且首次 utm 命中 A、库中员工为 B
    first_slug = match_employee_slug(extract_utm(src if isinstance(src, str) else None))
    shop_hint = False
    if (
        db_type == "employee"
        and db_dec == "last"
        and first_slug is not None
        and db_slug is not None
        and first_slug != db_slug
        and landing_has_utm_source_param(last if isinstance(last, str) else None)
    ):
        shop_hint = True

    return consistent, shop_hint, (rec_type, rec_slug, rec_decision)


def _print_one_example(row: Dict[str, Any], extra: str = "") -> None:
    fs, ls, p_f, p_l = row_utm_slugs(row)
    slug = row.get("employee_slug") or "-"
    dec = row.get("utm_decision") or "-"
    at = row.get("attribution_type") or "-"
    oid = row.get("order_id")
    shop = row.get("shop_domain")
    bd = row.get("biz_date")
    price = _price_str(row.get("total_price"))
    cur = row.get("currency") or ""
    hit = f"首次命中={fs or '-'} | 末次命中={ls or '-'}"
    tail = f" {extra}" if extra else ""
    print(
        f"  · 订单 {oid} | {shop} | {bd} | {price} {cur} | "
        f"type={at} 归因={slug} decision={dec} | {hit}{tail}\n"
        f"    首次 utm: {p_f or '(无)'}\n"
        f"    末次 utm: {p_l or '(无)'}"
    )


def print_categorized_examples(rows: List[Dict[str, Any]], each: int) -> None:
    """每类最多 each 条：双运营末次胜、公共池、首次链、末次链（末次与首次同人或仅末次命中）。"""
    dual: List[Dict[str, Any]] = []
    public_l: List[Dict[str, Any]] = []
    first_l: List[Dict[str, Any]] = []
    last_pure: List[Dict[str, Any]] = []

    dual_ids = set()
    for row in rows:
        _, shop_hint, _ = analyze_row(row)
        db_type = (row.get("attribution_type") or "").strip()
        db_dec = _norm_decision(row.get("utm_decision"))
        if shop_hint and len(dual) < each:
            dual.append(row)
            dual_ids.add(row.get("order_id"))
        if db_type == "public_pool" and len(public_l) < each:
            public_l.append(row)
        if db_dec in ("first", "first_fallback") and len(first_l) < each:
            first_l.append(row)

    for row in rows:
        if len(last_pure) >= each:
            break
        db_type = (row.get("attribution_type") or "").strip()
        db_dec = _norm_decision(row.get("utm_decision"))
        if db_type != "employee" or db_dec != "last":
            continue
        oid = row.get("order_id")
        if oid in dual_ids:
            continue
        fs, ls, _, _ = row_utm_slugs(row)
        db_slug = _norm_slug(row.get("employee_slug"))
        # 「纯末次」示例：末次决策且（首次未命中任何人，或首次与归因一致）
        if fs is None or fs == db_slug:
            last_pure.append(row)

    if len(last_pure) < each:
        for row in rows:
            if len(last_pure) >= each:
                break
            db_type = (row.get("attribution_type") or "").strip()
            db_dec = _norm_decision(row.get("utm_decision"))
            if db_type != "employee" or db_dec != "last":
                continue
            if row.get("order_id") in dual_ids:
                continue
            if row in last_pure:
                continue
            last_pure.append(row)

    print()
    print("========== 示例订单（便于对照店匠后台；每类至多 {} 条）==========".format(each))

    print("\n【1】首次 utm 与末次 utm 各命中不同运营，规则取末次运营")
    if not dual:
        print("  （本窗口内无样本）")
    for row in dual:
        fs, ls, _, _ = row_utm_slugs(row)
        _print_one_example(row, extra=f"→ 归因取末次: {ls}")

    print("\n【2】公共池（无明确员工或末次无命中且首次也无）")
    if not public_l:
        print("  （本窗口内无样本）")
    for row in public_l:
        _print_one_example(row)

    print("\n【3】按「首次」得到当前归因运营（utm_decision=first 或 first_fallback）")
    if not first_l:
        print("  （本窗口内无样本）")
    for row in first_l:
        dec = _norm_decision(row.get("utm_decision"))
        note = "（末次带 utm 参数但未命中员工，回退首次）" if dec == "first_fallback" else "（末次落地无 utm_source 参数，用首次）"
        _print_one_example(row, extra=note)

    print("\n【4】按「末次」得到当前归因运营，且非「双运营抢末次」类（首次未命中或首次与归因一致）")
    if not last_pure:
        print("  （本窗口内无样本）")
    for row in last_pure:
        _print_one_example(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 store_ops_order_attributions 归因是否与规则一致")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="自然日天数，含结束日（默认 7，即今天起往前共 7 天）",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="",
        help="可选：写出 CSV 路径（相对项目根或绝对路径）",
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="打印分类示例订单（双运营末次胜 / 公共池 / 首次归因 / 末次归因）",
    )
    parser.add_argument(
        "--example-each",
        type=int,
        default=3,
        help="与 --examples 联用：每类最多几条（默认 3）",
    )
    args = parser.parse_args()
    if args.days < 1:
        print("error: --days 须 >= 1", file=sys.stderr)
        return 2

    d_end = date.today()
    d_start = d_end - timedelta(days=args.days - 1)

    db = Database()
    rows = fetch_rows(db, d_start, d_end)
    n = len(rows)
    n_bad = 0
    n_shop_hint = 0
    bad_samples: List[Dict[str, Any]] = []

    csv_path = args.csv.strip()
    csv_file = None
    writer = None
    if csv_path:
        out_abs = csv_path if os.path.isabs(csv_path) else os.path.join(_ROOT, csv_path)
        os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
        csv_file = open(out_abs, "w", newline="", encoding="utf-8-sig")
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "shop_domain",
                "order_id",
                "biz_date",
                "total_price",
                "currency",
                "db_attribution_type",
                "db_employee_slug",
                "db_utm_decision",
                "recomputed_type",
                "recomputed_slug",
                "recomputed_decision",
                "consistent",
                "shop_report_divergence_hint",
                "first_utm_prefix",
                "last_utm_prefix",
            ]
        )

    for row in rows:
        consistent, shop_hint, (rt, rs, rd) = analyze_row(row)
        if not consistent:
            n_bad += 1
            bad_samples.append(row)
        if shop_hint:
            n_shop_hint += 1

        u_first = extract_utm(row.get("source_url") if isinstance(row.get("source_url"), str) else None)
        u_last = extract_utm(
            row.get("last_landing_url") if isinstance(row.get("last_landing_url"), str) else None
        )

        if writer:
            writer.writerow(
                [
                    row.get("shop_domain"),
                    row.get("order_id"),
                    row.get("biz_date"),
                    _price_str(row.get("total_price")),
                    row.get("currency") or "",
                    row.get("attribution_type"),
                    row.get("employee_slug") or "",
                    row.get("utm_decision") or "",
                    rt,
                    rs or "",
                    rd,
                    "yes" if consistent else "no",
                    "yes" if shop_hint else "no",
                    _utm_prefix(u_first),
                    _utm_prefix(u_last),
                ]
            )

    if csv_file:
        csv_file.close()
        print(f"已写入 CSV: {out_abs}")

    sum_price_bad = Decimal("0")
    for r in bad_samples:
        p = r.get("total_price")
        if p is not None:
            sum_price_bad += Decimal(str(p))

    print(
        f"日期范围: {d_start} ~ {d_end}（共 {args.days} 天）\n"
        f"扫描行数: {n}\n"
        f"重放与库不一致: {n_bad}"
        + (f"（涉及金额合计约 {sum_price_bad}）" if n_bad else "")
        + "\n"
        f"口径提示（末次归因且首次 utm 命中他人）: {n_shop_hint}"
    )

    if n_bad and n <= 20:
        print("\n不一致明细（行数较少时全量列出）:")
        for row in bad_samples:
            c, _, (rt, rs, rd) = analyze_row(row)
            if not c:
                print(
                    f"  {row.get('shop_domain')} {row.get('order_id')} "
                    f"db=({row.get('attribution_type')},{row.get('employee_slug')},{row.get('utm_decision')}) "
                    f"recomputed=({rt},{rs},{rd})"
                )
    elif n_bad:
        print(f"\n不一致样本较多，请用 --csv 导出后筛选 consistent=no。")

    if args.examples:
        if args.example_each < 1:
            print("error: --example-each 须 >= 1", file=sys.stderr)
            return 2
        print_categorized_examples(rows, args.example_each)

    return 1 if n_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
