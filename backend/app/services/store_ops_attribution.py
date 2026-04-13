"""
utm_source 解析与员工 / 公共池归因（与方案 §3 一致）。
员工匹配：在完整 utm_source 中按子串命中全拼，见 match_employee_slug。
"""
from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from app.services.store_ops_constants import EMPLOYEE_SLUGS_ORDERED


def extract_utm(url: Optional[str]) -> Optional[str]:
    """从 URL 的 query 中取 utm_source 原始字符串（不解码 slug 结构，仅 unquote）。"""
    if not url or not isinstance(url, str):
        return None
    try:
        q = parse_qs(urlparse(url.strip()).query)
        vals = q.get("utm_source")
        if vals and str(vals[0]).strip():
            return unquote(vals[0].strip())
    except Exception:
        pass
    return None


def landing_has_utm_source_param(url: Optional[str]) -> bool:
    """末次落地页 URL 是否**带有** utm_source 参数（有空值也算「带参数」，走末次逻辑链）。"""
    if not url or not isinstance(url, str):
        return False
    try:
        q = parse_qs(urlparse(url.strip()).query)
        return "utm_source" in q
    except Exception:
        return False


def match_employee_slug(utm_raw: Optional[str]) -> Optional[str]:
    """
    在完整 utm_source 值中查找员工全拼：转小写后，若子串包含某位员工 slug 即命中。

    多人同时出现在同一串中时，按 EMPLOYEE_SLUGS_ORDERED 从左到右取「第一个在串中
    存在的 slug」（名单优先级，非按字符出现先后）。短 slug（如 kiki）可能在无关
    英文词中误命中，属业务可接受范围。

    未命中返回 None。
    """
    if not utm_raw or not str(utm_raw).strip():
        return None
    haystack = utm_raw.strip().lower()
    for slug in EMPLOYEE_SLUGS_ORDERED:
        if slug in haystack:
            return slug
    return None


def resolve_attribution(
    source: Optional[str],
    last_landing_url: Optional[str],
) -> Tuple[str, Optional[str], str]:
    """
    返回 (attribution_type, employee_slug|None, utm_decision)。
    attribution_type: 'employee' | 'public_pool'
    utm_decision: 'last' | 'first' | 'first_fallback' | 'public'
    """
    u_first = extract_utm(source if isinstance(source, str) else None)
    u_last = extract_utm(last_landing_url if isinstance(last_landing_url, str) else None)
    has_last_param = landing_has_utm_source_param(last_landing_url)

    if has_last_param:
        m_last = match_employee_slug(u_last)
        if m_last:
            return "employee", m_last, "last"
        m_first = match_employee_slug(u_first)
        if m_first:
            return "employee", m_first, "first_fallback"
        return "public_pool", None, "public"

    m_first = match_employee_slug(u_first)
    if m_first:
        return "employee", m_first, "first"
    return "public_pool", None, "public"
