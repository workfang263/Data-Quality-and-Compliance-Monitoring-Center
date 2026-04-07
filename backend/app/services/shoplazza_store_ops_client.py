"""
店匠 OpenAPI 2025-06 客户端（仅店铺运营模块使用，与 shoplazza_api / data_sync 隔离）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from app.services.store_ops_constants import OPENAPI_VERSION_STORE_OPS

logger = logging.getLogger(__name__)

_urllib3_insecure_warning_disabled = False


def _disable_insecure_request_warning_once() -> None:
    """verify=False 时避免每次请求刷屏 InsecureRequestWarning。"""
    global _urllib3_insecure_warning_disabled
    if _urllib3_insecure_warning_disabled:
        return
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    _urllib3_insecure_warning_disabled = True


def _unwrap_orders(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not payload:
        return []
    if isinstance(payload.get("data"), dict):
        orders = payload["data"].get("orders")
        if orders:
            return list(orders)
    raw = payload.get("orders")
    return list(raw) if raw else []


def _unwrap_cursor(payload: Optional[Dict[str, Any]]) -> Optional[str]:
    if not payload:
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        c = data.get("cursor")
        if c:
            return str(c)
    return None


def unwrap_order_detail(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not payload:
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        order = data.get("order")
        if isinstance(order, dict):
            return order
    order = payload.get("order")
    return order if isinstance(order, dict) else None


class ShoplazzaStoreOpsClient:
    def __init__(
        self,
        shop_domain: str,
        access_token: str,
        api_version: str = OPENAPI_VERSION_STORE_OPS,
        verify_ssl: bool = True,
        timeout: int = 90,
    ):
        self.shop_domain = shop_domain.rstrip("/")
        self.access_token = access_token
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        if not verify_ssl:
            _disable_insecure_request_warning_once()
        host = self.shop_domain
        if not host.startswith("http"):
            host = f"https://{host}"
        self.base_url = f"{host}/openapi/{api_version}"

    def _headers(self) -> Dict[str, str]:
        return {
            "access-token": self.access_token,
            "Accept": "application/json",
        }

    def fetch_orders_page(
        self,
        placed_at_min: str,
        placed_at_max: str,
        page: int,
        limit: int,
        cursor: Optional[str],
    ) -> Dict[str, Any]:
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
            f"{self.base_url}/orders",
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        r.raise_for_status()
        return r.json()

    def fetch_order_detail(self, order_id: str) -> Dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/orders/{order_id}",
            headers=self._headers(),
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        r.raise_for_status()
        return r.json()

    def pull_orders_for_placed_at_range(
        self,
        placed_at_min: str,
        placed_at_max: str,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        """
        拉取 placed_at 落在 [placed_at_min, placed_at_max] 内的全部订单列表行。
        """
        all_rows: List[Dict[str, Any]] = []
        page = 1
        cursor: Optional[str] = None
        max_rounds = 500
        use_cursor: Optional[bool] = None

        for _ in range(max_rounds):
            payload = self.fetch_orders_page(
                placed_at_min,
                placed_at_max,
                page=page,
                limit=limit,
                cursor=cursor,
            )
            code = payload.get("code")
            if code and code != "Success":
                raise RuntimeError(f"店匠 API code={code}, body={payload}")

            batch = _unwrap_orders(payload)
            all_rows.extend(batch)

            data_block = (
                payload.get("data") if isinstance(payload.get("data"), dict) else {}
            )
            next_c = data_block.get("cursor") or _unwrap_cursor(payload)
            has_more = bool(data_block.get("has_more"))

            if not batch:
                break

            if use_cursor is None:
                use_cursor = bool(has_more and next_c)

            if use_cursor:
                if has_more and next_c:
                    cursor = str(next_c)
                    continue
                break

            if len(batch) < limit:
                break
            page += 1

        return all_rows
