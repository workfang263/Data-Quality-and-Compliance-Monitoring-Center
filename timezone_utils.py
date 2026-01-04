"""
时区工具函数
用于处理 Facebook 和 TikTok 广告账户的时区转换

时区配置优先级：
1. 账户级别配置（最高优先级）- ad_account_timezone_mapping / tt_ad_account_timezone_mapping
2. 负责人级别配置（中等优先级）- owner_timezone_mapping
3. 默认配置（最低优先级）- UTC+8
"""
import pymysql
from typing import Optional, Dict
from datetime import datetime, timedelta
from config import DB_CONFIG


def get_db_conn():
    """获取数据库连接"""
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_timezone_config(conn, ad_account_id: str, owner: Optional[str] = None, 
                       platform: str = "facebook") -> Dict[str, float]:
    """
    获取广告账户的时区配置
    
    参数:
        conn: 数据库连接
        ad_account_id: 广告账户ID
        owner: 负责人名称（可选，用于回退到负责人级别配置）
        platform: 平台类型，"facebook" 或 "tiktok"
    
    返回:
        {
            "timezone": "Asia/Shanghai" 或 "America/Los_Angeles",
            "timezone_offset": 8.0 或 -8.0
        }
        默认返回 UTC+8（北京时间）
    """
    # 1. 优先查询账户级别配置
    if platform == "facebook":
        table_name = "ad_account_timezone_mapping"
    elif platform == "tiktok":
        table_name = "tt_ad_account_timezone_mapping"
    else:
        raise ValueError(f"不支持的平台类型: {platform}")
    
    with conn.cursor() as cur:
        # 查询账户级别配置
        cur.execute(
            f"SELECT timezone, timezone_offset FROM {table_name} WHERE ad_account_id = %s",
            (ad_account_id,)
        )
        account_config = cur.fetchone()
        if account_config:
            return {
                "timezone": account_config["timezone"],
                "timezone_offset": float(account_config["timezone_offset"])
            }
        
        # 2. 如果没有账户级别配置，查询负责人级别配置
        if owner:
            cur.execute(
                "SELECT timezone, timezone_offset FROM owner_timezone_mapping WHERE owner = %s",
                (owner,)
            )
            owner_config = cur.fetchone()
            if owner_config:
                return {
                    "timezone": owner_config["timezone"],
                    "timezone_offset": float(owner_config["timezone_offset"])
                }
    
    # 3. 默认返回 UTC+8（北京时间）
    return {
        "timezone": "Asia/Shanghai",
        "timezone_offset": 8.0
    }


def convert_to_beijing_time(dt: datetime, source_timezone_offset: float) -> datetime:
    """
    将源时区时间转换为北京时间（UTC+8）
    
    参数:
        dt: 源时区的 datetime 对象（无时区信息，naive datetime）
        source_timezone_offset: 源时区偏移量（小时），例如 8.0 表示 UTC+8, -8.0 表示 UTC-8
    
    返回:
        转换后的北京时间（无时区信息，naive datetime）
    
    转换公式:
        hours_to_add = 8.0 - source_timezone_offset
        例如：UTC-8 → UTC+8：8.0 - (-8.0) = 16.0 小时
        例如：UTC+8 → UTC+8：8.0 - 8.0 = 0.0 小时（不需要转换）
    """
    # 计算需要添加的小时数
    hours_to_add = 8.0 - source_timezone_offset
    
    # 如果不需要转换（已经是UTC+8），直接返回
    if hours_to_add == 0.0:
        return dt
    
    # 转换为北京时间
    beijing_dt = dt + timedelta(hours=hours_to_add)
    return beijing_dt


def get_timezone_config_for_account(ad_account_id: str, owner: Optional[str] = None,
                                    platform: str = "facebook") -> Dict[str, float]:
    """
    便捷函数：获取账户时区配置（自动创建和关闭数据库连接）
    
    参数:
        ad_account_id: 广告账户ID
        owner: 负责人名称（可选）
        platform: 平台类型，"facebook" 或 "tiktok"
    
    返回:
        {
            "timezone": "Asia/Shanghai" 或 "America/Los_Angeles",
            "timezone_offset": 8.0 或 -8.0
        }
    """
    conn = get_db_conn()
    try:
        return get_timezone_config(conn, ad_account_id, owner, platform)
    finally:
        conn.close()




