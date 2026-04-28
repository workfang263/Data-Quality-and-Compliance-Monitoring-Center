"""
店铺运营：拉取店匠订单列表 + 详情，写入 store_ops_order_attributions。
在 BackgroundTasks 中调用；自行使用 Database 连接。
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

# 项目根目录，用于加载 utils.datetime_to_iso8601（与 data_sync 一致北京日界）
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from utils import datetime_to_iso8601  # noqa: E402

from app.services.database_new import Database
from app.services.shoplazza_store_ops_client import (
    ShoplazzaStoreOpsClient,
    unwrap_order_detail,
)
from app.services.store_ops_attribution import extract_utm, resolve_attribution
from app.services.store_ops_constants import get_store_ops_token_for_shop
from app.services.store_ops_time import order_to_biz_date

logger = logging.getLogger(__name__)

# region agent log
_AGENT_DEBUG_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    ".cursor",
    "debug.log",
)


def _agent_debug_ndjson(payload: Dict[str, Any]) -> None:
    """NDJSON 一行写入 .cursor/debug.log；勿记录 token/PII。"""
    try:
        payload.setdefault("timestamp", int(time.time() * 1000))
        with open(_AGENT_DEBUG_LOG, "a", encoding="utf-8") as _f:
            _f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


# endregion


def beijing_today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def default_sync_biz_dates() -> List[date]:
    """默认同步「北京昨日 + 今日」（与方案推荐一致）。"""
    t = beijing_today()
    return [t - timedelta(days=1), t]


def _resolve_sync_shops(db: Database, shop_domains: Optional[List[str]]) -> List[str]:
    """统一解析同步店铺范围。

    设计要点：
    - 调用方显式传店铺时，以调用方为准，兼容现有接口
    - 未显式传店铺时，统一从 DB 白名单读取，和报表范围保持同源
    """
    if shop_domains:
        return list(shop_domains)
    return db.get_enabled_store_ops_shop_domains()


def beijing_day_placed_at_range(d: date) -> tuple[str, str]:
    start = datetime(d.year, d.month, d.day, 0, 0, 0)
    end = datetime(d.year, d.month, d.day, 23, 59, 59)
    return datetime_to_iso8601(start), datetime_to_iso8601(end)


def _to_decimal_price(raw: Any) -> Decimal:
    if raw is None:
        return Decimal("0")
    return Decimal(str(raw))


def _sync_one_shop(
    shop: str,
    dates: List[date],
    sync_run_id: str,
    verify_ssl: bool,
    employee_slugs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    单店同步（供线程池调用）。每线程自建 Database / Client，避免连接混用。
    """
    t0 = time.monotonic()
    th = threading.current_thread().name
    logger.info(
        "store_ops 店铺开始 shop=%s thread=%s run=%s",
        shop,
        th,
        sync_run_id,
    )
    partial: Dict[str, Any] = {
        "shop_domain": shop,
        "orders_seen": 0,
        "orders_upserted_paid": 0,
        "orders_skipped_not_paid": 0,
        "errors": [],
    }
    employee_filter = {
        str(s).strip().lower() for s in (employee_slugs or []) if str(s).strip()
    }

    token = get_store_ops_token_for_shop(shop)
    if not token:
        msg = f"未配置店铺 token（DB / env），跳过店铺: {shop}"
        logger.error(msg)
        partial["errors"].append(msg)
        logger.info(
            "store_ops 店铺结束 shop=%s thread=%s 跳过(无 token) 耗时=%.2fs run=%s",
            shop,
            th,
            time.monotonic() - t0,
            sync_run_id,
        )
        return partial

    client = ShoplazzaStoreOpsClient(shop, token, verify_ssl=verify_ssl)
    db = Database()

    for d in dates:
        pmin, pmax = beijing_day_placed_at_range(d)
        try:
            list_rows = client.pull_orders_for_placed_at_range(
                pmin, pmax, limit=250
            )
        except Exception as e:
            msg = f"拉取订单列表失败 {shop} {d}: {e}"
            logger.error(msg, exc_info=True)
            partial["errors"].append(msg)
            continue

        for row in list_rows:
            partial["orders_seen"] += 1
            oid = row.get("id")
            if oid is None:
                continue
            oid_str = str(oid)
            try:
                detail_resp = client.fetch_order_detail(oid_str)
            except Exception as e:
                msg = f"订单详情失败 {shop} {oid_str}: {e}"
                logger.warning(msg)
                partial["errors"].append(msg)
                continue

            order_detail = unwrap_order_detail(detail_resp)
            if not order_detail:
                partial["errors"].append(f"详情无 order 对象: {shop} {oid_str}")
                continue

            if (order_detail.get("financial_status") or "").lower() != "paid":
                partial["orders_skipped_not_paid"] += 1
                continue

            biz = order_to_biz_date(order_detail)
            if biz is None:
                partial["errors"].append(f"无法解析 placed_at: {shop} {oid_str}")
                continue

            src = order_detail.get("source")
            last_u = order_detail.get("last_landing_url")
            att_type, slug, decision = resolve_attribution(
                src if isinstance(src, str) else None,
                last_u if isinstance(last_u, str) else None,
            )

            if employee_filter and att_type == "employee":
                norm_slug = (slug or "").strip().lower()
                if norm_slug not in employee_filter:
                    continue

            # region agent log — 归因与店匠 UTM 报表差异验证（仅异常样本）
            u_f = extract_utm(src if isinstance(src, str) else None)
            u_l = extract_utm(last_u if isinstance(last_u, str) else None)
            _hay = f"{u_f or ''}|{u_l or ''}".lower()
            if "xiaoyang" in _hay and (
                att_type == "public_pool" or slug != "xiaoyang"
            ):
                _agent_debug_ndjson(
                    {
                        "hypothesisId": "H_xiaoyang_in_utm_not_attributed",
                        "location": "store_ops_sync._sync_one_shop",
                        "message": "utm 含 xiaoyang 但未归给 xiaoyang 或进公共池",
                        "data": {
                            "shop": shop,
                            "order_id": oid_str,
                            "biz_date": str(biz),
                            "attribution_type": att_type,
                            "employee_slug": slug,
                            "utm_decision": decision,
                            "u_first_prefix": (u_f[:120] if u_f else None),
                            "u_last_prefix": (u_l[:120] if u_l else None),
                        },
                    }
                )
            # endregion

            price = _to_decimal_price(order_detail.get("total_price"))
            rec: Dict[str, Any] = {
                "shop_domain": shop,
                "order_id": oid_str,
                "placed_at_raw": order_detail.get("placed_at"),
                "biz_date": biz,
                "total_price": price,
                "currency": (order_detail.get("currency") or "USD"),
                "financial_status": order_detail.get("financial_status"),
                "attribution_type": att_type,
                "employee_slug": slug,
                "utm_decision": decision,
                "source_url": src if isinstance(src, str) else None,
                "last_landing_url": last_u if isinstance(last_u, str) else None,
                "raw_json": order_detail,
                "sync_run_id": sync_run_id,
            }
            if db.upsert_store_ops_order_attribution(rec):
                partial["orders_upserted_paid"] += 1
            else:
                partial["errors"].append(f"写入失败 {shop} {oid_str}")

    elapsed = time.monotonic() - t0
    logger.info(
        "store_ops 店铺结束 shop=%s thread=%s seen=%s upserted=%s skipped=%s err_shop=%s 耗时=%.2fs run=%s",
        shop,
        th,
        partial["orders_seen"],
        partial["orders_upserted_paid"],
        partial["orders_skipped_not_paid"],
        len(partial["errors"]),
        elapsed,
        sync_run_id,
    )
    return partial


def run_store_ops_sync(
    sync_run_id: str,
    biz_dates: Optional[List[date]] = None,
    shop_domains: Optional[List[str]] = None,
    verify_ssl: bool = True,
    employee_slugs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    执行一轮同步：按店、按北京日拉列表，再逐单详情，仅 financial_status=paid 入库。
    多店时按店铺并行拉单（线程池），单店内仍按日顺序处理。

    Returns:
        统计摘要 dict，便于日志与接口记录。
    """
    db = Database()
    dates = biz_dates if biz_dates else default_sync_biz_dates()
    shops = _resolve_sync_shops(db, shop_domains)

    stats: Dict[str, Any] = {
        "sync_run_id": sync_run_id,
        "shops": shops,
        "biz_dates": [str(d) for d in dates],
        "employee_slugs": [str(s).strip().lower() for s in (employee_slugs or [])],
        "orders_seen": 0,
        "orders_upserted_paid": 0,
        "orders_skipped_not_paid": 0,
        "errors": [],
        "per_shop": [],
    }

    if not shops:
        logger.warning("store_ops 无店铺可同步 run=%s", sync_run_id)
        return stats

    max_workers = min(len(shops), 8)
    logger.info(
        "store_ops 并行调度 run=%s workers=%s shops=%s employee_filter=%s",
        sync_run_id,
        max_workers,
        shops,
        stats["employee_slugs"],
    )
    futures_map = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for shop in shops:
            fut = executor.submit(
                _sync_one_shop,
                shop,
                dates,
                sync_run_id,
                verify_ssl,
                employee_slugs,
            )
            futures_map[fut] = shop

        for fut in as_completed(futures_map):
            shop = futures_map[fut]
            try:
                partial = fut.result()
            except Exception as e:
                msg = f"店铺同步线程异常 {shop}: {e}"
                logger.error(msg, exc_info=True)
                stats["errors"].append(msg)
                stats["per_shop"].append(
                    {
                        "shop_domain": shop,
                        "orders_seen": 0,
                        "orders_upserted_paid": 0,
                        "orders_skipped_not_paid": 0,
                        "error_count": 1,
                        "errors": [msg],
                    }
                )
                continue

            stats["orders_seen"] += partial["orders_seen"]
            stats["orders_upserted_paid"] += partial["orders_upserted_paid"]
            stats["orders_skipped_not_paid"] += partial["orders_skipped_not_paid"]
            stats["errors"].extend(partial["errors"])
            stats["per_shop"].append(
                {
                    "shop_domain": partial["shop_domain"],
                    "orders_seen": partial["orders_seen"],
                    "orders_upserted_paid": partial["orders_upserted_paid"],
                    "orders_skipped_not_paid": partial["orders_skipped_not_paid"],
                    "error_count": len(partial["errors"]),
                    "errors": list(partial["errors"]),
                }
            )

    logger.info(
        "store_ops 同步完成 run=%s seen=%s upserted_paid=%s skipped=%s err_n=%s",
        sync_run_id,
        stats["orders_seen"],
        stats["orders_upserted_paid"],
        stats["orders_skipped_not_paid"],
        len(stats["errors"]),
    )
    return stats
