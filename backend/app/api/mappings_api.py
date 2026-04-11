"""
【新系统】FastAPI后端 - 映射编辑API接口
提供映射相关的API接口，包括：
- GET /api/mappings/stores - 获取店铺映射列表
- GET /api/mappings/facebook - 获取Facebook广告账户映射列表
- GET /api/mappings/tiktok - 获取TikTok广告账户映射列表
- GET /api/mappings/owners/suggestions - 负责人联想（三表去重）
- PUT /api/mappings/stores/{id} - 更新店铺映射
- PUT /api/mappings/facebook/{id} - 更新Facebook映射
- PUT /api/mappings/tiktok/{id} - 更新TikTok映射
"""
from fastapi import APIRouter, Path, Query, HTTPException, Body, Depends, status
from typing import List, Dict, Any, Optional
from datetime import date
import logging
import os

from app.services.database_new import Database
from app.api.auth_api import get_current_user
from app.services.mapping_resource_utils import (
    normalize_fb_ad_account_id,
    validate_shoplazza_shop_domain,
    fetch_and_upsert_fb_ad_timezone,
    fetch_and_upsert_tt_ad_timezone,
)

logger = logging.getLogger(__name__)

router = APIRouter()
db = Database()


def _redact_mapping_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """审计前脱敏，避免 token/secret 明文入库。"""
    secret_keys = {
        "access_token",
        "password",
        "password_hash",
        "authorization",
        "refresh_token",
        "client_secret",
        "fb_long_lived_token",
        "store_ops_sync_secret",
        "secret",
    }

    def _walk(value: Any) -> Any:
        if isinstance(value, dict):
            out: Dict[str, Any] = {}
            for k, v in value.items():
                key = str(k).lower()
                if key in secret_keys or key.endswith("_token") or "secret" in key:
                    out[k] = "***REDACTED***"
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(value, list):
            return [_walk(x) for x in value]
        return value

    return _walk(payload)


def _check_mapping_edit_permission(current_user: Dict[str, Any]) -> None:
    """统一权限校验：普通用户需 can_edit_mappings。"""
    user_role = current_user.get("role", "user")
    if user_role != "user":
        return
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您没有权限编辑映射")
    extended_permissions = db.get_user_extended_permissions(user_id)
    can_edit_mappings = extended_permissions.get("can_edit_mappings", False)
    if not can_edit_mappings:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您没有权限编辑映射")


@router.post("/api/mappings/stores")
async def create_store_mapping(
    shop_domain: str = Body(..., description="店铺域名", embed=True),
    owner: str = Body(..., description="负责人", embed=True),
    access_token: str = Body(..., description="店铺 access token", embed=True),
    is_active: bool = Body(True, description="是否启用", embed=True),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    新增（或更新）店铺映射。
    注意：店铺侧不收集时区，按现有同步链路统一处理时间。
    """
    operator_user_id = current_user.get("id")
    operator_username = current_user.get("username")
    try:
        _check_mapping_edit_permission(current_user)

        domain = (shop_domain or "").strip().lower()
        owner_text = (owner or "").strip()
        token = (access_token or "").strip()
        if not domain or not owner_text or not token:
            raise HTTPException(status_code=400, detail="shop_domain/owner/access_token 均为必填")
        if not validate_shoplazza_shop_domain(domain):
            raise HTTPException(status_code=400, detail="shop_domain 格式不合法")

        ok = db.create_or_update_store_mapping(domain, owner_text, token, is_active)
        if not ok:
            raise HTTPException(status_code=500, detail="创建店铺映射失败")

        db.log_mapping_audit(
            action="create",
            resource_type="store",
            resource_id=domain,
            owner=owner_text,
            operator_user_id=operator_user_id,
            operator_username=operator_username,
            request_payload=_redact_mapping_payload(
                {
                    "shop_domain": domain,
                    "owner": owner_text,
                    "access_token": token,
                    "is_active": is_active,
                }
            ),
            result_status="success",
            result_message="店铺映射创建/更新成功",
        )
        return {
            "code": 200,
            "message": "success",
            "data": {
                "shop_domain": domain,
                "owner": owner_text,
                "is_active": bool(is_active),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建店铺映射失败: {e}")
        db.log_mapping_audit(
            action="create",
            resource_type="store",
            resource_id=(shop_domain or "").strip().lower(),
            owner=(owner or "").strip(),
            operator_user_id=operator_user_id,
            operator_username=operator_username,
            request_payload=_redact_mapping_payload(
                {
                    "shop_domain": shop_domain,
                    "owner": owner,
                    "access_token": access_token,
                    "is_active": is_active,
                }
            ),
            result_status="error",
            result_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.post("/api/mappings/facebook")
async def create_facebook_mapping(
    ad_account_id: str = Body(..., description="Facebook 广告账户ID，可传纯数字或 act_前缀", embed=True),
    owner: str = Body(..., description="负责人", embed=True),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    新增（或更新）Facebook 映射，并尝试自动拉取账户时区。
    时区拉取失败不阻塞映射创建，审计记 warning。
    """
    operator_user_id = current_user.get("id")
    operator_username = current_user.get("username")
    try:
        _check_mapping_edit_permission(current_user)

        owner_text = (owner or "").strip()
        normalized_id = normalize_fb_ad_account_id(ad_account_id)
        if not owner_text or not normalized_id:
            raise HTTPException(status_code=400, detail="owner 必填，ad_account_id 必须为有效数字或 act_数字")

        ok = db.create_or_update_facebook_mapping(normalized_id, owner_text)
        if not ok:
            raise HTTPException(status_code=500, detail="创建 Facebook 映射失败")

        token = (os.getenv("FB_LONG_LIVED_TOKEN") or "").strip()
        tz_result: Dict[str, Any] = {"ok": False, "message": "未尝试"}
        with db.get_connection() as conn:
            tz_result = fetch_and_upsert_fb_ad_timezone(conn, normalized_id, token)
            if tz_result.get("ok"):
                conn.commit()
            else:
                conn.rollback()

        audit_status = "success" if tz_result.get("ok") else "warning"
        audit_message = (
            "Facebook 映射创建成功，时区已更新"
            if tz_result.get("ok")
            else f"Facebook 映射创建成功，但时区拉取失败：{tz_result.get('message', 'unknown')}"
        )
        db.log_mapping_audit(
            action="create",
            resource_type="facebook",
            resource_id=normalized_id,
            owner=owner_text,
            operator_user_id=operator_user_id,
            operator_username=operator_username,
            request_payload=_redact_mapping_payload(
                {"ad_account_id": normalized_id, "owner": owner_text, "fb_token": token}
            ),
            result_status=audit_status,
            result_message=audit_message,
        )
        return {
            "code": 200,
            "message": "success",
            "data": {
                "ad_account_id": normalized_id,
                "owner": owner_text,
                "timezone_sync": tz_result,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建Facebook映射失败: {e}")
        db.log_mapping_audit(
            action="create",
            resource_type="facebook",
            resource_id=(ad_account_id or "").strip(),
            owner=(owner or "").strip(),
            operator_user_id=operator_user_id,
            operator_username=operator_username,
            request_payload=_redact_mapping_payload({"ad_account_id": ad_account_id, "owner": owner}),
            result_status="error",
            result_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.post("/api/mappings/tiktok")
async def create_tiktok_mapping(
    ad_account_id: str = Body(..., description="TikTok advertiser_id", embed=True),
    owner: str = Body(..., description="负责人", embed=True),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    新增（或更新）TikTok 映射，并按 TT_CONFIG 的 BC 顺序轮询 token 自动拉取时区。
    时区拉取失败不阻塞映射创建，审计记 warning。
    """
    operator_user_id = current_user.get("id")
    operator_username = current_user.get("username")
    try:
        _check_mapping_edit_permission(current_user)

        advertiser_id = (ad_account_id or "").strip()
        owner_text = (owner or "").strip()
        if not advertiser_id or not advertiser_id.isdigit() or not owner_text:
            raise HTTPException(status_code=400, detail="ad_account_id 必须为纯数字 advertiser_id，owner 必填")

        ok = db.create_or_update_tiktok_mapping(advertiser_id, owner_text)
        if not ok:
            raise HTTPException(status_code=500, detail="创建 TikTok 映射失败")

        tz_result: Dict[str, Any] = {"ok": False, "message": "未尝试"}
        with db.get_connection() as conn:
            tz_result = fetch_and_upsert_tt_ad_timezone(conn, advertiser_id, access_token=None)
            if tz_result.get("ok"):
                conn.commit()
            else:
                conn.rollback()

        audit_status = "success" if tz_result.get("ok") else "warning"
        audit_message = (
            "TikTok 映射创建成功，时区已更新"
            if tz_result.get("ok")
            else f"TikTok 映射创建成功，但时区拉取失败：{tz_result.get('message', 'unknown')}"
        )
        db.log_mapping_audit(
            action="create",
            resource_type="tiktok",
            resource_id=advertiser_id,
            owner=owner_text,
            operator_user_id=operator_user_id,
            operator_username=operator_username,
            request_payload=_redact_mapping_payload({"ad_account_id": advertiser_id, "owner": owner_text}),
            result_status=audit_status,
            result_message=audit_message,
        )
        return {
            "code": 200,
            "message": "success",
            "data": {
                "ad_account_id": advertiser_id,
                "owner": owner_text,
                "timezone_sync": tz_result,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建TikTok映射失败: {e}")
        db.log_mapping_audit(
            action="create",
            resource_type="tiktok",
            resource_id=(ad_account_id or "").strip(),
            owner=(owner or "").strip(),
            operator_user_id=operator_user_id,
            operator_username=operator_username,
            request_payload=_redact_mapping_payload({"ad_account_id": ad_account_id, "owner": owner}),
            result_status="error",
            result_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/api/mappings/stores")
async def get_store_mappings() -> Dict[str, Any]:
    """
    获取所有店铺-负责人映射列表
    """
    try:
        mappings = db.get_store_owner_mappings()
        
        # 格式化数据
        formatted_data = []
        for mapping in mappings:
            formatted_item = {
                "id": mapping.get("id"),
                "shop_domain": mapping.get("shop_domain", ""),
                "owner": mapping.get("owner", ""),
                "created_at": mapping.get("created_at").isoformat() if mapping.get("created_at") else None,
                "updated_at": mapping.get("updated_at").isoformat() if mapping.get("updated_at") else None
            }
            formatted_data.append(formatted_item)
        
        return {
            "code": 200,
            "message": "success",
            "data": formatted_data
        }
    except Exception as e:
        logger.error(f"获取店铺映射列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@router.get("/api/mappings/facebook")
async def get_facebook_mappings() -> Dict[str, Any]:
    """
    获取所有Facebook广告账户-负责人映射列表
    """
    try:
        mappings = db.get_ad_account_owner_mappings()
        
        # 格式化数据
        formatted_data = []
        for mapping in mappings:
            formatted_item = {
                "id": mapping.get("id"),
                "ad_account_id": mapping.get("ad_account_id", ""),
                "owner": mapping.get("owner", ""),
                "created_at": mapping.get("created_at").isoformat() if mapping.get("created_at") else None,
                "updated_at": mapping.get("updated_at").isoformat() if mapping.get("updated_at") else None
            }
            formatted_data.append(formatted_item)
        
        return {
            "code": 200,
            "message": "success",
            "data": formatted_data
        }
    except Exception as e:
        logger.error(f"获取Facebook映射列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@router.get("/api/mappings/tiktok")
async def get_tiktok_mappings() -> Dict[str, Any]:
    """
    获取所有TikTok广告账户-负责人映射列表
    """
    try:
        mappings = db.get_tt_ad_account_owner_mappings()
        
        # 格式化数据
        formatted_data = []
        for mapping in mappings:
            formatted_item = {
                "id": mapping.get("id"),
                "ad_account_id": mapping.get("ad_account_id", ""),
                "owner": mapping.get("owner", ""),
                "created_at": mapping.get("created_at").isoformat() if mapping.get("created_at") else None,
                "updated_at": mapping.get("updated_at").isoformat() if mapping.get("updated_at") else None
            }
            formatted_data.append(formatted_item)
        
        return {
            "code": 200,
            "message": "success",
            "data": formatted_data
        }
    except Exception as e:
        logger.error(f"获取TikTok映射列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@router.get("/api/mappings/owners/suggestions")
async def get_mapping_owner_suggestions(
    q: str = Query("", description="模糊匹配子串，空则返回字典序前若干名", max_length=64),
    limit: int = Query(40, ge=1, le=100, description="最多返回条数"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    从 store / FB / TT 三张负责人映射表合并去重，供新增映射时 Autocomplete。
    需具备与 POST 新增映射相同的编辑权限。
    """
    try:
        _check_mapping_edit_permission(current_user)
        owners = db.suggest_mapping_owners(q.strip(), limit)
        return {"code": 200, "message": "success", "data": owners}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"负责人联想查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.put("/api/mappings/stores/{id}")
async def update_store_mapping(
    id: int = Path(..., description="映射ID"),
    owner: str = Body(..., description="负责人名称", embed=True),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    更新店铺-负责人映射
    """
    operator_user_id = current_user.get("id")
    operator_username = current_user.get("username")
    try:
        # 权限检查：普通用户需要can_edit_mappings权限才能编辑映射
        user_role = current_user.get("role", "user")
        if user_role == "user":
            user_id = current_user.get("id")
            if user_id:
                extended_permissions = db.get_user_extended_permissions(user_id)
                can_edit_mappings = extended_permissions.get("can_edit_mappings", False)
                if not can_edit_mappings:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="您没有权限编辑映射"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="您没有权限编辑映射"
                )
        # 先获取映射信息
        mappings = db.get_store_owner_mappings()
        mapping = next((m for m in mappings if m.get("id") == id), None)
        
        if not mapping:
            raise HTTPException(status_code=404, detail="映射不存在")
        
        shop_domain = mapping.get("shop_domain")
        if not shop_domain:
            raise HTTPException(status_code=400, detail="店铺域名不存在")
        
        # 更新映射
        affected_dates = db.update_store_owner_mapping(shop_domain, owner)
        
        if affected_dates is None:
            raise HTTPException(status_code=500, detail="更新映射失败")
        
        # 重新聚合受影响日期的数据
        if affected_dates:
            success = db.aggregate_owner_daily_for_dates(affected_dates)
            if not success:
                logger.warning(f"映射已更新，但重新聚合失败，影响 {len(affected_dates)} 个日期")
                db.log_mapping_audit(
                    action="update",
                    resource_type="store",
                    resource_id=shop_domain,
                    owner=owner,
                    operator_user_id=operator_user_id,
                    operator_username=operator_username,
                    request_payload=_redact_mapping_payload({"id": id, "owner": owner}),
                    result_status="warning",
                    result_message=f"映射更新成功，但重新聚合失败，影响 {len(affected_dates)} 个日期",
                )
            else:
                db.log_mapping_audit(
                    action="update",
                    resource_type="store",
                    resource_id=shop_domain,
                    owner=owner,
                    operator_user_id=operator_user_id,
                    operator_username=operator_username,
                    request_payload=_redact_mapping_payload({"id": id, "owner": owner}),
                    result_status="success",
                    result_message=f"更新成功，影响 {len(affected_dates)} 个日期",
                )
        else:
            db.log_mapping_audit(
                action="update",
                resource_type="store",
                resource_id=shop_domain,
                owner=owner,
                operator_user_id=operator_user_id,
                operator_username=operator_username,
                request_payload=_redact_mapping_payload({"id": id, "owner": owner}),
                result_status="success",
                result_message="更新成功，无历史日期受影响",
            )
        
        return {
            "code": 200,
            "message": "success",
            "data": {
                "id": id,
                "shop_domain": shop_domain,
                "owner": owner,
                "affected_dates_count": len(affected_dates)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新店铺映射失败: {e}")
        db.log_mapping_audit(
            action="update",
            resource_type="store",
            resource_id=str(id),
            owner=owner,
            operator_user_id=operator_user_id,
            operator_username=operator_username,
            request_payload=_redact_mapping_payload({"id": id, "owner": owner}),
            result_status="error",
            result_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.put("/api/mappings/facebook/{id}")
async def update_facebook_mapping(
    id: int = Path(..., description="映射ID"),
    owner: str = Body(..., description="负责人名称", embed=True),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    更新Facebook广告账户-负责人映射
    """
    operator_user_id = current_user.get("id")
    operator_username = current_user.get("username")
    try:
        # 权限检查：普通用户需要can_edit_mappings权限才能编辑映射
        user_role = current_user.get("role", "user")
        if user_role == "user":
            user_id = current_user.get("id")
            if user_id:
                extended_permissions = db.get_user_extended_permissions(user_id)
                can_edit_mappings = extended_permissions.get("can_edit_mappings", False)
                if not can_edit_mappings:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="您没有权限编辑映射"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="您没有权限编辑映射"
                )
        # 先获取映射信息
        mappings = db.get_ad_account_owner_mappings()
        mapping = next((m for m in mappings if m.get("id") == id), None)
        
        if not mapping:
            raise HTTPException(status_code=404, detail="映射不存在")
        
        ad_account_id = mapping.get("ad_account_id")
        if not ad_account_id:
            raise HTTPException(status_code=400, detail="广告账户ID不存在")
        
        # 更新映射
        affected_dates = db.update_ad_account_owner_mapping(ad_account_id, owner)
        
        if affected_dates is None:
            raise HTTPException(status_code=500, detail="更新映射失败")
        
        # 重新聚合受影响日期的数据
        if affected_dates:
            success = db.aggregate_owner_daily_for_dates(affected_dates)
            if not success:
                logger.warning(f"映射已更新，但重新聚合失败，影响 {len(affected_dates)} 个日期")
                db.log_mapping_audit(
                    action="update",
                    resource_type="facebook",
                    resource_id=ad_account_id,
                    owner=owner,
                    operator_user_id=operator_user_id,
                    operator_username=operator_username,
                    request_payload=_redact_mapping_payload({"id": id, "owner": owner, "ad_account_id": ad_account_id}),
                    result_status="warning",
                    result_message=f"映射更新成功，但重新聚合失败，影响 {len(affected_dates)} 个日期",
                )
            else:
                db.log_mapping_audit(
                    action="update",
                    resource_type="facebook",
                    resource_id=ad_account_id,
                    owner=owner,
                    operator_user_id=operator_user_id,
                    operator_username=operator_username,
                    request_payload=_redact_mapping_payload({"id": id, "owner": owner, "ad_account_id": ad_account_id}),
                    result_status="success",
                    result_message=f"更新成功，影响 {len(affected_dates)} 个日期",
                )
        else:
            db.log_mapping_audit(
                action="update",
                resource_type="facebook",
                resource_id=ad_account_id,
                owner=owner,
                operator_user_id=operator_user_id,
                operator_username=operator_username,
                request_payload=_redact_mapping_payload({"id": id, "owner": owner, "ad_account_id": ad_account_id}),
                result_status="success",
                result_message="更新成功，无历史日期受影响",
            )
        
        return {
            "code": 200,
            "message": "success",
            "data": {
                "id": id,
                "ad_account_id": ad_account_id,
                "owner": owner,
                "affected_dates_count": len(affected_dates)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新Facebook映射失败: {e}")
        db.log_mapping_audit(
            action="update",
            resource_type="facebook",
            resource_id=str(id),
            owner=owner,
            operator_user_id=operator_user_id,
            operator_username=operator_username,
            request_payload=_redact_mapping_payload({"id": id, "owner": owner}),
            result_status="error",
            result_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.put("/api/mappings/tiktok/{id}")
async def update_tiktok_mapping(
    id: int = Path(..., description="映射ID"),
    owner: str = Body(..., description="负责人名称", embed=True),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    更新TikTok广告账户-负责人映射
    """
    operator_user_id = current_user.get("id")
    operator_username = current_user.get("username")
    try:
        # 权限检查：普通用户需要can_edit_mappings权限才能编辑映射
        user_role = current_user.get("role", "user")
        if user_role == "user":
            user_id = current_user.get("id")
            if user_id:
                extended_permissions = db.get_user_extended_permissions(user_id)
                can_edit_mappings = extended_permissions.get("can_edit_mappings", False)
                if not can_edit_mappings:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="您没有权限编辑映射"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="您没有权限编辑映射"
                )
        # 先获取映射信息
        mappings = db.get_tt_ad_account_owner_mappings()
        mapping = next((m for m in mappings if m.get("id") == id), None)
        
        if not mapping:
            raise HTTPException(status_code=404, detail="映射不存在")
        
        ad_account_id = mapping.get("ad_account_id")
        if not ad_account_id:
            raise HTTPException(status_code=400, detail="广告账户ID不存在")
        
        # 更新映射
        affected_dates = db.update_tt_ad_account_owner_mapping(ad_account_id, owner)
        
        if affected_dates is None:
            raise HTTPException(status_code=500, detail="更新映射失败")
        
        # 重新聚合受影响日期的数据
        if affected_dates:
            success = db.aggregate_owner_daily_for_dates(affected_dates)
            if not success:
                logger.warning(f"映射已更新，但重新聚合失败，影响 {len(affected_dates)} 个日期")
                db.log_mapping_audit(
                    action="update",
                    resource_type="tiktok",
                    resource_id=ad_account_id,
                    owner=owner,
                    operator_user_id=operator_user_id,
                    operator_username=operator_username,
                    request_payload=_redact_mapping_payload({"id": id, "owner": owner, "ad_account_id": ad_account_id}),
                    result_status="warning",
                    result_message=f"映射更新成功，但重新聚合失败，影响 {len(affected_dates)} 个日期",
                )
            else:
                db.log_mapping_audit(
                    action="update",
                    resource_type="tiktok",
                    resource_id=ad_account_id,
                    owner=owner,
                    operator_user_id=operator_user_id,
                    operator_username=operator_username,
                    request_payload=_redact_mapping_payload({"id": id, "owner": owner, "ad_account_id": ad_account_id}),
                    result_status="success",
                    result_message=f"更新成功，影响 {len(affected_dates)} 个日期",
                )
        else:
            db.log_mapping_audit(
                action="update",
                resource_type="tiktok",
                resource_id=ad_account_id,
                owner=owner,
                operator_user_id=operator_user_id,
                operator_username=operator_username,
                request_payload=_redact_mapping_payload({"id": id, "owner": owner, "ad_account_id": ad_account_id}),
                result_status="success",
                result_message="更新成功，无历史日期受影响",
            )
        
        return {
            "code": 200,
            "message": "success",
            "data": {
                "id": id,
                "ad_account_id": ad_account_id,
                "owner": owner,
                "affected_dates_count": len(affected_dates)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新TikTok映射失败: {e}")
        db.log_mapping_audit(
            action="update",
            resource_type="tiktok",
            resource_id=str(id),
            owner=owner,
            operator_user_id=operator_user_id,
            operator_username=operator_username,
            request_payload=_redact_mapping_payload({"id": id, "owner": owner}),
            result_status="error",
            result_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")

