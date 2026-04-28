"""
【新系统】FastAPI后端 - 权限管理API接口
提供用户权限管理相关API接口（仅管理员可访问）
"""
from fastapi import APIRouter, HTTPException, Depends, status, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from app.services.database_new import Database
from app.api.auth_api import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# 延迟初始化 Database
db: Optional[Database] = None

def get_db():
    """获取数据库实例（单例模式）"""
    global db
    if db is None:
        db = Database()
    return db


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    验证当前用户是否为管理员（依赖注入）
    
    Args:
        current_user: 当前用户信息
    
    Returns:
        用户信息
    
    Raises:
        HTTPException: 如果不是管理员，返回403错误
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以访问此功能"
        )
    return current_user


# 请求模型
class UpdatePermissionsRequest(BaseModel):
    owners: List[str]  # 负责人名称列表
    can_view_dashboard: bool = False  # 是否可以查看看板总数据
    can_edit_mappings: bool = False  # 是否可以编辑映射
    can_view_store_ops: bool = False  # 是否可查看店铺运营/员工归因
    can_edit_store_ops_config: bool = False  # 是否可编辑店铺运营子系统配置（新）


@router.get("/api/permissions/users")
async def get_users(
    current_user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """
    获取所有用户列表（仅管理员）
    """
    try:
        users = get_db().get_all_users()
        return {
            "code": 200,
            "message": "success",
            "data": users
        }
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户列表失败: {str(e)}"
        )


@router.get("/api/permissions/owners")
async def get_owners(
    current_user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """
    获取所有负责人列表（仅管理员）
    """
    try:
        owners = get_db().get_all_owners()
        return {
            "code": 200,
            "message": "success",
            "data": owners
        }
    except Exception as e:
        logger.error(f"获取负责人列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取负责人列表失败: {str(e)}"
        )


@router.get("/api/permissions/users/{user_id}/owners")
async def get_user_permissions(
    user_id: int,
    current_user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """
    获取指定用户的授权列表（仅管理员）
    """
    try:
        # 验证用户是否存在
        users = get_db().get_all_users()
        user_exists = any(u["id"] == user_id for u in users)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        owners = get_db().get_user_permissions(user_id)
        return {
            "code": 200,
            "message": "success",
            "data": owners
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户权限失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户权限失败: {str(e)}"
        )


@router.get("/api/permissions/users/{user_id}/extended")
async def get_user_extended_permissions(
    user_id: int,
    current_user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """
    获取指定用户的扩展权限（仅管理员）
    """
    try:
        # 验证用户是否存在
        users = get_db().get_all_users()
        user_exists = any(u["id"] == user_id for u in users)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        permissions = get_db().get_user_extended_permissions(user_id)
        return {
            "code": 200,
            "message": "success",
            "data": permissions
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户扩展权限失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户扩展权限失败: {str(e)}"
        )


@router.put("/api/permissions/users/{user_id}/owners")
async def update_user_permissions(
    user_id: int,
    request_data: UpdatePermissionsRequest = Body(...),
    current_user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """
    更新指定用户的权限（仅管理员）
    
    请求体：
    {
        "owners": ["负责人1", "负责人2", "负责人3"]
    }
    """
    try:
        # 验证用户是否存在
        users = get_db().get_all_users()
        user_exists = any(u["id"] == user_id for u in users)
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 验证不能修改管理员权限
        target_user = next((u for u in users if u["id"] == user_id), None)
        if target_user and target_user.get("role") == "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能修改管理员的权限"
            )
        
        # 更新负责人权限
        success = get_db().update_user_permissions(user_id, request_data.owners)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新负责人权限失败"
            )
        
        # 更新扩展权限
        success = get_db().update_user_extended_permissions(
            user_id,
            request_data.can_view_dashboard,
            request_data.can_edit_mappings,
            request_data.can_view_store_ops,
            request_data.can_edit_store_ops_config,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新扩展权限失败"
            )
        
        return {
            "code": 200,
            "message": "权限更新成功",
            "data": None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新用户权限失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新用户权限失败: {str(e)}"
        )

