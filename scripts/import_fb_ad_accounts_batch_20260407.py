"""
批量导入 Facebook 广告账户 → ad_account_owner_mapping，并修正 fb_ad_account_spend_hourly.owner，
并对有数据的日期重跑负责人日聚合（owner_daily_summary），保证看板「负责人汇总」口径一致。

数据批次：Sunelva-TD-260402-* / Bertlove-TD-ZK-260206-*（2026-04-07 需求）

用法（项目根目录）：
  python scripts/import_fb_ad_accounts_batch_20260407.py
  python scripts/import_fb_ad_accounts_batch_20260407.py --no-aggregate   # 只写映射与花费表，不聚合

依赖：根目录 config.py / database.py（与 add_fb_account.py 相同）
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Tuple

# 项目根
if __name__ == "__main__":
    import os

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from aggregate_owner_daily import aggregate_date
from database import Database
from mapping_resource_utils import normalize_fb_ad_account_id

# (原始数字 ID 或 act_ 均可, 负责人) —— 名称见 db/migrations 注释
BATCH: List[Tuple[str, str]] = [
    ("1251009527180377", "阿毛"),
    ("1477243063804898", "晚秋"),
    ("832525359903650", "基米"),
    ("882617628155388", "kiki"),
    ("971610118743796", "校长"),
    ("1419981400142746", "小杨"),
    ("875355238849957", "杰尼"),
    ("4395028554063117", "阿毛"),
    ("1619760595811637", "无"),
    ("1023279760861216", "晚秋"),
    ("1222839759338297", "无"),
    ("925374940441429", "无"),
    ("879029751433363", "校长"),
    ("1220832883465993", "杰尼"),
    ("1337449094814463", "基米"),
    ("1221981739454062", "kiki"),
    ("909816892005999", "小杨"),
]


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-aggregate",
        action="store_true",
        help="跳过 owner_daily_summary 重算（仅写映射 + 修正花费表 owner）",
    )
    args = parser.parse_args()

    db = Database()
    affected: set = set()

    for raw_id, owner in BATCH:
        nid = normalize_fb_ad_account_id(raw_id)
        if not nid:
            print(f"[SKIP] 无效账户 ID: {raw_id}")
            continue
        own = (owner or "").strip() or "未分配"
        dates = db.update_ad_account_owner_mapping(nid, own)
        if dates is None:
            print(f"[ERR ] {nid} -> {own}")
            continue
        print(f"[OK ] {nid} -> {own}（历史影响日期数: {len(dates)}）")
        affected.update(dates)

    if args.no_aggregate or not affected:
        if not affected and not args.no_aggregate:
            print("[INFO] 无历史花费日期可聚合（新户正常）；有数据后可对指定日期再跑 aggregate_owner_daily")
        return

    print(f"[聚合] 共 {len(affected)} 个日历日: {sorted(affected)}")
    with db.get_connection() as conn:
        for d in sorted(affected):
            try:
                aggregate_date(conn, d, verbose=True)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"[ERR ] 聚合 {d} 失败: {e}")
                raise SystemExit(1)
    print("[完成] 映射 + 花费 owner + 日聚合 已处理")


if __name__ == "__main__":
    main()
