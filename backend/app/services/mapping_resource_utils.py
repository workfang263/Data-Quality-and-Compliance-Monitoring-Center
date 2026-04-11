"""
映射资源工具（后端专用）

职责：
1) 规范化 Facebook 广告账户 ID（统一为 act_纯数字）
2) 校验店铺域名格式（基础语法校验）
3) 调用 Meta / TikTok 拉取账户时区并写入映射表
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from config_new import TT_CONFIG

logger = logging.getLogger(__name__)

FB_GRAPH_API_VERSION = "v19.0"

FB_TIMEZONE_NAME_ALIASES: Dict[str, str] = {
    "Asia/Beijing": "Asia/Shanghai",
    "Asia/Chongqing": "Asia/Shanghai",
    "Asia/Harbin": "Asia/Shanghai",
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
}

TIKTOK_TIMEZONE_CODE_TO_IANA: Dict[str, str] = {
    "Asia/Shanghai": "Asia/Shanghai",
    "Asia/Bangkok": "Asia/Bangkok",
    "America/Los_Angeles": "America/Los_Angeles",
}

_SHOP_DOMAIN_RE = re.compile(r"^(?=.{4,255}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?$")


def normalize_fb_ad_account_id(raw: Optional[str]) -> Optional[str]:
    """将输入标准化为 act_纯数字。"""
    text = (raw or "").strip()
    if not text:
        return None
    if text.lower().startswith("act_"):
        text = text[4:].strip()
    if not text.isdigit():
        return None
    return f"act_{text}"


def validate_shoplazza_shop_domain(domain: str) -> bool:
    """基础域名校验：字符合法，且包含点号。"""
    d = (domain or "").strip().lower()
    if not d or "." not in d:
        return False
    return bool(_SHOP_DOMAIN_RE.match(d))


def _get_proxy_settings() -> Optional[Dict[str, str]]:
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if http_proxy or https_proxy:
        return {
            "http": http_proxy or "",
            "https": (https_proxy or http_proxy) or "",
        }
    return None


def _resolve_iana_and_offset(timezone_name: str) -> Tuple[str, float]:
    """
    时区字符串 -> (规范 IANA, 小时偏移)

    偏移计算采用参考时间 2025-07-01 12:00，确保夏令时地区能得到业务可用的 offset。
    """
    name = (timezone_name or "").strip()
    if not name:
        raise ValueError("empty timezone name")
    name = FB_TIMEZONE_NAME_ALIASES.get(name, name)
    z = ZoneInfo(name)
    ref = datetime(2025, 7, 1, 12, 0, 0, tzinfo=z)
    offset = ref.utcoffset()
    if offset is None:
        raise ValueError(f"timezone has no utcoffset: {name}")
    offset_hours = round(offset.total_seconds() / 3600.0, 1)
    return name, float(offset_hours)


def fetch_and_upsert_fb_ad_timezone(conn: Any, act_id: str, access_token: str) -> Dict[str, Any]:
    """
    从 Meta 获取 timezone_name 并写入 ad_account_timezone_mapping。
    失败时不抛异常，返回 ok=False 供调用方写 warning 审计。
    """
    result: Dict[str, Any] = {"ok": False, "platform": "facebook", "ad_account_id": act_id}
    if not access_token:
        result["message"] = "缺少 FB_LONG_LIVED_TOKEN"
        return result

    try:
        url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{act_id}"
        params = {"fields": "timezone_name", "access_token": access_token}
        resp = requests.get(url, params=params, timeout=30, proxies=_get_proxy_settings())
        resp.raise_for_status()
        data = resp.json()
        timezone_name = (data.get("timezone_name") or "").strip()
        if not timezone_name:
            result["message"] = "Graph 未返回 timezone_name"
            return result

        canonical, offset = _resolve_iana_and_offset(timezone_name)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ad_account_timezone_mapping (ad_account_id, timezone, timezone_offset)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  timezone = VALUES(timezone),
                  timezone_offset = VALUES(timezone_offset),
                  updated_at = CURRENT_TIMESTAMP
                """,
                (act_id, canonical, Decimal(str(offset))),
            )
        result.update(
            {
                "ok": True,
                "timezone": canonical,
                "timezone_offset": offset,
                "message": "upsert 成功",
            }
        )
        return result
    except (requests.RequestException, ZoneInfoNotFoundError, ValueError) as e:
        result["message"] = str(e)
        return result


def _resolve_tiktok_timezone(raw_tz: str) -> Tuple[str, float]:
    """解析 TikTok 时区字符串（IANA / UTC± / 编码映射）。"""
    tz = (raw_tz or "").strip()
    if not tz:
        raise ValueError("empty tiktok timezone")

    m = re.match(r"^UTC\s*([+-])(\d+(?:\.\d+)?)$", tz, re.IGNORECASE)
    if m:
        sign = 1.0 if m.group(1) == "+" else -1.0
        val = round(sign * float(m.group(2)), 1)
        return tz.upper().replace(" ", ""), val

    mapped = TIKTOK_TIMEZONE_CODE_TO_IANA.get(tz)
    if mapped:
        return _resolve_iana_and_offset(mapped)

    return _resolve_iana_and_offset(tz)


def _iter_tt_tokens() -> List[str]:
    tokens: List[str] = []
    seen: set[str] = set()
    for bc in TT_CONFIG.get("business_centers", []):
        token = (bc.get("access_token") or "").strip()
        if not token or token.startswith("YOUR_TIKTOK"):
            continue
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def _fetch_tt_advertiser_info(advertiser_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    base = TT_CONFIG.get("base_url", "https://business-api.tiktok.com/open_api/v1.3").rstrip("/")
    url = f"{base}/advertiser/info/"
    params = {"advertiser_ids": json.dumps([str(advertiser_id)])}
    headers = {"Access-Token": access_token, "Accept": "application/json"}

    try:
        resp = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=TT_CONFIG.get("timeout", 20),
            proxies=TT_CONFIG.get("proxies"),
        )
        data = resp.json()
        if data.get("code") != 0:
            return None
        lst = data.get("data", {}).get("list") or []
        return lst[0] if lst else None
    except Exception as e:
        logger.warning("TikTok advertiser/info 请求异常 advertiser_id=%s: %s", advertiser_id, e)
        return None


def fetch_and_upsert_tt_ad_timezone(conn: Any, advertiser_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    从 TikTok 拉取广告主时区并写入 tt_ad_account_timezone_mapping。
    未传 access_token 时，按 TT_CONFIG 中 business_centers 顺序轮询 token。
    """
    result: Dict[str, Any] = {"ok": False, "platform": "tiktok", "ad_account_id": advertiser_id}
    tokens = [access_token] if (access_token or "").strip() else _iter_tt_tokens()
    tokens = [t for t in tokens if (t or "").strip()]
    if not tokens:
        result["message"] = "无可用 TikTok token"
        return result

    row: Optional[Dict[str, Any]] = None
    for token in tokens:
        row = _fetch_tt_advertiser_info(advertiser_id, token)
        if row:
            break
    if not row:
        result["message"] = "所有 BC token 均无法获取广告主信息"
        return result

    raw_tz = None
    for key in ("display_timezone", "timezone", "advertiser_timezone", "iana_timezone"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            raw_tz = val.strip()
            break
    if not raw_tz:
        result["message"] = "广告主信息缺少 timezone 字段"
        return result

    try:
        canonical, offset = _resolve_tiktok_timezone(raw_tz)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tt_ad_account_timezone_mapping (ad_account_id, timezone, timezone_offset)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  timezone = VALUES(timezone),
                  timezone_offset = VALUES(timezone_offset),
                  updated_at = CURRENT_TIMESTAMP
                """,
                (advertiser_id, canonical, Decimal(str(offset))),
            )
        result.update(
            {
                "ok": True,
                "timezone": canonical,
                "timezone_offset": offset,
                "message": "upsert 成功",
            }
        )
        return result
    except (ZoneInfoNotFoundError, ValueError) as e:
        result["message"] = str(e)
        return result
