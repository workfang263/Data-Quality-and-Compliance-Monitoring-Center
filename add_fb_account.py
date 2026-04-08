"""
添加/更新 Facebook 广告账户（交互式）

目标：像 add_store.py 一样，通过脚本把 Facebook 广告账户写入系统的映射表：
  - ad_account_owner_mapping(ad_account_id, owner)

为什么需要这张表？
  - fb_spend_sync.py 会从 ad_account_owner_mapping 读取广告账户清单，
    逐个账户拉取花费并写入 fb_ad_account_spend_hourly。

用法（在项目根目录执行）：
  1) 交互式：
     python add_fb_account.py

  2) 命令行传参：
     python add_fb_account.py "4395028554063117" "永言"

说明：
  - 负责人可暂时为空；为空时会写入占位值“未分配”（因为数据库字段 owner NOT NULL）。
  - ad_account_id 支持输入 "act_4395028554063117" 或 "4395028554063117"；会规范化为与库内一致的 **act_纯数字**（与 fb_spend_sync、阶段0迁移一致）。
"""

from __future__ import annotations

import sys
from typing import Optional

from database import Database
from mapping_resource_utils import normalize_fb_ad_account_id


# 负责人为空时的占位值（策略 A）
UNASSIGNED_OWNER = "未分配"


def add_fb_account(ad_account_id: str, owner: Optional[str]) -> bool:
    """
    写入/更新 Facebook 广告账户映射。

    底层原理（对照 add_store.py）：
    - 映射表有 UNIQUE(ad_account_id)，所以用 ON DUPLICATE KEY UPDATE 实现“存在则更新，不存在则插入”。
    - 同时把历史花费表 fb_ad_account_spend_hourly 的 owner 字段更新为最新 owner（保持口径一致）。
    """
    # 1) 标准化为 act_{纯数字}，与明细表 / 映射表迁移后格式一致
    normalized_id = normalize_fb_ad_account_id(ad_account_id)
    if not normalized_id:
        print("错误：广告账户编号无效。请输入纯数字ID，例如 4395028554063117（也可输入 act_4395028554063117）。")
        return False

    # 2) 负责人允许为空；为空时写入占位值“未分配”（满足 NOT NULL 约束）
    owner_str = (owner or "").strip()
    if not owner_str:
        owner_str = UNASSIGNED_OWNER

    # 3) 复用项目现有 Database，确保连接配置与日志风格一致
    db = Database()

    # 4) 写入映射表，并同步修正历史数据 owner（如果该账号已有历史花费）
    affected_dates = db.update_ad_account_owner_mapping(normalized_id, owner_str)
    if affected_dates is None:
        print(f"[ERROR] 写入失败：{normalized_id} -> {owner_str}")
        return False

    # 5) 反馈：对新账号通常没有历史数据，因此受影响日期往往为空
    if affected_dates:
        print(f"[OK] 已写入映射：{normalized_id} -> {owner_str}（已修正历史数据，影响 {len(affected_dates)} 个日期）")
    else:
        print(f"[OK] 已写入映射：{normalized_id} -> {owner_str}")
    return True


def main() -> None:
    # Windows 控制台 UTF-8（避免中文输出乱码）
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # 1) 支持命令行传参：python add_fb_account.py "id" "owner"
    if len(sys.argv) >= 2:
        ad_account_id = (sys.argv[1] or "").strip()
        owner = (sys.argv[2] if len(sys.argv) >= 3 else "").strip()
    else:
        # 2) 交互式输入
        print()
        print("==========  添加/更新 Facebook 广告账户  ==========")
        print()
        ad_account_id = input("广告账户编号（例如 4395028554063117 或 act_4395028554063117）: ").strip()
        owner = input(f"该账户负责人（可留空，默认写入“{UNASSIGNED_OWNER}”）: ").strip()
        print()

    ok = add_fb_account(ad_account_id, owner)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

