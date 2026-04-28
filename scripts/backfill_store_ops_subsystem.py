"""
店铺运营子系统独立化 · 数据回填脚本

目的：
    把老代码里写死在 Python 常量中的「店铺列表 / 账户→店铺绑定 / 运营 slug 与中文名」
    一次性迁移到新建的 3 张配置表里，作为子系统的权威数据源。

数据来源：
    - STORE_OPS_SHOP_DOMAINS              → store_ops_shop_whitelist
    - STORE_OPS_FB_ACT_IDS_BY_SHOP        → store_ops_shop_ad_whitelist（仅绑店铺）
    - EMPLOYEE_SLUGS_ORDERED              → store_ops_employee_config.employee_slug / utm_keyword
    - STORE_OPS_OWNER_CN_TO_SLUG（反向）  → store_ops_employee_config.display_name
    - campaign_keyword                    → 先写占位 `__unset_{slug}`，待 UI 完成后由运营手动补填

设计要点（与方案第 7 节 阶段 A 对应）：
    1) 默认 --dry-run：不加 --apply 绝不写库
    2) 幂等：已存在的数据跳过；脚本可重复执行
    3) 主表校验：插入前 SELECT 主系统相关表，缺失则 [WARN] 跳过并最后汇总
    4) 事务分段：三张表各一个事务，便于部分失败时定位
    5) 日志：[OK] / [SKIP] / [WARN] / [ERR] 四级别，最后给汇总统计

用法：
    python scripts/backfill_store_ops_subsystem.py                          # 默认 dry-run
    python scripts/backfill_store_ops_subsystem.py --apply                  # 真正写入
    python scripts/backfill_store_ops_subsystem.py --apply --only shops
    python scripts/backfill_store_ops_subsystem.py --apply --only ad_whitelist
    python scripts/backfill_store_ops_subsystem.py --apply --only operators

退出码：
    0 全部成功；1 存在错误；2 参数错误
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
for _p in (_ROOT, _BACKEND):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from database import Database  # noqa: E402
from app.services.store_ops_constants import (  # noqa: E402
    EMPLOYEE_SLUGS_ORDERED,
    STORE_OPS_SHOP_DOMAINS,
)
from app.services.store_ops_fb_mapping import (  # noqa: E402
    STORE_OPS_FB_ACT_IDS_BY_SHOP,
    STORE_OPS_OWNER_CN_TO_SLUG,
)

SECTION_SHOPS = "shops"
SECTION_AD_WHITELIST = "ad_whitelist"
SECTION_OPERATORS = "operators"
ALL_SECTIONS = (SECTION_SHOPS, SECTION_AD_WHITELIST, SECTION_OPERATORS)


class BackfillSummary:
    """单段（一张表）的统计小账本。"""

    def __init__(self, section: str) -> None:
        self.section = section
        self.inserted = 0
        self.skipped = 0
        self.warned = 0
        self.errored = 0

    def line(self) -> str:
        return (
            f"[{self.section:<14}] inserted={self.inserted} "
            f"skipped(existed)={self.skipped} "
            f"warned(missing_in_main)={self.warned} "
            f"errored={self.errored}"
        )


def _slug_display_name_map() -> Dict[str, str]:
    """反转 STORE_OPS_OWNER_CN_TO_SLUG 为 slug -> 中文名；保证每个 slug 都有显示名。"""
    slug_to_cn: Dict[str, str] = {}
    for cn, slug in STORE_OPS_OWNER_CN_TO_SLUG.items():
        slug_to_cn.setdefault(slug.strip().lower(), cn.strip())
    return slug_to_cn


def backfill_shops(conn, dry_run: bool) -> BackfillSummary:
    """
    阶段 1：店铺白名单
    - 先校验 shoplazza_stores 是否存在该域名
    - 已在 store_ops_shop_whitelist 的跳过
    """
    s = BackfillSummary(SECTION_SHOPS)
    print("\n======= 阶段 1: store_ops_shop_whitelist =======")
    with conn.cursor() as cur:
        for raw in STORE_OPS_SHOP_DOMAINS:
            domain = raw.strip()
            if not domain:
                continue

            cur.execute(
                "SELECT 1 FROM shoplazza_stores WHERE shop_domain=%s LIMIT 1",
                (domain,),
            )
            if not cur.fetchone():
                print(f"[WARN] {domain:<40} 主表 shoplazza_stores 未登记，跳过")
                s.warned += 1
                continue

            cur.execute(
                "SELECT id FROM store_ops_shop_whitelist WHERE shop_domain=%s LIMIT 1",
                (domain,),
            )
            if cur.fetchone():
                print(f"[SKIP] {domain:<40} 子系统已存在")
                s.skipped += 1
                continue

            if dry_run:
                print(f"[OK  ] {domain:<40} (dry-run 待插入)")
            else:
                cur.execute(
                    "INSERT INTO store_ops_shop_whitelist (shop_domain, is_enabled) VALUES (%s, 1)",
                    (domain,),
                )
                print(f"[OK  ] {domain:<40} 已写入")
            s.inserted += 1

    print(s.line())
    return s


def backfill_ad_whitelist(conn, dry_run: bool) -> BackfillSummary:
    """
    阶段 2：广告账户白名单（仅绑店铺，不绑运营）
    - 先校验 ad_account_owner_mapping 存在该 ad_account_id
    - 已在 store_ops_shop_ad_whitelist 的跳过（UNIQUE 会兜底，这里主要为打印清晰）
    """
    s = BackfillSummary(SECTION_AD_WHITELIST)
    print("\n======= 阶段 2: store_ops_shop_ad_whitelist =======")

    flat: List[Tuple[str, str]] = []
    for shop, acct_ids in STORE_OPS_FB_ACT_IDS_BY_SHOP.items():
        for acct_id in acct_ids:
            flat.append((shop.strip(), acct_id.strip()))

    with conn.cursor() as cur:
        for shop, acct_id in flat:
            if not shop or not acct_id:
                continue

            cur.execute(
                "SELECT 1 FROM ad_account_owner_mapping WHERE ad_account_id=%s LIMIT 1",
                (acct_id,),
            )
            if not cur.fetchone():
                print(f"[WARN] {acct_id:<30} → {shop:<40} 主表未登记，跳过")
                s.warned += 1
                continue

            cur.execute(
                "SELECT shop_domain FROM store_ops_shop_ad_whitelist WHERE ad_account_id=%s LIMIT 1",
                (acct_id,),
            )
            row = cur.fetchone()
            if row:
                existed_shop = row["shop_domain"]
                if existed_shop != shop:
                    print(
                        f"[ERR ] {acct_id:<30} 已绑到其他店铺 {existed_shop}，与当前目标 {shop} 冲突"
                    )
                    s.errored += 1
                else:
                    print(f"[SKIP] {acct_id:<30} → {shop:<40} 子系统已存在")
                    s.skipped += 1
                continue

            if dry_run:
                print(f"[OK  ] {acct_id:<30} → {shop:<40} (dry-run 待插入)")
            else:
                cur.execute(
                    """
                    INSERT INTO store_ops_shop_ad_whitelist (shop_domain, ad_account_id, is_enabled)
                    VALUES (%s, %s, 1)
                    """,
                    (shop, acct_id),
                )
                print(f"[OK  ] {acct_id:<30} → {shop:<40} 已写入")
            s.inserted += 1

    print(s.line())
    return s


def backfill_operators(conn, dry_run: bool) -> BackfillSummary:
    """
    阶段 3：运营人员全局配置
    - slug 顺序严格沿用 EMPLOYEE_SLUGS_ORDERED，sort_order 以 10 为步长递增
    - display_name 从 STORE_OPS_OWNER_CN_TO_SLUG 反查；缺失时兜底为 slug 本身
    - utm_keyword = slug
    - campaign_keyword = __unset_{slug}（占位；前端上线后由运营手动补真实关键词）
    """
    s = BackfillSummary(SECTION_OPERATORS)
    print("\n======= 阶段 3: store_ops_employee_config =======")
    slug_to_cn = _slug_display_name_map()

    with conn.cursor() as cur:
        for idx, raw_slug in enumerate(EMPLOYEE_SLUGS_ORDERED):
            slug = raw_slug.strip().lower()
            if not slug:
                continue
            display_name = slug_to_cn.get(slug) or slug
            utm_keyword = slug
            campaign_keyword = f"__unset_{slug}"
            sort_order = (idx + 1) * 10

            cur.execute(
                "SELECT id FROM store_ops_employee_config WHERE employee_slug=%s LIMIT 1",
                (slug,),
            )
            if cur.fetchone():
                print(
                    f"[SKIP] slug={slug:<12} display={display_name:<8} 子系统已存在（如需更新请在 UI 做）"
                )
                s.skipped += 1
                continue

            cur.execute(
                "SELECT id FROM store_ops_employee_config WHERE utm_keyword=%s LIMIT 1",
                (utm_keyword,),
            )
            if cur.fetchone():
                print(f"[ERR ] utm_keyword={utm_keyword!r} 已被其他运营占用")
                s.errored += 1
                continue
            cur.execute(
                "SELECT id FROM store_ops_employee_config WHERE campaign_keyword=%s LIMIT 1",
                (campaign_keyword,),
            )
            if cur.fetchone():
                print(f"[ERR ] campaign_keyword={campaign_keyword!r} 已被其他运营占用")
                s.errored += 1
                continue

            if dry_run:
                print(
                    f"[OK  ] slug={slug:<12} display={display_name:<6} "
                    f"utm={utm_keyword:<12} campaign={campaign_keyword:<20} sort={sort_order} (dry-run)"
                )
            else:
                cur.execute(
                    """
                    INSERT INTO store_ops_employee_config
                        (employee_slug, display_name, utm_keyword, campaign_keyword,
                         status, sort_order, deleted_at)
                    VALUES (%s, %s, %s, %s, 'active', %s, NULL)
                    """,
                    (slug, display_name, utm_keyword, campaign_keyword, sort_order),
                )
                print(
                    f"[OK  ] slug={slug:<12} display={display_name:<6} "
                    f"utm={utm_keyword:<12} campaign={campaign_keyword:<20} sort={sort_order} 已写入"
                )
            s.inserted += 1

    print(s.line())
    return s


def run_section(db: Database, section: str, dry_run: bool) -> BackfillSummary:
    """每个 section 独立事务：失败只影响本段。"""
    handler = {
        SECTION_SHOPS: backfill_shops,
        SECTION_AD_WHITELIST: backfill_ad_whitelist,
        SECTION_OPERATORS: backfill_operators,
    }[section]

    conn = db.get_connection()
    try:
        summary = handler(conn, dry_run=dry_run)
        if dry_run:
            conn.rollback()
        elif summary.errored > 0:
            conn.rollback()
            print(f"[TXN ] {section}: 存在错误，事务已回滚")
        else:
            conn.commit()
            print(f"[TXN ] {section}: 事务已提交")
        return summary
    except Exception as e:
        conn.rollback()
        print(f"[FATAL] {section}: 异常回滚 -> {e!r}")
        raise
    finally:
        conn.close()


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="店铺运营子系统数据回填")
    parser.add_argument("--apply", action="store_true", help="真正写入数据库；不加则 dry-run")
    parser.add_argument(
        "--only",
        choices=ALL_SECTIONS,
        default=None,
        help="仅执行指定阶段；默认全跑",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    sections = (args.only,) if args.only else ALL_SECTIONS

    mode_banner = "DRY-RUN（不写库）" if dry_run else "APPLY（真正写入）"
    print(f"==== 店铺运营子系统回填 · 模式: {mode_banner} · 阶段: {sections} ====")

    db = Database()
    summaries: List[BackfillSummary] = []
    try:
        for section in sections:
            summaries.append(run_section(db, section, dry_run=dry_run))
    except Exception:
        sys.exit(1)

    print("\n======= 汇总 =======")
    total_errors = 0
    for s in summaries:
        print(s.line())
        total_errors += s.errored

    if dry_run:
        print("\n[DRY-RUN] 未写入数据库。确认无误后加 --apply 重跑。")
    elif total_errors > 0:
        print("\n[结果] 存在错误，部分段已回滚。请检查上方 [ERR]/[FATAL] 日志。")
        sys.exit(1)
    else:
        print("\n[结果] 全部阶段成功写入。")


if __name__ == "__main__":
    main()
