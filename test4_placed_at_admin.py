"""
测试 4：验证店匠 OpenAPI 订单详情中的 placed_at 与后台「成功下单时间」是否一致。

做法：
1. GET /openapi/2025-06/orders/{id} 读取 placed_at（及 created_at 供参考）
2. 使用与 data_sync._get_order_beijing_time 相同的规则，将 placed_at 转为北京时间（无时区 naive）
3. 输出格式与店匠后台常见展示一致：YYYY-MM-DD HH:MM:SS，便于肉眼对比

用法（项目根目录）:
  set SHOPLAZZA_ACCESS_TOKEN=你的token
  python test4_placed_at_admin.py --subdomain newgges --insecure

  python test4_placed_at_admin.py --subdomain newgges --order-ids 2392769-HQWIFA72023 2392769-HQWRIV62110

不修改其它项目文件；依赖 requests、pytz（与 data_sync 一致）。
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pytz
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import parse_iso8601  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

API_VERSION = "2025-06"


def placed_at_to_beijing_naive(time_str: str) -> Optional[datetime]:
    """
    与 data_sync._get_order_beijing_time 中解析逻辑保持一致（仅处理单时间串）。
    """
    if not time_str:
        return None
    try:
        if "Z" in time_str:
            order_dt_utc = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return order_dt_utc.astimezone(pytz.timezone("Asia/Shanghai")).replace(tzinfo=None)
        if "+00:00" in time_str:
            order_dt_utc = datetime.fromisoformat(time_str)
            return order_dt_utc.astimezone(pytz.timezone("Asia/Shanghai")).replace(tzinfo=None)
        if "+08:00" in time_str:
            return datetime.fromisoformat(time_str).replace(tzinfo=None)
        order_dt = parse_iso8601(time_str)
        if order_dt.tzinfo is not None:
            return order_dt.astimezone(pytz.timezone("Asia/Shanghai")).replace(tzinfo=None)
        return order_dt + timedelta(hours=8)
    except Exception:
        return None


def fetch_order(
    base: str, token: str, order_id: str, verify: bool
) -> Dict[str, Any]:
    headers = {"access-token": token, "Accept": "application/json"}
    r = requests.get(f"{base}/orders/{order_id}", headers=headers, timeout=60, verify=verify)
    r.raise_for_status()
    return r.json()


def unwrap_order(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not payload or payload.get("code") not in (None, "Success"):
        return None
    data = payload.get("data")
    if isinstance(data, dict) and "order" in data:
        return data["order"]
    return payload.get("order")


def main() -> None:
    parser = argparse.ArgumentParser(description="测试4：placed_at 与后台成功下单时间对照")
    parser.add_argument("--subdomain", default="newgges", help="店铺子域")
    parser.add_argument(
        "--order-ids",
        nargs="*",
        default=[
            "2392769-HQWIFA72023",
            "2392769-HQWRIV62110",
            "2392769-HQWKVH39299",
        ],
        help="要验证的订单 ID 列表（默认三条 newgges 联调用例）",
    )
    parser.add_argument("--insecure", action="store_true", help="跳过 HTTPS 证书校验")
    args = parser.parse_args()

    token = os.getenv("SHOPLAZZA_ACCESS_TOKEN", "").strip()
    if not token:
        token = input("请输入 access-token: ").strip()
    if not token:
        print("未提供 token", file=sys.stderr)
        sys.exit(1)

    sub = args.subdomain.strip().replace("https://", "").replace("http://", "").rstrip("/")
    base = f"https://{sub}.myshoplaza.com/openapi/{API_VERSION}"
    verify_ssl = not args.insecure

    print("=" * 70)
    print("测试 4：placed_at（API）→ 北京时间，与店匠后台「成功下单」人工对照")
    print(f"接口: {base}/orders/{{id}}")
    print("=" * 70)
    print(
        "\n请打开店匠后台订单详情，查看「成功下单」时间，与下方「placed_at→北京」一行对比。\n"
        "若一致，则统计口径可采用 placed_at；若不一致，记录差异订单并反馈。\n"
    )

    for oid in args.order_ids:
        print("-" * 70)
        print(f"订单 ID: {oid}")
        try:
            payload = fetch_order(base, token, oid, verify_ssl)
            order = unwrap_order(payload)
            if not order:
                print(f"  响应异常: {json_snippet(payload)}")
                continue
            pa = order.get("placed_at") or ""
            ca = order.get("created_at") or ""
            ua = order.get("updated_at") or ""
            bt = placed_at_to_beijing_naive(pa) if pa else None
            print(f"  placed_at (API 原始): {pa or '(空)'}")
            print(f"  created_at (参考):    {ca or '(空)'}")
            print(f"  updated_at (参考):    {ua or '(空)'}")
            if bt:
                print(f"  placed_at → 北京时间: {bt.strftime('%Y-%m-%d %H:%M:%S')}  （用于与后台「成功下单」对比）")
            else:
                print("  placed_at → 北京时间: 解析失败")
        except requests.RequestException as e:
            print(f"  请求失败: {e}")

    print("-" * 70)
    print("结束。若三条均一致，测试 4 通过。")


def json_snippet(d: Any, n: int = 240) -> str:
    import json

    s = json.dumps(d, ensure_ascii=False)[:n]
    return s + ("..." if len(json.dumps(d, ensure_ascii=False)) > n else "")


if __name__ == "__main__":
    main()
