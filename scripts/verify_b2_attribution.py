"""
B.2 一次性验证脚本：活体检查 store_ops_attribution 的四条链路。

1) 真实 DB 读取 → 打印 operators 明细，确认 quqi.utm_keyword 当前值
2) 30s TTL 缓存命中 → 第二次调用应返回同一对象 id
3) DB 失败降级到旧缓存 → 用 monkey-patch 模拟 DB 故障，应返回旧缓存且打 warning
4) DB 失败且无缓存 → 应返回 EMPLOYEE_SLUGS_ORDERED 兜底列表且打 error

用法（项目根目录）：
    python scripts/verify_b2_attribution.py
"""
from __future__ import annotations

import logging
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.services import store_ops_attribution as attr  # noqa: E402


def _fmt_operators(rows):
    lines = [f"  (共 {len(rows)} 条)"]
    for r in rows:
        lines.append(
            f"  - sort_order={r['sort_order']:<4} "
            f"slug={r['employee_slug']:<12} "
            f"utm_keyword={r['utm_keyword']:<12} "
            f"campaign_keyword={r['campaign_keyword']}"
        )
    return "\n".join(lines)


def check_1_live_db():
    print("\n===== Check 1：活体 DB 读取 =====")
    attr.reset_cache_for_tests()
    rows = attr.get_active_operators()
    print(_fmt_operators(rows))
    quqi = next((r for r in rows if r["employee_slug"] == "quqi"), None)
    if quqi is None:
        print("  [WARN] 未找到 quqi 运营行")
        return None
    print(f"\n  quqi.utm_keyword = {quqi['utm_keyword']!r}")
    if quqi["utm_keyword"] == "cookie":
        print("  [OK] 已切到 'cookie'，归因逻辑符合 B.2 预期")
    elif quqi["utm_keyword"] == "quqi":
        print("  [PENDING] 仍为 'quqi'；B.2 代码已就绪，但需执行 SQL UPDATE")
    else:
        print(f"  [UNEXPECTED] utm_keyword 是非预期值: {quqi['utm_keyword']!r}")
    return quqi["utm_keyword"]


def check_2_cache_hit():
    print("\n===== Check 2：TTL 缓存命中（同一对象） =====")
    attr.reset_cache_for_tests()
    first = attr.get_active_operators()
    second = attr.get_active_operators()
    same = first is second
    print(f"  首次调用返回 id = {id(first)}")
    print(f"  再次调用返回 id = {id(second)}")
    print(f"  [{'OK' if same else 'FAIL'}] {'命中缓存（同一对象）' if same else '未命中缓存'}")
    return same


def check_3_failure_degrade_to_stale_cache():
    print("\n===== Check 3：DB 故障时降级到旧缓存 =====")
    attr.reset_cache_for_tests()
    warm = attr.get_active_operators()
    print(f"  预热缓存完成，{len(warm)} 条")
    original = attr._query_active_operators_from_db

    def _boom() -> list:
        raise RuntimeError("模拟 DB 连接异常")

    attr._query_active_operators_from_db = _boom
    attr._cache_expires_at = 0.0
    try:
        degraded = attr.get_active_operators()
    finally:
        attr._query_active_operators_from_db = original

    ok = degraded is warm
    print(f"  故障时返回列表长度 = {len(degraded)}")
    print(f"  返回对象 id = {id(degraded)}（与预热缓存 id={id(warm)} {'一致' if ok else '不一致'}）")
    print(f"  [{'OK' if ok else 'FAIL'}] 降级到旧缓存的行为符合预期")
    return ok


def check_4_failure_no_cache_fallback_to_constants():
    print("\n===== Check 4：DB 故障且无缓存时兜底常量 =====")
    attr.reset_cache_for_tests()
    original = attr._query_active_operators_from_db

    def _boom() -> list:
        raise RuntimeError("模拟 DB 首次连接就失败")

    attr._query_active_operators_from_db = _boom
    try:
        fallback = attr.get_active_operators()
    finally:
        attr._query_active_operators_from_db = original

    print(_fmt_operators(fallback))
    from app.services.store_ops_constants import EMPLOYEE_SLUGS_ORDERED

    slugs_equal = [r["employee_slug"] for r in fallback] == list(EMPLOYEE_SLUGS_ORDERED)
    ids_are_negative = all(r["id"] < 0 for r in fallback)
    ok = slugs_equal and ids_are_negative
    print(
        f"  [{'OK' if ok else 'FAIL'}] "
        f"slugs={'一致' if slugs_equal else '不一致'}, "
        f"id 均为负（区分兜底行）: {ids_are_negative}"
    )
    return ok


def check_5_match_employee_slug_end_to_end(quqi_utm_keyword):
    print("\n===== Check 5：match_employee_slug 端到端调用 =====")
    attr.reset_cache_for_tests()
    cases = [
        ("jieni-promo", "jieni"),
        ("xx_kiki_yy_jieni_zz", "kiki"),
        ("facebook_organic", None),
        ("Promo_JieNi_X", "jieni"),
    ]
    if quqi_utm_keyword == "cookie":
        cases += [
            ("Promo-Cookie-2026", "quqi"),
            ("promo_quqi_only", None),
        ]
    elif quqi_utm_keyword == "quqi":
        cases += [
            ("Promo-Cookie-2026", None),
            ("promo_quqi_only", "quqi"),
        ]
    all_ok = True
    for utm, expect in cases:
        got = attr.match_employee_slug(utm)
        ok = got == expect
        if not ok:
            all_ok = False
        print(f"  [{'OK' if ok else 'FAIL'}] match_employee_slug({utm!r}) => {got!r} (期望 {expect!r})")
    return all_ok


def main():
    print("=" * 72)
    print("B.2 活体验证：store_ops_attribution 读路径")
    print("=" * 72)

    results = {}
    results["live_db"] = check_1_live_db() is not None
    quqi_kw = attr.get_active_operators()[-1]["utm_keyword"]  # 末位 sort_order 是 quqi
    results["cache_hit"] = check_2_cache_hit()
    results["degrade_stale"] = check_3_failure_degrade_to_stale_cache()
    results["fallback_constants"] = check_4_failure_no_cache_fallback_to_constants()
    results["match_e2e"] = check_5_match_employee_slug_end_to_end(quqi_kw)

    print("\n" + "=" * 72)
    print("验收结果汇总")
    print("=" * 72)
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    print()
    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"[FAIL] 以下检查未通过：{failed}")
        sys.exit(1)
    print("[PASS] 全部检查通过。")


if __name__ == "__main__":
    main()
