"""
订单 placed_at → 北京时间日历日 biz_date。
分支逻辑与 data_sync._get_order_beijing_time 一致（仅用 placed_at）。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
_SH = ZoneInfo("Asia/Shanghai")


def placed_at_to_beijing_naive_datetime(time_str: str) -> Optional[datetime]:
    """
    将 API 返回的 ISO 时间转为「 naive 北京时间 datetime」。
    """
    if not time_str or not isinstance(time_str, str):
        return None
    time_str = time_str.strip()
    try:
        if "Z" in time_str:
            order_dt_utc = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            order_dt = order_dt_utc.astimezone(_SH).replace(tzinfo=None)
        elif "+00:00" in time_str:
            order_dt_utc = datetime.fromisoformat(time_str)
            order_dt = order_dt_utc.astimezone(_SH).replace(tzinfo=None)
        elif "+08:00" in time_str:
            order_dt = datetime.fromisoformat(time_str).replace(tzinfo=None)
        else:
            order_dt = datetime.fromisoformat(time_str)
            if order_dt.tzinfo is not None:
                order_dt = order_dt.astimezone(_SH).replace(tzinfo=None)
            else:
                order_dt = order_dt + timedelta(hours=8)
        if order_dt.tzinfo is not None:
            order_dt = order_dt.replace(tzinfo=None)
        return order_dt
    except Exception as e:
        logger.warning(f"placed_at 解析失败: {time_str!r} err={e}")
        return None


def order_to_biz_date(order: Dict[str, Any]) -> Optional[date]:
    """从订单对象取 placed_at，得到北京日历日。"""
    ts = order.get("placed_at")
    if not ts:
        return None
    naive = placed_at_to_beijing_naive_datetime(ts)
    if not naive:
        return None
    return naive.date()
