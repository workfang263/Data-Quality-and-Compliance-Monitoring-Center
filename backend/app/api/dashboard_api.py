"""
【新系统】FastAPI后端 - 看板数据API接口
提供看板相关的API接口，包括：
- GET /api/dashboard/data - 获取看板数据（折线图数据）
"""
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging

# 导入数据库操作类
from app.services.database_new import Database
from app.api.auth_api import get_current_user

logger = logging.getLogger(__name__)

# 创建路由实例
router = APIRouter()

# 创建数据库实例（单例模式，所有请求共享同一个实例）
db = Database()


@router.get("/api/dashboard/data")
async def get_dashboard_data(
    shop_domain: Optional[str] = Query(None, description="店铺域名，不传或传'ALL_STORES'表示总店铺"),
    start_date: str = Query(..., description="开始日期，格式：YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期，格式：YYYY-MM-DD"),
    granularity: str = Query("hour", description="粒度，可选值：hour（小时）、day（天），默认：hour"),
    start_hour: Optional[int] = Query(None, ge=0, le=23, description="开始小时（0-23），用于日内时段筛选"),
    end_hour: Optional[int] = Query(None, ge=0, le=23, description="结束小时（0-23），用于日内时段筛选"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取看板数据（折线图数据）
    
    参数说明：
    - shop_domain: 店铺域名，不传或传"ALL_STORES"表示总店铺
    - start_date: 开始日期，格式：YYYY-MM-DD
    - end_date: 结束日期，格式：YYYY-MM-DD
    - granularity: 粒度，可选值：hour（小时）、day（天），默认：hour
    - start_hour: 开始小时（0-23），用于日内时段筛选
    - end_hour: 结束小时（0-23），用于日内时段筛选
    
    返回格式：
    {
        "code": 200,
        "message": "success",
        "data": [
            {
                "time_hour": "2025-12-01T00:00:00",
                "total_gmv": 1234.56,
                "total_orders": 10,
                "total_visitors": 100,
                "total_spend": 50.0,
                "avg_order_value": 123.456
            }
        ]
    }
    """
    try:
        # 1. 参数验证
        # 验证日期格式
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="日期格式错误，请使用 YYYY-MM-DD 格式"
            )
        
        # 验证日期范围
        if start_dt > end_dt:
            raise HTTPException(
                status_code=400,
                detail="开始日期不能晚于结束日期"
            )
        
        # 验证粒度
        if granularity not in ["hour", "day"]:
            raise HTTPException(
                status_code=400,
                detail="granularity 参数只能是 'hour' 或 'day'"
            )
        
        # 验证小时范围（如果提供了）
        if start_hour is not None and end_hour is not None:
            if start_hour >= end_hour:
                raise HTTPException(
                    status_code=400,
                    detail="开始小时必须小于结束小时"
                )
        
        # 处理shop_domain：如果为None或"ALL_STORES"，则查询总店铺数据
        is_all_stores = (shop_domain is None or shop_domain == "ALL_STORES" or shop_domain == "")
        
        # 权限检查：普通用户需要can_view_dashboard权限才能查看总数据
        user_role = current_user.get("role", "user")
        allowed_owners = None  # 用于存储授权负责人列表
        
        if user_role == "user" and is_all_stores:
            # 检查用户是否有查看看板总数据的权限
            user_id = current_user.get("id")
            if user_id:
                extended_permissions = db.get_user_extended_permissions(user_id)
                can_view_dashboard = extended_permissions.get("can_view_dashboard", False)
                if not can_view_dashboard:
                    # 没有权限，返回空数据
                    return {
                        "code": 200,
                        "message": "success",
                        "data": []
                    }
                
                # 如果有权限，获取用户的授权负责人列表
                allowed_owners = db.get_user_permissions(user_id)
                if not allowed_owners:
                    # 没有授权任何负责人，返回空数据
                    return {
                        "code": 200,
                        "message": "success",
                        "data": []
                    }
            else:
                # 没有用户ID，返回空数据
                return {
                    "code": 200,
                    "message": "success",
                    "data": []
                }
        
        # 2. 转换为datetime对象（用于数据库查询）
        start_datetime = datetime.combine(start_dt, datetime.min.time())
        end_datetime = datetime.combine(end_dt, datetime.max.time())
        
        # 3. 根据店铺和粒度调用相应的数据库方法
        try:
            if is_all_stores:
                # 查询汇总数据（总店铺）
                # 如果是普通用户且有can_view_dashboard权限，使用过滤后的方法
                if user_role == "user" and allowed_owners is not None:
                    # 普通用户：只查询被授权负责人的数据
                    if granularity == "hour":
                        data = db.get_hourly_data_with_spend_filtered(
                            start_datetime, end_datetime,
                            allowed_owners,
                            start_hour, end_hour
                        )
                    else:  # day
                        data = db.get_daily_data_with_spend_filtered(
                            start_datetime, end_datetime,
                            allowed_owners
                        )
                else:
                    # 管理员：查询所有数据
                    if granularity == "hour":
                        data = db.get_hourly_data_with_spend(
                            start_datetime, end_datetime, 
                            start_hour, end_hour
                        )
                    else:  # day
                        data = db.get_daily_data_with_spend(
                            start_datetime, end_datetime
                        )
            else:
                # 查询单店铺数据
                if granularity == "hour":
                    data = db.get_store_hourly_data(
                        shop_domain,
                        start_datetime, end_datetime,
                        start_hour, end_hour
                    )
                else:  # day
                    data = db.get_store_daily_data(
                        shop_domain,
                        start_datetime, end_datetime,
                        start_hour, end_hour
                    )
        except Exception as db_error:
            # 数据库查询失败，记录错误并返回空数据
            logger.error(f"数据库查询失败: {db_error}", exc_info=True)
            data = []
        
        # 确保 data 是列表类型
        if data is None:
            logger.warning("数据库查询返回 None，使用空数组")
            data = []
        
        # 4. 处理数据：格式化时间、计算avg_order_value等
        # ⚠️ 访客数说明：
        # - 访客数是累计值，同一天内不同小时是递增的（00:00 ≤ 01:00 ≤ ... ≤ 23:00）
        # - 不应该把同一天所有小时设置为相同值，保持数据库中的原始累计值
        # - 计算总访客数时，前端会按天分组取最大值后累加（不同天的访客应该累加）
        
        result_data = []
        
        if granularity == "hour":
            # 小时粒度：处理time_hour字段
            for row in data:
                try:
                    time_hour = row.get('time_hour')
                    
                    # 确保time_hour是datetime对象
                    if time_hour is None:
                        logger.warning(f"数据行缺少 time_hour 字段，跳过: {row}")
                        continue
                    
                    if isinstance(time_hour, str):
                        try:
                            time_hour = datetime.strptime(time_hour, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            # 尝试其他格式
                            try:
                                time_hour = datetime.fromisoformat(time_hour.replace('Z', '+00:00'))
                            except ValueError:
                                logger.warning(f"无法解析 time_hour 字符串: {time_hour}")
                                continue
                    elif isinstance(time_hour, date) and not isinstance(time_hour, datetime):
                        time_hour = datetime.combine(time_hour, datetime.min.time())
                    elif not isinstance(time_hour, datetime):
                        logger.warning(f"time_hour 类型不正确: {type(time_hour)}, 值: {time_hour}")
                        continue
                    
                    # 计算avg_order_value（如果数据库没有计算）
                    total_gmv = float(row.get('total_gmv', 0) or 0)
                    total_orders = int(row.get('total_orders', 0) or 0)
                    avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
                    
                    # 获取total_spend（如果数据库没有，默认为0）
                    total_spend = float(row.get('total_spend', 0) or 0)
                    
                    result_data.append({
                        "time_hour": time_hour.isoformat(),  # ISO 8601格式
                        "total_gmv": total_gmv,
                        "total_orders": total_orders,
                        "total_visitors": int(row.get('total_visitors', 0) or 0),
                        "total_spend": total_spend,
                        "avg_order_value": round(avg_order_value, 2)
                    })
                except Exception as row_error:
                    logger.error(f"处理数据行时出错: {row_error}, 数据行: {row}", exc_info=True)
                    # 跳过有问题的数据行，继续处理其他行
                    continue
        else:
            # 天粒度：处理date字段
            for row in data:
                try:
                    date_value = row.get('date')
                    
                    if date_value is None:
                        logger.warning(f"数据行缺少 date 字段，跳过: {row}")
                        continue
                    
                    # 确保date是date对象
                    if isinstance(date_value, str):
                        try:
                            date_value = datetime.strptime(date_value, "%Y-%m-%d").date()
                        except ValueError:
                            logger.warning(f"无法解析 date 字符串: {date_value}")
                            continue
                    elif isinstance(date_value, datetime):
                        date_value = date_value.date()
                    elif not isinstance(date_value, date):
                        logger.warning(f"date 类型不正确: {type(date_value)}, 值: {date_value}")
                        continue
                    
                    # 计算avg_order_value（天粒度需要重新计算：总销售额 / 总订单数）
                    total_gmv = float(row.get('total_gmv', 0) or 0)
                    total_orders = int(row.get('total_orders', 0) or 0)
                    avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
                    
                    # 获取total_spend（如果数据库没有，默认为0）
                    total_spend = float(row.get('total_spend', 0) or 0)
                    
                    # 天粒度也使用time_hour字段名（保持API返回格式一致）
                    # 将date转换为datetime（使用当天的00:00:00）
                    time_hour = datetime.combine(date_value, datetime.min.time())
                    
                    result_data.append({
                        "time_hour": time_hour.isoformat(),  # ISO 8601格式
                        "total_gmv": total_gmv,
                        "total_orders": total_orders,
                        "total_visitors": int(row.get('total_visitors', 0) or 0),
                        "total_spend": total_spend,
                        "avg_order_value": round(avg_order_value, 2)
                    })
                except Exception as row_error:
                    logger.error(f"处理数据行时出错: {row_error}, 数据行: {row}", exc_info=True)
                    # 跳过有问题的数据行，继续处理其他行
                    continue
        
        # 5. 返回统一格式的响应
        return {
            "code": 200,
            "message": "success",
            "data": result_data
        }
        
    except HTTPException:
        # 重新抛出HTTP异常（参数验证错误等）
        raise
    except Exception as e:
        # 捕获其他异常，返回500错误
        logger.error(f"获取看板数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"服务器内部错误: {str(e)}"
        )

