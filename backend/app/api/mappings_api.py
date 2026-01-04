"""
【新系统】FastAPI后端 - 映射编辑API接口
提供映射相关的API接口，包括：
- GET /api/mappings/stores - 获取店铺映射列表
- GET /api/mappings/facebook - 获取Facebook广告账户映射列表
- GET /api/mappings/tiktok - 获取TikTok广告账户映射列表
- PUT /api/mappings/stores/{id} - 更新店铺映射
- PUT /api/mappings/facebook/{id} - 更新Facebook映射
- PUT /api/mappings/tiktok/{id} - 更新TikTok映射
"""
from fastapi import APIRouter, Path, HTTPException, Body, Depends, status
from typing import List, Dict, Any, Optional
from datetime import date
import logging

from app.services.database_new import Database
from app.api.auth_api import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()
db = Database()


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


@router.put("/api/mappings/stores/{id}")
async def update_store_mapping(
    id: int = Path(..., description="映射ID"),
    owner: str = Body(..., description="负责人名称", embed=True),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    更新店铺-负责人映射
    """
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
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")

