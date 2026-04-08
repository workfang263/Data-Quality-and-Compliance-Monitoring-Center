"""
映射 / 资源相关的公共工具（阶段 1）

用途简述（像「收发室」）：
- normalize：所有人交来的 FB 账户号，先统一成同一格式再入库，避免同户多条记录。
- validate：店匠域名先做基本校验，减少脏数据挤进 shoplazza_stores。
- redact_for_audit：审计日志像「公示栏」，绝对不能贴上 access_token 等机密。
- fetch_and_upsert_*：从 Meta / TikTok 拉账户时区，写入映射表，供 timezone_utils + 同步脚本使用。
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

logger = logging.getLogger(__name__)

# 与 fb_spend_sync / 测试脚本保持一致，便于同一 token 访问 Graph
FB_GRAPH_API_VERSION = "v19.0"

# Meta 有时返回非标准 IANA 字符串，这里做少量别名（可随线上报错迭代补充）
FB_TIMEZONE_NAME_ALIASES: Dict[str, str] = {
    "Asia/Beijing": "Asia/Shanghai",
    "Asia/Chongqing": "Asia/Shanghai",
    "Asia/Harbin": "Asia/Shanghai",
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
}

# TikTok 附录或旧版接口可能返回非 IANA 编码：先查表，无法解析再降级（见计划「编码→offset」）
# TikTok 附录编码 → IANA：仅收录不易歧义的项；其余走 resolve_tt_timezone_to_storage 的 ZoneInfo 或 UTC± 解析
TIKTOK_TIMEZONE_CODE_TO_IANA: Dict[str, str] = {
    "Asia/Shanghai": "Asia/Shanghai",
    "Asia/Bangkok": "Asia/Bangkok",
    "America/Los_Angeles": "America/Los_Angeles",
}

# 店匠店铺域名：字母数字与点号等，且必须含「点」（如 xxx.myshoplaza.com）
_SHOPLAZZA_DOMAIN_RE = re.compile(
    r"^(?=.{4,255}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?$"
)


def normalize_fb_ad_account_id(raw: Optional[str]) -> Optional[str]:
    """
    将用户或 API 输入的 Facebook 广告账户 ID 规范为数据库现行标准：act_ + 纯数字。

    步骤：
    1. 去空白；空串视为无效。
    2. 若前缀为 act_（大小写不敏感），剥掉前缀得到数字部分。
    3. 剩余部分必须全为数字，否则无效（避免把 demo_、错帖的 TT ID 写进 FB 表）。
    4. 返回 act_{数字}，与迁移脚本及 fb_spend_sync 写入格式一致。
    """
    text = (raw or "").strip()
    if not text:
        return None
    if text.lower().startswith("act_"):
        text = text[4:].strip()
    if not text.isdigit():
        return None
    return f"act_{text}"


def validate_shoplazza_shop_domain(domain: str) -> bool:
    """
    店匠店铺域名校验（宽松但够用）：
    - 整体长度 4～255；
    - 至少包含一个点号（通常为主机名.一级域）；
    - 字符集为常见 DNS 子集，避免空格与控制字符。
    """
    d = (domain or "").strip().lower()
    if not d or "." not in d:
        return False
    return bool(_SHOPLAZZA_DOMAIN_RE.match(d))


# 审计时禁止原文出现的字段名（小写匹配）；值会改成 "***REDACTED***"
_AUDIT_SECRET_KEYS = frozenset(
    {
        "access_token",
        "password",
        "password_hash",
        "refresh_token",
        "client_secret",
        "authorization",
        "secret",
        "fb_long_lived_token",
        "store_ops_sync_secret",
    }
)


def redact_for_audit(payload: Any) -> Any:
    """
    递归复制并脱敏：任何 dict/list 中含敏感键则替换值，防止 token 写入审计表或日志。

    设计意图：审计要可追溯「谁改了什么」，但不要复制密钥本身（合规与泄漏风险）。
    """
    if isinstance(payload, dict):
        out: Dict[str, Any] = {}
        for k, v in payload.items():
            key_lower = str(k).lower()
            if key_lower in _AUDIT_SECRET_KEYS or key_lower.endswith("_token") or "secret" in key_lower:
                out[k] = "***REDACTED***"
            else:
                out[k] = redact_for_audit(v)
        return out
    if isinstance(payload, list):
        return [redact_for_audit(item) for item in payload]
    return payload


def _requests_proxies() -> Optional[Dict[str, str]]:
    http_p = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_p = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if http_p or https_p:
        return {"http": http_p or "", "https": (https_p or http_p) or ""}
    return None


def resolve_iana_and_offset_hours(timezone_name: str) -> Tuple[str, float]:
    """
    将 IANA 时区名转为「夏令时参考日」下的 UTC 偏移小时数，写入 timezone_offset 字段。

    说明：同一 IANA 在冬夏令时偏移可能不同；项目现有逻辑用单个小数表示「业务用」偏移，
    这里取每年 7 月 1 日 12:00 本地时刻的 utcoffset，与常见运营报表习惯接近。
    """
    name = (timezone_name or "").strip()
    if not name:
        raise ValueError("empty timezone name")
    name = FB_TIMEZONE_NAME_ALIASES.get(name, name)
    ref_local = datetime(2025, 7, 1, 12, 0, 0)
    z = ZoneInfo(name)
    aware = ref_local.replace(tzinfo=z)
    off = aware.utcoffset()
    if off is None:
        raise ValueError(f"no utcoffset for {name}")
    hours = round(off.total_seconds() / 3600.0, 1)
    return name, float(hours)


def fetch_fb_timezone_name_from_graph(act_id: str, access_token: str, timeout: int = 30) -> Optional[str]:
    """
    调用 Graph：GET /v19.0/{act_id}?fields=timezone_name
    act_id 须已 normalize（含 act_ 前缀）。
    """
    if not access_token or not act_id:
        return None
    url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{act_id}"
    params = {"fields": "timezone_name", "access_token": access_token}
    try:
        resp = requests.get(url, params=params, timeout=timeout, proxies=_requests_proxies())
        resp.raise_for_status()
        data = resp.json()
        tz = data.get("timezone_name")
        if isinstance(tz, str) and tz.strip():
            return tz.strip()
    except Exception as e:
        logger.warning("Graph timezone_name 请求失败 act_id=%s: %s", act_id, e)
    return None


def fetch_and_upsert_fb_ad_timezone(
    conn: Any,
    act_id: str,
    access_token: str,
) -> Dict[str, Any]:
    """
    拉取 Meta 账户 timezone_name → 解析偏移 → upsert ad_account_timezone_mapping。

    失败不抛异常：返回 dict 含 ok=False 与 message，便于调用方写审计 warning（映射创建仍应成功）。
    """
    result: Dict[str, Any] = {"ok": False, "platform": "facebook", "ad_account_id": act_id}
    tz_name = fetch_fb_timezone_name_from_graph(act_id, access_token)
    if not tz_name:
        result["message"] = "Graph 未返回 timezone_name 或请求失败"
        return result
    try:
        canonical, offset = resolve_iana_and_offset_hours(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as e:
        result["message"] = f"无法解析 IANA 时区: {tz_name!r} ({e})"
        return result

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
    result["ok"] = True
    result["timezone"] = canonical
    result["timezone_offset"] = offset
    result["message"] = "upsert 成功"
    return result


def resolve_tt_timezone_to_storage(raw: Optional[str]) -> Tuple[str, float]:
    """
    TikTok 返回的时区可能是 IANA、附录编码或 UTC± 文本；统一得到 (存入 timezone 列的字符串, offset)。
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty tiktok timezone")

    # 形如 UTC+8 / UTC-5.5
    m = re.match(r"^UTC\s*([+-])(\d+(?:\.\d+)?)$", s, re.IGNORECASE)
    if m:
        sign = 1.0 if m.group(1) == "+" else -1.0
        hrs = sign * float(m.group(2))
        return (s.upper().replace(" ", ""), round(hrs, 1))

    mapped = TIKTOK_TIMEZONE_CODE_TO_IANA.get(s)
    if mapped:
        return resolve_iana_and_offset_hours(mapped)

    try:
        return resolve_iana_and_offset_hours(s)
    except (ZoneInfoNotFoundError, ValueError):
        pass

    raise ValueError(f"unknown tiktok timezone code: {s!r}")


def iter_tt_bc_access_tokens_ordered() -> List[str]:
    """
    按照 config.TT_CONFIG['business_centers'] 列表顺序返回各 BC 的 access_token（去重、跳过空占位）。
    """
    from config import TT_CONFIG

    tokens: List[str] = []
    seen: set[str] = set()
    for bc in TT_CONFIG.get("business_centers", []):
        t = (bc.get("access_token") or "").strip()
        if not t or t.startswith("YOUR_TIKTOK"):
            continue
        if t not in seen:
            seen.add(t)
            tokens.append(t)
    return tokens


def _tiktok_advertiser_info(advertiser_id: str, access_token: str, timeout: int = 20) -> Optional[Dict[str, Any]]:
    """
    GET /open_api/v1.3/advertiser/info/，从返回 list[0] 取 timezone 相关字段。
    TikTok 字段名随版本可能为 display_timezone / timezone 等，这里做多键兼容。
    """
    from config import TT_CONFIG

    base = TT_CONFIG.get("base_url", "https://business-api.tiktok.com/open_api/v1.3").rstrip("/")
    url = f"{base}/advertiser/info/"
    params = {"advertiser_ids": json.dumps([str(advertiser_id)])}
    headers = {
        "Access-Token": access_token,
        "Accept": "application/json",
    }
    try:
        resp = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            proxies=TT_CONFIG.get("proxies"),
        )
        data = resp.json()
        if data.get("code") == 0:
            lst = data.get("data", {}).get("list") or []
            if lst:
                return cast(Dict[str, Any], lst[0])
        else:
            logger.debug(
                "TikTok advertiser/info 非0 code advertiser=%s message=%s",
                advertiser_id,
                data.get("message"),
            )
    except Exception as e:
        logger.warning("TikTok advertiser/info 请求异常 advertiser=%s: %s", advertiser_id, e)
    return None


def pick_tt_timezone_raw_from_advertiser_row(row: Dict[str, Any]) -> Optional[str]:
    """从广告主信息对象里尽量取出时区字符串（兼容多字段名）。"""
    for key in ("display_timezone", "timezone", "advertiser_timezone", "iana_timezone"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def fetch_and_upsert_tt_ad_timezone(
    conn: Any,
    advertiser_id: str,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    使用 TikTok BC token 拉广告主时区并写入 tt_ad_account_timezone_mapping。

    - 若未传 access_token：按 business_centers 顺序轮询，直到 advertiser/info 成功返回。
    """
    result: Dict[str, Any] = {"ok": False, "platform": "tiktok", "ad_account_id": advertiser_id}
    tokens = [access_token] if (access_token or "").strip() else iter_tt_bc_access_tokens_ordered()
    tokens = [t for t in tokens if (t or "").strip()]
    if not tokens:
        result["message"] = "无可用 TikTok access_token（请检查 .env 与 TT_CONFIG）"
        return result

    row: Optional[Dict[str, Any]] = None
    for tok in tokens:
        row = _tiktok_advertiser_info(advertiser_id, tok)
        if row:
            break
    if not row:
        result["message"] = "所有 BC token 均无法取得广告主信息（权限或 ID 错误）"
        return result

    raw_tz = pick_tt_timezone_raw_from_advertiser_row(row)
    if not raw_tz:
        result["message"] = "广告主信息中无时区字段"
        return result

    try:
        store_tz, offset = resolve_tt_timezone_to_storage(raw_tz)
    except ValueError as e:
        result["message"] = str(e)
        return result

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
            (advertiser_id, store_tz, Decimal(str(offset))),
        )
    result["ok"] = True
    result["timezone"] = store_tz
    result["timezone_offset"] = offset
    result["message"] = "upsert 成功"
    return result
