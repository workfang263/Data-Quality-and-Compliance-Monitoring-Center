"""
utm_source 解析与员工 / 公共池归因（与方案 §3 一致）。
"""
from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from app.services.store_ops_constants import EMPLOYEE_SLUG_SET


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
    utm_source 第一个 '-' 之前的段，转小写后与白名单匹配。
    未命中返回 None。
    """
    if not utm_raw:
        return None
    seg = utm_raw.split("-")[0].strip().lower()
    if not seg:
        return None
    if seg in EMPLOYEE_SLUG_SET:
        return seg
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
