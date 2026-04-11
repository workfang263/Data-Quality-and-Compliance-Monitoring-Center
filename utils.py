"""
工具函数模块
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional
import pytz

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """密码加密（使用SHA256）"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return hash_password(password) == password_hash


def beijing_time() -> datetime:
    """获取当前北京时间"""
    tz = pytz.timezone('Asia/Shanghai')
    return datetime.now(tz).replace(tzinfo=None)


def datetime_to_timestamp(dt: datetime) -> int:
    """将datetime转换为Unix时间戳（秒）"""
    return int(dt.timestamp())


def timestamp_to_datetime(ts: int) -> datetime:
    """将Unix时间戳转换为datetime（北京时间）"""
    return datetime.fromtimestamp(ts)


def datetime_to_iso8601(dt: datetime) -> str:
    """将datetime转换为ISO 8601格式（北京时间）"""
    return dt.strftime('%Y-%m-%dT%H:%M:%S+08:00')


def parse_iso8601(iso_str: str) -> datetime:
    """解析ISO 8601格式字符串为datetime"""
    # 处理各种ISO 8601格式
    iso_str = iso_str.replace('Z', '+00:00')
    if '+' not in iso_str and '-' not in iso_str[-6:]:
        iso_str += '+08:00'
    
    try:
        return datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    except:
        # 尝试其他格式
        for fmt in ['%Y-%m-%dT%H:%M:%S+08:00', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
            try:
                return datetime.strptime(iso_str, fmt)
            except:
                continue
        raise ValueError(f"无法解析时间格式: {iso_str}")


def get_yesterday_range(extend_hours: int = 0, return_target_date: bool = False) -> tuple:
    """
    获取昨天的时间范围（北京时间）
    
    Args:
        extend_hours: 扩展时间窗口的小时数（方案2：扩大查询范围以抓取边界订单）
                     例如：1 表示查询范围扩展到第二天01:00:00
        return_target_date: 是否返回目标统计日期（用于向后兼容）
    
    Returns:
        如果 return_target_date=True 或 extend_hours > 0:
            (start_time, end_time, actual_end_date)
        Otherwise (向后兼容):
            (start_time, end_time)
        
        - start_time: 查询起始时间（昨天的00:00:00）
        - end_time: 查询结束时间（如果extend_hours>0，扩展到第二天；否则到昨天23:59:59）
        - actual_end_date: 实际统计截止日期（昨天的日期，用于筛选订单时只统计昨天的数据）
    """
    today = beijing_time().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today - timedelta(days=1)
    yesterday_end = today - timedelta(seconds=1)
    target_date = yesterday_end.date()
    
    # 方案2：扩展查询时间窗口
    if extend_hours > 0:
        extended_end = yesterday_end + timedelta(hours=extend_hours)
        return yesterday_start, extended_end, target_date
    
    # 向后兼容：如果没有扩展窗口且不要求返回target_date，只返回2个值
    if return_target_date:
        return yesterday_start, yesterday_end, target_date
    
    return yesterday_start, yesterday_end


def get_hour_range(start_date: datetime, end_date: datetime) -> list:
    """获取日期范围内所有小时的时间段"""
    hours = []
    current = start_date.replace(minute=0, second=0, microsecond=0)
    end = end_date.replace(minute=59, second=59, microsecond=999999)
    
    while current <= end:
        hour_end = current + timedelta(hours=1) - timedelta(seconds=1)
        if hour_end > end:
            hour_end = end
        hours.append((current, hour_end))
        current += timedelta(hours=1)
    
    return hours


def setup_logging(log_file: str = 'logs/app.log', log_level: str = 'INFO'):
    """配置日志（实现见 lib.log_config，此处薄封装以减少全仓库 import 改动）。"""
    from config import LOG_CONFIG
    from lib.log_config import setup_logging as _setup

    _setup(log_file, log_level, LOG_CONFIG)

