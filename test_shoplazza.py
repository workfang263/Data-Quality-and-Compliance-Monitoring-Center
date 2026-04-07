"""
店匠订单详情测试脚本。

归因相关字段（见官方订单详情 GET /orders/{id}）:
- source: 首次落地页完整 URL，query 里常有 utm_source
- last_landing_url: 末次落地页 URL，query 里常有 utm_source
- placed_at: 成交/支付时间，按业务应以该字段做「北京日历日」归档（与 data_sync 一致需转 Asia/Shanghai）
- refer_info: 有时是 JSON 字符串，一般不含落地页 utm；归因以 source / last_landing_url 为准

Worker「幂等与增量」(原对话第 6 点) 落地要点:
1) 表中以 (shop_domain, order_id) 唯一约束，同步时 INSERT ... ON DUPLICATE KEY UPDATE（或 ORM upsert）
2) 同一订单每小时重复拉取只更新一行，不累加销售额
3) 定时任务按 placed_at_min/max 或 updated_at 窗口拉单，覆盖改价、晚支付等情况
4) 仅回补 2026-04-03：上线时单独跑一段 placed_at 落在该日的全量拉取
"""
import argparse
import json
import os
import sys

# Windows 终端下尽量用 UTF-8 输出中文
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from urllib.parse import parse_qs, unquote, urlparse

import requests


# --- 配置区（建议用环境变量，避免把 token 写进仓库）---
SUBDOMAIN = os.getenv("SHOPLAZZA_SUBDOMAIN", "crispiner")
ACCESS_TOKEN = os.getenv("SHOPLAZZA_ACCESS_TOKEN", "")


def extract_utm_source(url: str | None) -> str | None:
    """从完整 URL 的 query 中取出 utm_source（不做业务白名单判断）。"""
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
        vals = parse_qs(parsed.query).get("utm_source")
        if vals:
            return unquote(vals[0].strip())
    except Exception:
        pass
    return None


def preview_attribution(order: dict) -> dict:
    """
    按你们定义的三场景做只读预览（用于联调）:
    - 无 last_landing_url（空字符串视为无）: 仅用 source 上的 utm_source
    - 有 last_landing_url: 仅用 last_landing_url 上的 utm_source
    - 两者在「所选 URL」上都没有 utm_source: 公共池（本函数不解析员工前缀，只展示原始 utm 串）
    """
    source = order.get("source") or ""
    last = (order.get("last_landing_url") or "").strip()
    utm_first = extract_utm_source(source) if source else None
    utm_last = extract_utm_source(last) if last else None

    if not last:
        scenario = "场景1: 无末次落地页 → 以首次(source)的 utm_source 为准"
        chosen = utm_first
    else:
        scenario = "场景2: 有末次落地页 → 以 last_landing_url 的 utm_source 为准"
        chosen = utm_last

    if chosen is None and not last:
        if utm_first is None:
            scenario = "场景3: 首次/末次均无 utm_source（或末次缺失且首次也无）→ 公共池"
    elif chosen is None and last:
        # 末次存在但 URL 内无 utm_source：是否仍算场景3需产品拍板；此处标出供核对
        scenario += " | 注意: 末次 URL 内未解析到 utm_source"

    return {
        "scenario_hint": scenario,
        "utm_from_source": utm_first,
        "utm_from_last_landing": utm_last,
        "utm_used_for_attribution": chosen,
        "placed_at": order.get("placed_at"),
        "financial_status": order.get("financial_status"),
        "total_price": order.get("total_price"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="拉取店匠单笔订单详情并预览归因字段")
    parser.add_argument(
        "--subdomain",
        default=None,
        help="店铺子域，如 newgges（对应 newgges.myshoplaza.com）；默认读 SHOPLAZZA_SUBDOMAIN 或 crispiner",
    )
    parser.add_argument(
        "--order-id",
        dest="order_id",
        default=None,
        help="订单 ID，如 2392769-HQWIFA72023；不传则交互输入",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="跳过 HTTPS 证书校验（仅本机调试；若遇 CERTIFICATE_VERIFY_FAILED 可临时使用）",
    )
    args = parser.parse_args()

    subdomain = (args.subdomain or SUBDOMAIN or "crispiner").strip()
    order_id = (args.order_id or "").strip()
    if not order_id:
        order_id = input("请输入订单 ID（例如 2392763-IMBZGT54782）: ").strip()
    if not order_id:
        print("错误: 订单 ID 不能为空。")
        sys.exit(1)

    token = ACCESS_TOKEN.strip()
    if not token:
        print("错误: 请设置环境变量 SHOPLAZZA_ACCESS_TOKEN（勿提交仓库）。")
        sys.exit(1)

    url = f"https://{subdomain}.myshoplaza.com/openapi/2025-06/orders/{order_id}"
    headers = {
        "access-token": token,
        "Accept": "application/json",
    }

    print(f"正在请求订单详情: {url}\n")
    if args.insecure:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        response = requests.get(
            url, headers=headers, timeout=30, verify=not args.insecure
        )
        if response.status_code == 404:
            print("错误: 找不到该订单。请确认 ORDER_ID 是否为后台 URL 中的纯数字 ID。")
            return

        response.raise_for_status()
        data = response.json()

        print("======== 订单完整原始数据 (JSON) ========")
        try:
            full_json = json.dumps(data, indent=2, ensure_ascii=False)
            print(full_json)
        except UnicodeEncodeError:
            # Windows 终端可能是 GBK 编码，遇到 emoji 时降级成 ASCII 转义，保证完整输出不中断
            full_json = json.dumps(data, indent=2, ensure_ascii=True)
            print(full_json)
        print("========================================\n")

        keyword = "Ms13"
        if keyword in full_json:
            print(f"发现关键词 '{keyword}'。请在上方数据中搜索它所在的字段名。")
        else:
            print(f"在所有返回数据中未找到关键词 '{keyword}'。")

        order_obj = (data.get("data") or {}).get("order")
        if isinstance(order_obj, dict):
            prev = preview_attribution(order_obj)
            print("\n-------- 归因字段解析（联调用）--------")
            print(json.dumps(prev, indent=2, ensure_ascii=False))
            print(
                "\n说明: 员工英文拼写需从 utm_source 字符串解析（如首段 zhaodengfang-），"
                "再与白名单比对；未命中则计公共池。"
            )

    except Exception as exc:
        print(f"请求发生异常: {exc}")


if __name__ == "__main__":
    main()
