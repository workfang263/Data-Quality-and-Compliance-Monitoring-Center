"""
【店铺运营子系统】配置中心 API - 读写 + 审计（阶段 B.1-b + C.1）

职责：
    - 读/写子系统三张配置表：
        shops         = store_ops_shop_whitelist
        ad_whitelist  = store_ops_shop_ad_whitelist
        operator      = store_ops_employee_config
    - 读主系统两张引用表（shoplazza_stores / ad_account_owner_mapping）的"可加入候选"
    - 所有写操作落 store_ops_config_audit（独立审计表）

设计原则（与方案第 1 节"核心边界"一致）：
    - 本模块对主系统表只 SELECT，绝不做任何写操作
    - SQL 全部收敛在本文件内，不依赖主系统面向展示的 Database 方法
    - 统一响应壳：{"code": 200, "message": "success", "data": ...}
    - 读权限：登录即可（Depends(get_current_user)）
    - 写权限：admin 或 can_edit_store_ops_config=True
    - 软删策略：
        - operator：deleted_at = NOW()（不物理删；历史归因数据保留）
        - shop/ad_whitelist：is_enabled = 0（没有 deleted_at 列，复用启用开关）
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.auth_api import get_current_user
from app.services.database_new import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/store-ops/config", tags=["store-ops-config"])

_db: Optional[Database] = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def _ok(data: Any) -> Dict[str, Any]:
    return {"code": 200, "message": "success", "data": data}


# =============================================================================
# 权限依赖：写接口专用
# =============================================================================

def require_can_edit_store_ops_config(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """admin 直通；否则必须 can_edit_store_ops_config=True。"""
    if current_user.get("role") == "admin":
        return current_user
    ext = _get_db().get_user_extended_permissions(current_user["id"])
    if not ext.get("can_edit_store_ops_config"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无店铺运营配置编辑权限（can_edit_store_ops_config=False）",
        )
    return current_user


# =============================================================================
# 审计 helper：统一往 store_ops_config_audit 写一条
# =============================================================================

_AUDIT_RESOURCE_TYPES = {"shop", "ad_whitelist", "operator"}
_AUDIT_ACTIONS = {
    "create", "update", "delete", "enable", "disable", "block", "unblock",
}


def _write_audit(
    cur,
    *,
    resource_type: str,
    resource_key: str,
    action: str,
    actor_user_id: Optional[int],
    actor_username: Optional[str],
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    changes: Optional[Dict[str, Any]] = None,
    result_status: str = "success",
    result_message: Optional[str] = None,
) -> None:
    """
    统一写审计行。复用调用方已有的 cursor，方便放在同一事务内回滚。

    request_payload 字段打包成 {"before":..., "after":..., "changes":...}，
    便于未来在审计页做"变更 diff"展示；敏感字段调用方自行脱敏（本表从未接触 token/密码）。
    """
    if resource_type not in _AUDIT_RESOURCE_TYPES:
        raise ValueError(f"非法 resource_type: {resource_type}")
    if action not in _AUDIT_ACTIONS:
        raise ValueError(f"非法 action: {action}")

    payload_obj: Dict[str, Any] = {}
    if before is not None:
        payload_obj["before"] = before
    if after is not None:
        payload_obj["after"] = after
    if changes is not None:
        payload_obj["changes"] = changes
    payload_json = json.dumps(payload_obj, ensure_ascii=False, default=str) if payload_obj else None

    cur.execute(
        """
        INSERT INTO store_ops_config_audit
            (resource_type, resource_key, action,
             actor_user_id, actor_username,
             request_payload, result_status, result_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            resource_type, resource_key, action,
            actor_user_id, actor_username,
            payload_json, result_status, result_message,
        ),
    )


def _row_to_dict(cur, row) -> Dict[str, Any]:
    """DictCursor 场景下 row 本身就是 dict；兼容万一是 tuple 的情况。"""
    if isinstance(row, dict):
        return dict(row)
    desc = [d[0] for d in cur.description]
    return dict(zip(desc, row))


# =============================================================================
# 店铺白名单：store_ops_shop_whitelist —— GET 接口（B.1-b 遗留）
# =============================================================================

@router.get("/shops")
async def list_shops(
    _current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """子系统已加入的店铺列表（启用 + 停用全部返回；前端自行过滤）。"""
    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, shop_domain, is_enabled, created_at, updated_at
                    FROM store_ops_shop_whitelist
                    ORDER BY is_enabled DESC, shop_domain ASC
                    """
                )
                rows = cur.fetchall()
        return _ok(rows)
    except Exception as e:
        logger.error(f"list_shops 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取店铺白名单失败: {e}")


@router.get("/available-shops")
async def list_available_shops(
    _current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    主系统 store_owner_mapping 中的所有店铺候选。

    说明：
    - 直接对齐「映射编辑」页数据源（store_owner_mapping），不再额外过滤 is_active
    - 返回全量候选，每条带 ``already_bound``（是否已在子系统白名单）与 ``owner``
    - 前端可据此把已绑定的条目置灰/禁用，避免重复加入
    """
    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        m.shop_domain,
                        m.owner,
                        CASE WHEN w.shop_domain IS NULL THEN 0 ELSE 1 END AS already_bound
                    FROM store_owner_mapping m
                    LEFT JOIN store_ops_shop_whitelist w
                        ON w.shop_domain = m.shop_domain COLLATE utf8mb4_unicode_ci
                    ORDER BY m.shop_domain ASC
                    """
                )
                rows = cur.fetchall() or []
                for r in rows:
                    r["already_bound"] = bool(r.get("already_bound"))
        return _ok(rows)
    except Exception as e:
        logger.error(f"list_available_shops 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取可加入店铺候选失败: {e}")


# =============================================================================
# 店铺白名单：POST / PATCH / DELETE （C.1.3）
# =============================================================================

class ShopCreateRequest(BaseModel):
    shop_domain: str = Field(..., min_length=3, max_length=255)


class ShopPatchRequest(BaseModel):
    is_enabled: Optional[bool] = None


def _fetch_shop_by_id(cur, shop_id: int) -> Optional[Dict[str, Any]]:
    cur.execute(
        "SELECT id, shop_domain, is_enabled FROM store_ops_shop_whitelist WHERE id=%s",
        (shop_id,),
    )
    r = cur.fetchone()
    return _row_to_dict(cur, r) if r else None


@router.post("/shops", status_code=status.HTTP_201_CREATED)
async def create_shop(
    body: ShopCreateRequest = Body(...),
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """
    添加店铺到子系统白名单。

    规则：
    - shop_domain 必须存在于主系统「店铺映射」(store_owner_mapping)，与
      「映射编辑」页数据源保持一致；不再强制要求 is_active=1
    - 已存在于子系统白名单（无论启用/停用）→ 409
    """
    domain = (body.shop_domain or "").strip()
    if not domain:
        raise HTTPException(400, detail="shop_domain 不能为空")

    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM store_owner_mapping WHERE shop_domain = %s",
                    (domain,),
                )
                if not cur.fetchone():
                    raise HTTPException(
                        400,
                        detail=f"主系统「店铺映射」中不存在该店铺: {domain}",
                    )
                cur.execute(
                    "SELECT id FROM store_ops_shop_whitelist WHERE shop_domain = %s",
                    (domain,),
                )
                if cur.fetchone():
                    raise HTTPException(409, detail=f"店铺已在白名单: {domain}")

                cur.execute(
                    """
                    INSERT INTO store_ops_shop_whitelist (shop_domain, is_enabled)
                    VALUES (%s, 1)
                    """,
                    (domain,),
                )
                new_id = cur.lastrowid
                _write_audit(
                    cur,
                    resource_type="shop",
                    resource_key=domain,
                    action="create",
                    actor_user_id=user.get("id"),
                    actor_username=user.get("username"),
                    after={"id": new_id, "shop_domain": domain, "is_enabled": 1},
                )
            conn.commit()
        return _ok({"id": new_id, "shop_domain": domain, "is_enabled": 1})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_shop 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"添加店铺失败: {e}")


@router.patch("/shops/{shop_id}")
async def patch_shop(
    shop_id: int,
    body: ShopPatchRequest = Body(...),
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """切换店铺 is_enabled（启用/停用）。"""
    if body.is_enabled is None:
        raise HTTPException(400, detail="至少需要提供 is_enabled")

    new_enabled = 1 if body.is_enabled else 0
    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                before = _fetch_shop_by_id(cur, shop_id)
                if not before:
                    raise HTTPException(404, detail=f"店铺 id={shop_id} 不存在")

                if before["is_enabled"] == new_enabled:
                    return _ok({**before, "changed": False})

                cur.execute(
                    "UPDATE store_ops_shop_whitelist SET is_enabled = %s WHERE id = %s",
                    (new_enabled, shop_id),
                )
                action = "enable" if new_enabled == 1 else "disable"
                _write_audit(
                    cur,
                    resource_type="shop",
                    resource_key=before["shop_domain"],
                    action=action,
                    actor_user_id=user.get("id"),
                    actor_username=user.get("username"),
                    before=before,
                    after={**before, "is_enabled": new_enabled},
                    changes={"is_enabled": [before["is_enabled"], new_enabled]},
                )
            conn.commit()
        return _ok({**before, "is_enabled": new_enabled, "changed": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"patch_shop 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"更新店铺失败: {e}")


@router.delete("/shops/{shop_id}")
async def delete_shop(
    shop_id: int,
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """软删除（置 is_enabled=0）。已停用则幂等返回 changed=False。"""
    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                before = _fetch_shop_by_id(cur, shop_id)
                if not before:
                    raise HTTPException(404, detail=f"店铺 id={shop_id} 不存在")
                if before["is_enabled"] == 0:
                    return _ok({**before, "changed": False})
                cur.execute(
                    "UPDATE store_ops_shop_whitelist SET is_enabled = 0 WHERE id = %s",
                    (shop_id,),
                )
                _write_audit(
                    cur,
                    resource_type="shop",
                    resource_key=before["shop_domain"],
                    action="delete",
                    actor_user_id=user.get("id"),
                    actor_username=user.get("username"),
                    before=before,
                    after={**before, "is_enabled": 0},
                )
            conn.commit()
        return _ok({**before, "is_enabled": 0, "changed": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_shop 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"删除店铺失败: {e}")


# =============================================================================
# 广告账户白名单：store_ops_shop_ad_whitelist —— GET（B.1-b 遗留）
# =============================================================================

@router.get("/ad-accounts")
async def list_ad_accounts(
    shop_domain: Optional[str] = Query(None, description="按店铺过滤；不传返回全部"),
    _current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """广告账户白名单列表。"""
    domain = (shop_domain or "").strip()
    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                if domain:
                    cur.execute(
                        """
                        SELECT id, shop_domain, ad_account_id, is_enabled,
                               created_at, updated_at
                        FROM store_ops_shop_ad_whitelist
                        WHERE shop_domain = %s
                        ORDER BY is_enabled DESC, ad_account_id ASC
                        """,
                        (domain,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, shop_domain, ad_account_id, is_enabled,
                               created_at, updated_at
                        FROM store_ops_shop_ad_whitelist
                        ORDER BY shop_domain ASC, is_enabled DESC, ad_account_id ASC
                        """
                    )
                rows = cur.fetchall()
        return _ok(rows)
    except Exception as e:
        logger.error(f"list_ad_accounts 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"获取广告账户白名单失败: {e}")


@router.get("/available-ad-accounts")
async def list_available_ad_accounts(
    _current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    主系统 ad_account_owner_mapping（Facebook）全量候选。

    说明：
    - 对齐「映射编辑 / Facebook」页数据源
    - 返回全部账户；每条带 ``already_bound`` 与 ``bound_shop_domain``
      （已被哪家店铺绑定；未绑定则为 None）
    - 前端在下拉里展示全部，已绑定的置灰/禁用
    """
    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        m.ad_account_id,
                        m.owner,
                        w.shop_domain AS bound_shop_domain,
                        CASE WHEN w.ad_account_id IS NULL THEN 0 ELSE 1 END AS already_bound
                    FROM ad_account_owner_mapping m
                    LEFT JOIN store_ops_shop_ad_whitelist w
                        ON w.ad_account_id = m.ad_account_id COLLATE utf8mb4_unicode_ci
                    ORDER BY m.ad_account_id ASC
                    """
                )
                rows = cur.fetchall() or []
                for r in rows:
                    r["already_bound"] = bool(r.get("already_bound"))
        return _ok(rows)
    except Exception as e:
        logger.error(f"list_available_ad_accounts 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"获取可加入广告账户候选失败: {e}")


# =============================================================================
# 广告账户白名单：POST / PATCH / DELETE （C.1.4）
# =============================================================================

class AdAccountCreateRequest(BaseModel):
    shop_domain: str = Field(..., min_length=3, max_length=255)
    ad_account_id: str = Field(..., min_length=1, max_length=64)


class AdAccountPatchRequest(BaseModel):
    is_enabled: Optional[bool] = None
    shop_domain: Optional[str] = Field(default=None, min_length=3, max_length=255)


def _fetch_adacc_by_id(cur, adacc_id: int) -> Optional[Dict[str, Any]]:
    cur.execute(
        """
        SELECT id, shop_domain, ad_account_id, is_enabled
        FROM store_ops_shop_ad_whitelist WHERE id = %s
        """,
        (adacc_id,),
    )
    r = cur.fetchone()
    return _row_to_dict(cur, r) if r else None


@router.post("/ad-accounts", status_code=status.HTTP_201_CREATED)
async def create_ad_account(
    body: AdAccountCreateRequest = Body(...),
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """
    把广告账户绑到店铺。
    - 店铺必须已在子系统白名单且启用
    - ad_account_id 全局唯一（DDL 硬约束），重复 → 409
    """
    domain = (body.shop_domain or "").strip()
    acc_id = (body.ad_account_id or "").strip()
    if not domain or not acc_id:
        raise HTTPException(400, detail="shop_domain / ad_account_id 不能为空")

    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_enabled FROM store_ops_shop_whitelist WHERE shop_domain=%s",
                    (domain,),
                )
                shop_row = cur.fetchone()
                if not shop_row:
                    raise HTTPException(400, detail=f"店铺未加入子系统: {domain}")
                shop_row_d = _row_to_dict(cur, shop_row)
                if int(shop_row_d.get("is_enabled") or 0) != 1:
                    raise HTTPException(400, detail=f"店铺已停用，不能绑账户: {domain}")

                cur.execute(
                    "SELECT id, shop_domain FROM store_ops_shop_ad_whitelist WHERE ad_account_id=%s",
                    (acc_id,),
                )
                exist = cur.fetchone()
                if exist:
                    exist_d = _row_to_dict(cur, exist)
                    raise HTTPException(
                        409,
                        detail=f"广告账户已被占用: {acc_id} → {exist_d.get('shop_domain')}",
                    )

                cur.execute(
                    """
                    INSERT INTO store_ops_shop_ad_whitelist
                        (shop_domain, ad_account_id, is_enabled)
                    VALUES (%s, %s, 1)
                    """,
                    (domain, acc_id),
                )
                new_id = cur.lastrowid
                after_obj = {
                    "id": new_id, "shop_domain": domain,
                    "ad_account_id": acc_id, "is_enabled": 1,
                }
                _write_audit(
                    cur,
                    resource_type="ad_whitelist",
                    resource_key=acc_id,
                    action="create",
                    actor_user_id=user.get("id"),
                    actor_username=user.get("username"),
                    after=after_obj,
                )
            conn.commit()
        return _ok(after_obj)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_ad_account 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"绑定广告账户失败: {e}")


@router.patch("/ad-accounts/{adacc_id}")
async def patch_ad_account(
    adacc_id: int,
    body: AdAccountPatchRequest = Body(...),
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """
    修改广告账户：切换 is_enabled 或改 shop_domain（重新绑到另一家店）。
    若换店：目标店铺必须已启用。
    """
    if body.is_enabled is None and body.shop_domain is None:
        raise HTTPException(400, detail="至少需要提供 is_enabled 或 shop_domain")

    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                before = _fetch_adacc_by_id(cur, adacc_id)
                if not before:
                    raise HTTPException(404, detail=f"广告账户 id={adacc_id} 不存在")

                updates: Dict[str, Any] = {}
                set_parts: List[str] = []
                set_vals: List[Any] = []

                if body.shop_domain is not None:
                    new_domain = body.shop_domain.strip()
                    if new_domain != before["shop_domain"]:
                        cur.execute(
                            "SELECT is_enabled FROM store_ops_shop_whitelist WHERE shop_domain=%s",
                            (new_domain,),
                        )
                        shop_row = cur.fetchone()
                        if not shop_row:
                            raise HTTPException(400, detail=f"目标店铺未加入子系统: {new_domain}")
                        if int(_row_to_dict(cur, shop_row).get("is_enabled") or 0) != 1:
                            raise HTTPException(400, detail=f"目标店铺已停用: {new_domain}")
                        set_parts.append("shop_domain = %s")
                        set_vals.append(new_domain)
                        updates["shop_domain"] = [before["shop_domain"], new_domain]

                if body.is_enabled is not None:
                    new_en = 1 if body.is_enabled else 0
                    if new_en != before["is_enabled"]:
                        set_parts.append("is_enabled = %s")
                        set_vals.append(new_en)
                        updates["is_enabled"] = [before["is_enabled"], new_en]

                if not set_parts:
                    return _ok({**before, "changed": False})

                set_vals.append(adacc_id)
                cur.execute(
                    f"UPDATE store_ops_shop_ad_whitelist SET {', '.join(set_parts)} WHERE id = %s",
                    tuple(set_vals),
                )

                if "is_enabled" in updates and "shop_domain" not in updates:
                    action = "enable" if updates["is_enabled"][1] == 1 else "disable"
                else:
                    action = "update"

                after = _fetch_adacc_by_id(cur, adacc_id) or {}
                _write_audit(
                    cur,
                    resource_type="ad_whitelist",
                    resource_key=before["ad_account_id"],
                    action=action,
                    actor_user_id=user.get("id"),
                    actor_username=user.get("username"),
                    before=before,
                    after=after,
                    changes=updates,
                )
            conn.commit()
        return _ok({**after, "changed": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"patch_ad_account 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"更新广告账户失败: {e}")


@router.delete("/ad-accounts/{adacc_id}")
async def delete_ad_account(
    adacc_id: int,
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """软删除：is_enabled=0。已停用则幂等。"""
    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                before = _fetch_adacc_by_id(cur, adacc_id)
                if not before:
                    raise HTTPException(404, detail=f"广告账户 id={adacc_id} 不存在")
                if before["is_enabled"] == 0:
                    return _ok({**before, "changed": False})
                cur.execute(
                    "UPDATE store_ops_shop_ad_whitelist SET is_enabled=0 WHERE id=%s",
                    (adacc_id,),
                )
                _write_audit(
                    cur,
                    resource_type="ad_whitelist",
                    resource_key=before["ad_account_id"],
                    action="delete",
                    actor_user_id=user.get("id"),
                    actor_username=user.get("username"),
                    before=before,
                    after={**before, "is_enabled": 0},
                )
            conn.commit()
        return _ok({**before, "is_enabled": 0, "changed": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_ad_account 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"删除广告账户失败: {e}")


# =============================================================================
# 运营人员全局配置：store_ops_employee_config —— GET（B.1-b 遗留）
# =============================================================================

@router.get("/operators")
async def list_operators(
    include_deleted: bool = Query(False, description="是否包含已软删的运营"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="仅返回指定状态；可选 active / blocked"
    ),
    _current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """运营人员全局配置列表。"""
    status_norm = (status_filter or "").strip().lower()
    if status_norm and status_norm not in ("active", "blocked"):
        raise HTTPException(400, detail="status 仅支持 active / blocked")

    where_parts: List[str] = []
    params: List[Any] = []
    if not include_deleted:
        where_parts.append("deleted_at IS NULL")
    if status_norm:
        where_parts.append("status = %s")
        params.append(status_norm)
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
        SELECT id, employee_slug, display_name, utm_keyword, campaign_keyword,
               status, sort_order, deleted_at, created_at, updated_at
        FROM store_ops_employee_config
        {where_sql}
        ORDER BY sort_order ASC, id ASC
    """
    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        return _ok(rows)
    except Exception as e:
        logger.error(f"list_operators 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"获取运营列表失败: {e}")


# =============================================================================
# 运营人员：POST / PATCH / DELETE （C.1.2）
# =============================================================================

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


class OperatorCreateRequest(BaseModel):
    employee_slug: str = Field(..., min_length=2, max_length=32)
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    utm_keyword: Optional[str] = Field(default=None, max_length=64)
    campaign_keyword: Optional[str] = Field(default=None, max_length=64)
    sort_order: Optional[int] = None


class OperatorPatchRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    utm_keyword: Optional[str] = Field(default=None, max_length=64)
    campaign_keyword: Optional[str] = Field(default=None, max_length=64)
    sort_order: Optional[int] = None
    operator_status: Optional[str] = Field(
        default=None, description="active / blocked"
    )


def _fetch_operator_by_id(cur, op_id: int) -> Optional[Dict[str, Any]]:
    cur.execute(
        """
        SELECT id, employee_slug, display_name, utm_keyword, campaign_keyword,
               status, sort_order, deleted_at
        FROM store_ops_employee_config WHERE id = %s
        """,
        (op_id,),
    )
    r = cur.fetchone()
    return _row_to_dict(cur, r) if r else None


def _invalidate_operator_cache() -> None:
    """任何运营写操作后，清 TTL 缓存，避免 30 秒内归因走旧数据。"""
    try:
        from app.services.store_ops_attribution import reset_cache_for_tests
        reset_cache_for_tests()
    except Exception as e:
        logger.warning("清运营缓存失败（不影响主流程）: %s", e)


@router.post("/operators", status_code=status.HTTP_201_CREATED)
async def create_operator(
    body: OperatorCreateRequest = Body(...),
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """
    新增一个运营。
    - employee_slug：[a-z][a-z0-9_]{1,31}；全局唯一
    - utm_keyword 留空 → 自动填 employee_slug（便于原有 UTM 归因立即能用）
    - campaign_keyword 留空 → 自动填 `__unset_{slug}`（占位符，B.3 策略 1.5 约定）
    - 三个 keyword 均 UNIQUE；冲突 → 409
    """
    slug = (body.employee_slug or "").strip().lower()
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            400,
            detail="employee_slug 必须小写字母开头、仅含 [a-z0-9_]、长度 2-32",
        )
    # display_name 留空 → 自动用 employee_slug（前端精简新增表单后默认走这条分支）
    display = (body.display_name or "").strip() or slug

    utm_kw = (body.utm_keyword or "").strip().lower() or slug
    cmp_kw = (body.campaign_keyword or "").strip().lower() or f"__unset_{slug}"
    sort_order = body.sort_order if body.sort_order is not None else 100

    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, employee_slug, utm_keyword, campaign_keyword
                    FROM store_ops_employee_config
                    WHERE employee_slug=%s OR utm_keyword=%s OR campaign_keyword=%s
                    """,
                    (slug, utm_kw, cmp_kw),
                )
                existing = cur.fetchall() or []
                if existing:
                    exist_d = [_row_to_dict(cur, r) for r in existing]
                    raise HTTPException(
                        409,
                        detail=f"slug / utm_keyword / campaign_keyword 冲突: {exist_d}",
                    )

                cur.execute(
                    """
                    INSERT INTO store_ops_employee_config
                        (employee_slug, display_name, utm_keyword, campaign_keyword,
                         status, sort_order)
                    VALUES (%s, %s, %s, %s, 'active', %s)
                    """,
                    (slug, display, utm_kw, cmp_kw, sort_order),
                )
                new_id = cur.lastrowid
                after_obj = {
                    "id": new_id, "employee_slug": slug, "display_name": display,
                    "utm_keyword": utm_kw, "campaign_keyword": cmp_kw,
                    "status": "active", "sort_order": sort_order,
                }
                _write_audit(
                    cur,
                    resource_type="operator",
                    resource_key=slug,
                    action="create",
                    actor_user_id=user.get("id"),
                    actor_username=user.get("username"),
                    after=after_obj,
                )
            conn.commit()
        _invalidate_operator_cache()
        return _ok(after_obj)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_operator 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"新增运营失败: {e}")


@router.patch("/operators/{op_id}")
async def patch_operator(
    op_id: int,
    body: OperatorPatchRequest = Body(...),
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """
    修改运营字段：display_name / utm_keyword / campaign_keyword / sort_order / status。
    - utm_keyword / campaign_keyword 清空 → 自动回填占位（避免 UNIQUE NOT NULL 冲突）
    - status='blocked' → 归因依然跑但前端不展示；audit action=block
    """
    provided_any = any(
        v is not None for v in
        (body.display_name, body.utm_keyword, body.campaign_keyword,
         body.sort_order, body.operator_status)
    )
    if not provided_any:
        raise HTTPException(400, detail="没有提供任何待修改字段")

    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                before = _fetch_operator_by_id(cur, op_id)
                if not before:
                    raise HTTPException(404, detail=f"运营 id={op_id} 不存在")
                if before.get("deleted_at") is not None:
                    raise HTTPException(
                        400, detail=f"运营 {before['employee_slug']} 已软删，请先恢复",
                    )

                slug = before["employee_slug"]
                updates: Dict[str, Any] = {}
                set_parts: List[str] = []
                set_vals: List[Any] = []
                action = "update"

                if body.display_name is not None:
                    v = body.display_name.strip()
                    if v and v != before["display_name"]:
                        set_parts.append("display_name = %s")
                        set_vals.append(v)
                        updates["display_name"] = [before["display_name"], v]

                def _handle_kw(field: str, new_raw: Optional[str], default_fill: str):
                    if new_raw is None:
                        return
                    v = (new_raw or "").strip().lower() or default_fill
                    if v != before[field]:
                        cur.execute(
                            f"SELECT id FROM store_ops_employee_config "
                            f"WHERE {field} = %s AND id != %s",
                            (v, op_id),
                        )
                        if cur.fetchone():
                            raise HTTPException(409, detail=f"{field}={v} 已被占用")
                        set_parts.append(f"{field} = %s")
                        set_vals.append(v)
                        updates[field] = [before[field], v]

                _handle_kw("utm_keyword", body.utm_keyword, slug)
                _handle_kw("campaign_keyword", body.campaign_keyword, f"__unset_{slug}")

                if body.sort_order is not None and body.sort_order != before["sort_order"]:
                    set_parts.append("sort_order = %s")
                    set_vals.append(body.sort_order)
                    updates["sort_order"] = [before["sort_order"], body.sort_order]

                if body.operator_status is not None:
                    new_status = body.operator_status.strip().lower()
                    if new_status not in ("active", "blocked"):
                        raise HTTPException(400, detail="operator_status 仅支持 active/blocked")
                    if new_status != before["status"]:
                        set_parts.append("status = %s")
                        set_vals.append(new_status)
                        updates["status"] = [before["status"], new_status]
                        action = "block" if new_status == "blocked" else "unblock"

                if not set_parts:
                    return _ok({**before, "changed": False})

                set_vals.append(op_id)
                cur.execute(
                    f"UPDATE store_ops_employee_config SET {', '.join(set_parts)} "
                    f"WHERE id = %s",
                    tuple(set_vals),
                )
                after = _fetch_operator_by_id(cur, op_id) or {}
                _write_audit(
                    cur,
                    resource_type="operator",
                    resource_key=slug,
                    action=action,
                    actor_user_id=user.get("id"),
                    actor_username=user.get("username"),
                    before=before,
                    after=after,
                    changes=updates,
                )
            conn.commit()
        _invalidate_operator_cache()
        return _ok({**after, "changed": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"patch_operator 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"更新运营失败: {e}")


@router.delete("/operators/{op_id}")
async def delete_operator(
    op_id: int,
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """软删除运营：置 deleted_at=NOW()。历史归因数据保留。已删则幂等。"""
    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                before = _fetch_operator_by_id(cur, op_id)
                if not before:
                    raise HTTPException(404, detail=f"运营 id={op_id} 不存在")
                if before.get("deleted_at") is not None:
                    return _ok({**before, "changed": False})
                cur.execute(
                    "UPDATE store_ops_employee_config SET deleted_at = NOW() WHERE id = %s",
                    (op_id,),
                )
                after = _fetch_operator_by_id(cur, op_id) or {}
                _write_audit(
                    cur,
                    resource_type="operator",
                    resource_key=before["employee_slug"],
                    action="delete",
                    actor_user_id=user.get("id"),
                    actor_username=user.get("username"),
                    before=before,
                    after=after,
                )
            conn.commit()
        _invalidate_operator_cache()
        return _ok({**after, "changed": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_operator 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"删除运营失败: {e}")


# =============================================================================
# 审计日志：GET（C.1.5）
# =============================================================================

@router.get("/audit")
async def list_audit(
    resource_type: Optional[str] = Query(None, description="shop / ad_whitelist / operator"),
    action: Optional[str] = Query(None, description="create/update/delete/enable/disable/block/unblock"),
    resource_key: Optional[str] = Query(None, description="精确匹配"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_can_edit_store_ops_config),
) -> Dict[str, Any]:
    """
    审计分页查询（最新优先）。
    只对"可编辑"权限开放——纯浏览员工不应看到操作痕迹。
    """
    if resource_type and resource_type not in _AUDIT_RESOURCE_TYPES:
        raise HTTPException(400, detail=f"resource_type 仅支持 {_AUDIT_RESOURCE_TYPES}")
    if action and action not in _AUDIT_ACTIONS:
        raise HTTPException(400, detail=f"action 仅支持 {_AUDIT_ACTIONS}")

    where_parts: List[str] = []
    params: List[Any] = []
    if resource_type:
        where_parts.append("resource_type = %s")
        params.append(resource_type)
    if action:
        where_parts.append("action = %s")
        params.append(action)
    if resource_key:
        where_parts.append("resource_key = %s")
        params.append(resource_key.strip())
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    try:
        with _get_db().get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS c FROM store_ops_config_audit {where_sql}",
                    tuple(params),
                )
                cnt_row = cur.fetchone()
                total = int(_row_to_dict(cur, cnt_row).get("c", 0)) if cnt_row else 0

                cur.execute(
                    f"""
                    SELECT id, resource_type, resource_key, action,
                           actor_user_id, actor_username,
                           request_payload, result_status, result_message,
                           created_at
                    FROM store_ops_config_audit
                    {where_sql}
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params) + (limit, offset),
                )
                rows = cur.fetchall() or []

        items: List[Dict[str, Any]] = []
        for r in rows:
            d = _row_to_dict(cur, r)
            payload_raw = d.get("request_payload")
            if isinstance(payload_raw, (bytes, bytearray)):
                payload_raw = payload_raw.decode("utf-8", errors="replace")
            if isinstance(payload_raw, str) and payload_raw:
                try:
                    d["request_payload"] = json.loads(payload_raw)
                except Exception:
                    pass
            items.append(d)
        return _ok({"total": total, "limit": limit, "offset": offset, "items": items})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_audit 失败: {e}", exc_info=True)
        raise HTTPException(500, detail=f"查询审计失败: {e}")
