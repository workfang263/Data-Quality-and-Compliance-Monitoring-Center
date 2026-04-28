"""
utm_source 解析与员工 / 公共池归因（与方案 §3 一致）。

员工匹配：在完整 utm_source 中按子串命中 `store_ops_employee_config.utm_keyword`；
命中不到则归为公共池。原 `EMPLOYEE_SLUGS_ORDERED` 硬编码依赖与 `cookie -> quqi` 
硬编码兜底均已下沉到数据库行数据（由 quqi.utm_keyword='cookie' 承担）。

读路径：进程级 30 秒 TTL 缓存 + 失败降级到最近一次成功缓存 + 无缓存时回退到
`EMPLOYEE_SLUGS_ORDERED` 兜底常量（最后一道保命）。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from app.services.database_new import Database
from app.services.store_ops_constants import EMPLOYEE_SLUGS_ORDERED

logger = logging.getLogger(__name__)


# ===================== 运营配置：TTL 缓存 + 失败降级 =====================

_CACHE_TTL_SECONDS: float = 30.0
_cache_lock = threading.Lock()
_cache: Optional[List[Dict[str, Any]]] = None
_cache_expires_at: float = 0.0


def _query_active_operators_from_db() -> List[Dict[str, Any]]:
    """从 store_ops_employee_config 读取"激活未删除"的运营配置，按 sort_order, id 排序。"""
    db = Database()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, employee_slug, utm_keyword, campaign_keyword, sort_order
                FROM store_ops_employee_config
                WHERE status = 'active' AND deleted_at IS NULL
                ORDER BY sort_order ASC, id ASC
                """
            )
            rows = cur.fetchall() or []
    normalized: List[Dict[str, Any]] = []
    for r in rows:
        utm_kw = (r.get("utm_keyword") or "")
        camp_kw = (r.get("campaign_keyword") or "")
        normalized.append({
            "id": r.get("id"),
            "employee_slug": (r.get("employee_slug") or "").strip(),
            "utm_keyword": str(utm_kw).strip().lower(),
            "campaign_keyword": str(camp_kw).strip().lower(),
            "sort_order": r.get("sort_order") or 0,
        })
    return normalized


def _fallback_operators_from_constants() -> List[Dict[str, Any]]:
    """DB 首次连接就失败且无历史缓存时的最后一道保命。

    退化行为：quqi 的 utm_keyword 退化为 'quqi' 而非 'cookie'（接受该降级，
    因为正常链路极少触发到这一层）。
    """
    out: List[Dict[str, Any]] = []
    for idx, slug in enumerate(EMPLOYEE_SLUGS_ORDERED):
        out.append({
            "id": -(idx + 1),
            "employee_slug": slug,
            "utm_keyword": slug,
            "campaign_keyword": "",
            "sort_order": (idx + 1) * 10,
        })
    return out


def get_active_operators() -> List[Dict[str, Any]]:
    """获取激活运营配置列表（有序）。
    
    级联策略：
      1. 缓存未过期 → 直接返回缓存
      2. 过期或未初始化 → 查 DB；成功则刷新缓存
      3. DB 查询失败且有历史缓存 → 返回旧缓存（warning）
      4. DB 查询失败且无历史缓存 → 返回常量兜底（error）
    """
    global _cache, _cache_expires_at
    now = time.monotonic()
    with _cache_lock:
        if _cache is not None and _cache_expires_at > now:
            return _cache
        try:
            rows = _query_active_operators_from_db()
            _cache = rows
            _cache_expires_at = now + _CACHE_TTL_SECONDS
            return rows
        except Exception as e:
            if _cache is not None:
                logger.warning(
                    f"[store_ops_attribution] DB 读取 store_ops_employee_config 失败，"
                    f"降级使用最近一次成功缓存（{len(_cache)} 条）: {e}"
                )
                return _cache
            logger.error(
                f"[store_ops_attribution] DB 读取 store_ops_employee_config 失败且无历史缓存，"
                f"降级使用 EMPLOYEE_SLUGS_ORDERED 常量兜底: {e}"
            )
            return _fallback_operators_from_constants()


def reset_cache_for_tests() -> None:
    """仅测试用：强制下次重新读取（或走注入路径）。"""
    global _cache, _cache_expires_at
    with _cache_lock:
        _cache = None
        _cache_expires_at = 0.0


# ===================== URL 解析（逻辑保持原样） =====================

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


# ===================== 归因匹配：UTM / Campaign =====================

def match_employee_slug(
    utm_raw: Optional[str],
    operators: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    在完整 utm_source 值中查找员工：转小写后，按 `store_ops_employee_config` 的
    `sort_order ASC, id ASC` 顺序，返回首个 `utm_keyword` 作为子串命中的运营 slug。

    `operators=None` 时内部调用 `get_active_operators()`（带缓存）；
    批量调用方可传入一次取到的列表避免重复获取锁。

    多人同时出现在同一串中时，按 `sort_order` 从小到大取第一个命中者。
    短 keyword（如 `kiki`）可能在无关英文词中误命中，属业务可接受范围。

    未命中返回 None。
    """
    if not utm_raw or not str(utm_raw).strip():
        return None
    haystack = utm_raw.strip().lower()
    ops = operators if operators is not None else get_active_operators()
    for op in ops:
        kw = op.get("utm_keyword") or ""
        if kw and kw in haystack:
            return op.get("employee_slug")
    return None


def match_employee_by_campaign(
    campaign_name: Optional[str],
    operators: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    按广告系列名称关键词匹配运营（B.3 系列归因将使用）。

    规则：
      - 空值 / None → 返回 None
      - 按 `sort_order ASC, id ASC` 遍历激活运营
      - 跳过空 `campaign_keyword` 和以 `__unset_` 开头的占位符
      - 首个 `campaign_keyword` 为 `campaign_name.lower()` 子串者胜出
      - 未命中返回 None（由调用方决定归"未归属桶"）
    """
    if not campaign_name or not str(campaign_name).strip():
        return None
    haystack = campaign_name.strip().lower()
    ops = operators if operators is not None else get_active_operators()
    for op in ops:
        kw = op.get("campaign_keyword") or ""
        if not kw or kw.startswith("__unset_"):
            continue
        if kw in haystack:
            return op.get("employee_slug")
    return None


def resolve_attribution(
    source: Optional[str],
    last_landing_url: Optional[str],
    operators: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Optional[str], str]:
    """
    返回 (attribution_type, employee_slug|None, utm_decision)。
    attribution_type: 'employee' | 'public_pool'
    utm_decision:     'last' | 'first' | 'first_fallback' | 'public'

    `operators` 新增可选参数：批量调用可一次取到列表后传入，避免每单都获取缓存锁。
    """
    ops = operators if operators is not None else get_active_operators()
    u_first = extract_utm(source if isinstance(source, str) else None)
    u_last = extract_utm(last_landing_url if isinstance(last_landing_url, str) else None)
    has_last_param = landing_has_utm_source_param(last_landing_url)

    if has_last_param:
        m_last = match_employee_slug(u_last, ops)
        if m_last:
            return "employee", m_last, "last"
        m_first = match_employee_slug(u_first, ops)
        if m_first:
            return "employee", m_first, "first_fallback"
        return "public_pool", None, "public"

    m_first = match_employee_slug(u_first, ops)
    if m_first:
        return "employee", m_first, "first"
    return "public_pool", None, "public"
