"""
端到端演练 M1：探查 2026-04-21 系列花费与运营归属关系（只读）。

输出：
  1. 当前 active operators（slug / utm_keyword / campaign_keyword / sort_order）
  2. 2026-04-21 所有系列：ad_account_id + campaign_name + spend + 主系统 owner + 建议 slug
  3. 按建议 slug 分组汇总花费
  4. 按 campaign_name 子串推断"最低覆盖关键词"
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
for p in (_ROOT, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.database_new import Database  # type: ignore
from app.services.store_ops_fb_mapping import (  # type: ignore
    STORE_OPS_OWNER_CN_TO_SLUG,
)


TARGET_DATE = "2026-04-21"


def main() -> int:
    db = Database()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            print("=" * 80)
            print(f"  M1 探查：{TARGET_DATE} 系列花费归属关系")
            print("=" * 80)

            print("\n[1] 当前 active operators")
            cur.execute(
                """
                SELECT id, employee_slug, display_name, utm_keyword,
                       campaign_keyword, status, sort_order
                FROM store_ops_employee_config
                WHERE deleted_at IS NULL AND status='active'
                ORDER BY sort_order ASC, id ASC
                """
            )
            ops = cur.fetchall() or []
            for op in ops:
                print(
                    f"  slug={op['employee_slug']:<10} "
                    f"cn={op['display_name']:<6} "
                    f"utm={op['utm_keyword']!r:<12} "
                    f"campaign={op['campaign_keyword']!r:<24} "
                    f"sort={op['sort_order']}"
                )

            print("\n[2] 主系统 owner 中文名 → slug 映射（来自 store_ops_fb_mapping）")
            for cn, slug in STORE_OPS_OWNER_CN_TO_SLUG.items():
                print(f"  {cn:<8} → {slug}")

            print(f"\n[3] {TARGET_DATE} 全部系列 + 账户 owner + 建议归属")
            cur.execute(
                """
                SELECT c.ad_account_id, c.campaign_id, c.campaign_name, c.spend,
                       m.owner AS owner_cn, w.shop_domain
                FROM fb_campaign_spend_daily c
                LEFT JOIN ad_account_owner_mapping m
                       ON m.ad_account_id = c.ad_account_id COLLATE utf8mb4_0900_ai_ci
                LEFT JOIN store_ops_shop_ad_whitelist w
                       ON w.ad_account_id COLLATE utf8mb4_unicode_ci
                        = c.ad_account_id COLLATE utf8mb4_unicode_ci
                WHERE c.stat_date = %s
                ORDER BY c.ad_account_id, c.spend DESC
                """,
                (TARGET_DATE,),
            )
            rows = cur.fetchall() or []

            enriched: List[Dict[str, Any]] = []
            by_slug: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for r in rows:
                owner_cn = (r.get("owner_cn") or "").strip()
                suggested_slug = STORE_OPS_OWNER_CN_TO_SLUG.get(owner_cn)
                enriched_row = {**r, "suggested_slug": suggested_slug or "_unknown"}
                enriched.append(enriched_row)
                by_slug[enriched_row["suggested_slug"]].append(enriched_row)

            print(f"  {'ad_account_id':<24} {'owner':<8} {'→slug':<12} "
                  f"{'spend':>10}  {'shop':<24} {'campaign_name'}")
            for r in enriched:
                print(
                    f"  {r['ad_account_id']:<24} "
                    f"{(r.get('owner_cn') or ''):<8} "
                    f"{r['suggested_slug']:<12} "
                    f"{float(r['spend']):>10.2f}  "
                    f"{(r.get('shop_domain') or '')[:22]:<24} "
                    f"{r['campaign_name']}"
                )

            print(f"\n[4] 按建议 slug 汇总")
            print(f"  {'slug':<15} {'系列数':>6} {'花费合计':>12}")
            total_all = Decimal("0")
            for slug in sorted(by_slug.keys()):
                lst = by_slug[slug]
                s = sum((Decimal(str(x["spend"])) for x in lst), Decimal("0"))
                total_all += s
                print(f"  {slug:<15} {len(lst):>6} {float(s):>12.2f}")
            print(f"  {'-' * 40}")
            print(f"  {'总计':<15} {len(enriched):>6} {float(total_all):>12.2f}")

            print(f"\n[5] 每个建议 slug 的 campaign_name 样本（前 5 条）+ 关键词推断")
            for slug in sorted(by_slug.keys()):
                if slug in ("_unknown",):
                    continue
                lst = by_slug[slug]
                names = [x["campaign_name"] for x in lst]

                suggestion = _infer_keyword(slug, names)
                print(f"\n  === slug={slug} ({len(lst)} 个系列) ===")
                print(f"  推断 campaign_keyword: {suggestion!r}")
                for n in names[:5]:
                    covered = suggestion and suggestion.lower() in n.lower()
                    mark = "[Y]" if covered else "[N]"
                    print(f"    {mark} {n}")
                if len(names) > 5:
                    print(f"    ... 共 {len(names)} 条")

                if suggestion:
                    covered_cnt = sum(
                        1 for n in names if suggestion.lower() in n.lower()
                    )
                    print(f"  覆盖率: {covered_cnt}/{len(names)} = "
                          f"{100 * covered_cnt / len(names):.1f}%")

            print(f"\n[6] 未能判断归属的系列（owner 为空或无映射）")
            for r in by_slug.get("_unknown", []):
                print(
                    f"  spend={float(r['spend']):.2f}  "
                    f"acc={r['ad_account_id']}  "
                    f"owner={r.get('owner_cn')!r}  "
                    f"name={r['campaign_name']}"
                )

    print("\n" + "=" * 80)
    print("  M1 完成。下一步：基于上面的推断，设计 M2 沙盒归因配置")
    print("=" * 80)
    return 0


def _infer_keyword(slug: str, names: List[str]) -> Optional[str]:
    """
    从一组 campaign_name 中，找出 **所有名字都包含** 的最短有区分度子串。

    启发式：
      1) slug 本身是否都包含 -> 是 → 用 slug
      2) 尝试 campaign_name 第一段（按 '-' / '_' 分）里的共同 token
      3) 回退：从最长共同前缀里截取字母子串
    """
    if not names:
        return None
    lowered = [n.lower() for n in names]

    if all(slug.lower() in n for n in lowered):
        return slug.lower()

    tokens_per_name: List[List[str]] = []
    for n in lowered:
        parts = re.split(r"[-_/. ]+", n)
        tokens_per_name.append([p for p in parts if p])
    if tokens_per_name:
        common = set(tokens_per_name[0])
        for toks in tokens_per_name[1:]:
            common &= set(toks)
        if common:
            cand = sorted(common, key=len)
            for c in cand:
                if len(c) >= 3 and not c.isdigit():
                    return c

    def _lcp(a: str, b: str) -> str:
        i = 0
        while i < len(a) and i < len(b) and a[i] == b[i]:
            i += 1
        return a[:i]

    lcp = lowered[0]
    for n in lowered[1:]:
        lcp = _lcp(lcp, n)
        if not lcp:
            break
    m = re.match(r"^([a-z]{3,})", lcp)
    if m:
        return m.group(1)
    return None


if __name__ == "__main__":
    sys.exit(main())
