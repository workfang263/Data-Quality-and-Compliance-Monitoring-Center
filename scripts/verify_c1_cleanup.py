"""C.1 冒烟后确认：临时 operator 已软删，审计留痕，配置表无垃圾数据。"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
for p in (_ROOT, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.database_new import Database  # type: ignore


def main() -> int:
    db = Database()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, employee_slug, status, deleted_at "
                "FROM store_ops_employee_config WHERE employee_slug LIKE 'smoke_%'"
            )
            ops = cur.fetchall() or []
            print(f"[operator] 冒烟残留行数: {len(ops)}")
            for r in ops:
                print(f"  id={r['id']} slug={r['employee_slug']} "
                      f"status={r['status']} deleted_at={r['deleted_at']}")
            all_soft_deleted = all(r.get("deleted_at") is not None for r in ops)
            print(f"[operator] 全部 deleted_at 非空: {all_soft_deleted}")

            cur.execute(
                "SELECT COUNT(*) AS c FROM store_ops_config_audit "
                "WHERE resource_type = 'operator' AND resource_key LIKE 'smoke_%'"
            )
            row = cur.fetchone()
            print(f"[audit] 冒烟相关审计条数: {row['c']}")

            cur.execute(
                "SELECT action, COUNT(*) AS c FROM store_ops_config_audit "
                "WHERE resource_type = 'operator' AND resource_key LIKE 'smoke_%' "
                "GROUP BY action ORDER BY c DESC"
            )
            print("[audit] 按 action 分组：")
            for r in cur.fetchall() or []:
                print(f"  {r['action']}: {r['c']}")

            cur.execute(
                "SELECT COUNT(*) AS c FROM store_ops_employee_config "
                "WHERE deleted_at IS NULL"
            )
            print(f"\n[sanity] 当前未删除运营数: {cur.fetchone()['c']}")

            cur.execute(
                "SELECT COUNT(*) AS c FROM store_ops_shop_whitelist "
                "WHERE is_enabled = 1"
            )
            print(f"[sanity] 当前启用店铺数: {cur.fetchone()['c']}")

            cur.execute(
                "SELECT COUNT(*) AS c FROM store_ops_shop_ad_whitelist "
                "WHERE is_enabled = 1"
            )
            print(f"[sanity] 当前启用广告账户数: {cur.fetchone()['c']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
