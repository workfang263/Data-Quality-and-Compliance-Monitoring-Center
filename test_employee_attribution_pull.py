"""
独立测试脚本：按北京时间拉取指定日期的店匠订单列表，并抽样订单详情，
验证「员工归因」所需的字段是否存在。

- 复用项目内 data_sync 同款时间边界：utils.datetime_to_iso8601（+08:00）
- 不修改任何其它项目文件；仅新增本脚本
- Token 请交互输入或使用环境变量 SHOPLAZZA_ACCESS_TOKEN

用法（在项目根目录）:
  python test_employee_attribution_pull.py
  python test_employee_attribution_pull.py --dates 2026-04-02 2026-04-03
  python test_employee_attribution_pull.py --subdomain newgges --sample-detail 3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, time as dt_time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests

# 仅引用工具函数，不改动其它文件
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import datetime_to_iso8601  # noqa: E402

# 与 test_shoplazza.py / 官方文档测试一致的 OpenAPI 版本
DEFAULT_API_VERSION = "2025-06"
DEFAULT_LIMIT = 50


def _utf8_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def beijing_day_placed_at_range(d: date) -> tuple[str, str]:
    """
    某一「北京日历日」的 placed_at_min / placed_at_max（与 data_sync 一致：naive 本地日界 + +08:00 ISO）。
    """
    start = datetime(d.year, d.month, d.day, 0, 0, 0)
    end = datetime(d.year, d.month, d.day, 23, 59, 59)
    return datetime_to_iso8601(start), datetime_to_iso8601(end)


def unwrap_orders(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """兼容 { data: { orders } } 与旧式 { orders }。"""
    if not payload:
        return []
    if isinstance(payload.get("data"), dict):
        orders = payload["data"].get("orders")
        if orders:
            return list(orders)
    raw = payload.get("orders")
    return list(raw) if raw else []


def unwrap_cursor(payload: Optional[Dict[str, Any]]) -> Optional[str]:
    if not payload:
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        c = data.get("cursor")
        if c:
            return str(c)
    return None


def fetch_orders_page(
    base_url: str,
    token: str,
    placed_at_min: str,
    placed_at_max: str,
    page: int,
    limit: int,
    cursor: Optional[str],
    verify: bool,
) -> Dict[str, Any]:
    headers = {
        "access-token": token,
        "Accept": "application/json",
    }
    params: Dict[str, Any] = {
        "placed_at_min": placed_at_min,
        "placed_at_max": placed_at_max,
        "limit": str(limit),
    }
    if cursor:
        params["cursor"] = cursor
    else:
        params["page"] = str(page)

    r = requests.get(
        f"{base_url}/orders",
        headers=headers,
        params=params,
        timeout=60,
        verify=verify,
    )
    r.raise_for_status()
    return r.json()


def fetch_order_detail(
    base_url: str, token: str, order_id: str, verify: bool
) -> Dict[str, Any]:
    headers = {
        "access-token": token,
        "Accept": "application/json",
    }
    r = requests.get(
        f"{base_url}/orders/{order_id}",
        headers=headers,
        timeout=60,
        verify=verify,
    )
    r.raise_for_status()
    return r.json()


def extract_utm(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        q = parse_qs(urlparse(url.strip()).query)
        v = q.get("utm_source")
        if v:
            return unquote(v[0].strip())
    except Exception:
        pass
    return None


def summarize_list_order(o: Dict[str, Any]) -> Dict[str, Any]:
    """列表单条：标出归因相关字段是否出现（列表接口常不含 source）。"""
    oid = o.get("id")
    keys_needed = (
        "id",
        "total_price",
        "currency",
        "financial_status",
        "placed_at",
        "created_at",
        "source",
        "last_landing_url",
    )
    present = {k: (k in o and o.get(k) not in (None, "")) for k in keys_needed}
    return {
        "order_id": oid,
        "fields_present_in_list_response": present,
        "hint": "若 source/last_landing_url 为 false，通常需订单详情接口补全",
    }


def summarize_detail_order(order: Dict[str, Any]) -> Dict[str, Any]:
    src = order.get("source")
    last = order.get("last_landing_url")
    return {
        "order_id": order.get("id"),
        "total_price": order.get("total_price"),
        "currency": order.get("currency"),
        "financial_status": order.get("financial_status"),
        "placed_at": order.get("placed_at"),
        "has_source": bool(src),
        "has_last_landing_url": bool(last),
        "utm_source_from_source": extract_utm(src if isinstance(src, str) else None),
        "utm_source_from_last_landing": extract_utm(last if isinstance(last, str) else None),
        "source_preview": (src[:120] + "…") if isinstance(src, str) and len(src) > 120 else src,
        "last_landing_preview": (last[:120] + "…")
        if isinstance(last, str) and len(last) > 120
        else last,
    }


def pull_day(
    base_url: str,
    token: str,
    day: date,
    limit: int,
    verify: bool,
) -> tuple[List[Dict[str, Any]], int]:
    """拉取单日 placed_at 落在该北京日内的全部订单（先尝试 cursor，否则按 page 递增）。"""
    pmin, pmax = beijing_day_placed_at_range(day)
    all_rows: List[Dict[str, Any]] = []
    page = 1
    cursor: Optional[str] = None
    max_rounds = 500
    use_cursor: Optional[bool] = None

    for _ in range(max_rounds):
        payload = fetch_orders_page(
            base_url,
            token,
            pmin,
            pmax,
            page=page,
            limit=limit,
            cursor=cursor,
            verify=verify,
        )
        code = payload.get("code")
        if code and code != "Success":
            raise RuntimeError(f"API code={code}, body={payload}")

        batch = unwrap_orders(payload)
        all_rows.extend(batch)

        data_block = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        next_c = data_block.get("cursor") or unwrap_cursor(payload)
        has_more = bool(data_block.get("has_more"))

        if not batch:
            break

        # 首次根据返回决定分页方式：有 cursor/has_more 则走游标
        if use_cursor is None:
            use_cursor = bool(has_more and next_c)

        if use_cursor:
            if has_more and next_c:
                cursor = str(next_c)
                continue
            break

        # page 模式（与 shoplazza_api.get_orders_all_pages 一致）
        if len(batch) < limit:
            break
        page += 1

    return all_rows, len(all_rows)


def main() -> None:
    _utf8_stdio()
    parser = argparse.ArgumentParser(
        description="测试按北京时间拉取订单列表 + 抽样详情字段（员工归因联调）"
    )
    parser.add_argument(
        "--subdomain",
        default="newgges",
        help="店铺子域，默认 newgges（对应 newgges.myshoplaza.com）",
    )
    parser.add_argument(
        "--dates",
        nargs="+",
        default=["2026-04-02", "2026-04-03"],
        help="北京日历日，格式 YYYY-MM-DD，默认 4月2日与4月3日",
    )
    parser.add_argument(
        "--api-version",
        default=DEFAULT_API_VERSION,
        help=f"OpenAPI 路径版本，默认 {DEFAULT_API_VERSION}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="列表每页条数（最大视店匠限制，可先 50 或 250）",
    )
    parser.add_argument(
        "--sample-detail",
        type=int,
        default=2,
        help="每个统计日抽样拉取详情的订单条数（默认 2）",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="跳过 HTTPS 证书校验（本机调试 CERTIFICATE_VERIFY_FAILED 时使用）",
    )
    args = parser.parse_args()

    token = os.getenv("SHOPLAZZA_ACCESS_TOKEN", "").strip()
    if not token:
        token = input("请输入 access-token（输入不回显可用环境变量 SHOPLAZZA_ACCESS_TOKEN）: ").strip()
    if not token:
        print("错误: 未提供 token。", file=sys.stderr)
        sys.exit(1)

    sub = args.subdomain.strip().replace("https://", "").replace("http://", "").rstrip("/")
    base_url = f"https://{sub}.myshoplaza.com/openapi/{args.api_version}"
    verify_ssl = not args.insecure

    print("=" * 60)
    print("店匠订单拉取测试（员工归因字段检查）")
    print(f"Base: {base_url}")
    print(f"placed_at 范围：按北京日界，使用 utils.datetime_to_iso8601（+08:00）")
    print("=" * 60)

    for ds in args.dates:
        d = date.fromisoformat(ds)
        pmin, pmax = beijing_day_placed_at_range(d)
        print(f"\n>>> 北京日期 {ds}")
        print(f"    placed_at_min = {pmin}")
        print(f"    placed_at_max = {pmax}")

        orders, count = pull_day(base_url, token, d, args.limit, verify_ssl)
        print(f"    列表累计订单数: {count}")

        if not orders:
            print("    （无订单或请求失败，请检查 token / 网络 / SSL）")
            continue

        # 列表字段抽样：只看第一条
        sample0 = summarize_list_order(orders[0])
        print("    列表首条字段存在性:")
        print(json.dumps(sample0, ensure_ascii=False, indent=2))

        n_detail = min(args.sample_detail, len(orders))
        print(f"    抽样详情 {n_detail} 条 (GET /orders/{{id}}):")
        for i in range(n_detail):
            oid = orders[i].get("id")
            if not oid:
                continue
            try:
                detail_resp = fetch_order_detail(base_url, token, oid, verify_ssl)
                order_obj = (detail_resp.get("data") or {}).get("order") or detail_resp.get(
                    "order"
                )
                if not isinstance(order_obj, dict):
                    print(f"      [{i}] {oid} 详情结构异常: {list(detail_resp.keys())}")
                    continue
                sm = summarize_detail_order(order_obj)
                print(json.dumps(sm, ensure_ascii=False, indent=2))
            except Exception as exc:
                print(f"      [{i}] {oid} 详情失败: {exc}")


if __name__ == "__main__":
    main()
