"""
【新系统】FastAPI后端 - 负责人汇总API接口
提供负责人相关的API接口，包括：
- GET /api/owners/summary - 获取负责人汇总数据（表格数据）
- GET /api/owners/{owner}/hourly - 获取负责人的小时趋势数据（用于弹窗图表）
"""
from fastapi import APIRouter, Query, Path, HTTPException, Depends, status
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging

from app.services.database_new import Database
from app.api.auth_api import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()
db = Database()


@router.get("/api/owners/summary")
async def get_owners_summary(
    start_date: str = Query(..., description="开始日期，格式：YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期，格式：YYYY-MM-DD"),
    sort_by: Optional[str] = Query("owner", description="排序字段，可选值：owner、gmv、orders、visitors、aov、spend、roas"),
    sort_order: Optional[str] = Query("asc", description="排序方向，可选值：asc、desc"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取负责人汇总数据（表格数据）
    """
    try:
        # 验证日期格式
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        if start > end:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        
        # 验证排序参数
        valid_sort_fields = ['owner', 'gmv', 'orders', 'visitors', 'aov', 'spend', 'roas']
        if sort_by not in valid_sort_fields:
            raise HTTPException(status_code=400, detail=f"排序字段必须是以下之一：{', '.join(valid_sort_fields)}")
        
        if sort_order not in ['asc', 'desc']:
            raise HTTPException(status_code=400, detail="排序方向必须是 'asc' 或 'desc'")
        
        # 获取数据
        data = db.get_owner_daily_summary(start, end, sort_by, sort_order)
        
        # 权限过滤：普通用户只能查看被授权的负责人
        user_role = current_user.get("role", "user")
        if user_role == "user":
            # 获取用户的授权负责人列表
            user_id = current_user.get("id")
            allowed_owners = db.get_user_permissions(user_id)
            # 只保留被授权的负责人数据
            data = [item for item in data if item.get("owner") in allowed_owners]
        
        # 格式化数据（确保所有字段都存在）
        formatted_data = []
        for item in data:
            formatted_item = {
                "owner": item.get("owner", ""),
                "total_gmv": float(item.get("total_gmv", 0)),
                "total_orders": int(item.get("total_orders", 0)),
                "total_visitors": int(item.get("total_visitors", 0)),
                "avg_order_value": float(item.get("avg_order_value", 0)),
                "total_spend": float(item.get("total_spend", 0)),  # Facebook广告花费
                "tt_total_spend": float(item.get("tt_total_spend", 0)),  # TikTok广告花费
                "total_spend_all": float(item.get("total_spend_all", 0)),  # 总广告花费
                "roas": float(item.get("roas", 0)) if item.get("roas") is not None else None,
                "conversion_rate": float(item.get("conversion_rate", 0))
            }
            formatted_data.append(formatted_item)
        
        return {
            "code": 200,
            "message": "success",
            "data": formatted_data
        }
    except ValueError as e:
        logger.error(f"日期格式错误: {e}")
        raise HTTPException(status_code=400, detail=f"日期格式错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取负责人汇总数据失败: {e}", exc_info=True)
        # 返回更详细的错误信息，方便调试
        error_detail = str(e)
        if hasattr(e, '__cause__') and e.__cause__:
            error_detail += f" | 原因: {str(e.__cause__)}"
        raise HTTPException(status_code=500, detail=f"获取数据失败: {error_detail}")


@router.get("/api/owners/{owner}/hourly")
async def get_owner_hourly(
    owner: str = Path(..., description="负责人名称"),
    start_date: str = Query(..., description="开始日期，格式：YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期，格式：YYYY-MM-DD"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取负责人的小时趋势数据（用于弹窗图表）
    """
    try:
        # 验证日期格式
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        # 结束日期设置为当天的23:59:59
        end = end.replace(hour=23, minute=59, second=59)
        
        if start > end:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        
        # 限制查询范围最多7天
        if (end - start).days > 7:
            raise HTTPException(status_code=400, detail="查询范围不能超过7天")
        
        # 权限检查：普通用户只能查看被授权的负责人
        user_role = current_user.get("role", "user")
        if user_role == "user":
            # 获取用户的授权负责人列表
            user_id = current_user.get("id")
            allowed_owners = db.get_user_permissions(user_id)
            # 验证该负责人是否在授权列表中
            if owner not in allowed_owners:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="您没有权限查看该负责人的数据"
                )
        
        # 获取数据
        data = db.get_owner_hourly_data(owner, start, end)
        
        # 格式化数据
        formatted_data = []
        for item in data:
            formatted_item = {
                "time_hour": item.get("time_hour").isoformat() if isinstance(item.get("time_hour"), datetime) else item.get("time_hour"),
                "total_gmv": float(item.get("total_gmv", 0)),
                "total_orders": int(item.get("total_orders", 0)),
                "total_visitors": int(item.get("total_visitors", 0)),
                "total_spend": float(item.get("total_spend", 0)),  # Facebook广告花费
                "tt_total_spend": float(item.get("tt_total_spend", 0)),  # TikTok广告花费
                "total_spend_all": float(item.get("total_spend_all", 0)),  # 总广告花费
                "avg_order_value": float(item.get("avg_order_value", 0)),
                "roas": float(item.get("roas", 0)) if item.get("roas") is not None else None,
                "conversion_rate": float(item.get("conversion_rate", 0))
            }
            formatted_data.append(formatted_item)
        
        return {
            "code": 200,
            "message": "success",
            "data": formatted_data
        }
    except ValueError as e:
        logger.error(f"日期格式错误: {e}")
        raise HTTPException(status_code=400, detail=f"日期格式错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取负责人小时数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")

