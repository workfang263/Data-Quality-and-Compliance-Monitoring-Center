"""
【新系统】FastAPI后端 - 数据库连接和操作模块
从根目录 database.py 复制而来，完全独立，不影响旧系统
"""
import pymysql
import logging
import sys
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal
from collections import defaultdict

# 修改导入路径：从 backend/config_new 导入
# database_new.py 在 backend/app/services/ 目录下
# config_new.py 在 backend/ 目录下
# 向上两级到项目根目录，然后添加backend目录到路径，导入config_new
backend_dir = os.path.join(os.path.dirname(__file__), '../..')
sys.path.insert(0, backend_dir)
from config_new import DB_CONFIG

logger = logging.getLogger(__name__)


class Database:
    """数据库操作类"""
    
    def __init__(self):
        self.config = DB_CONFIG
    
    def get_connection(self):
        """获取数据库连接"""
        try:
            connection = pymysql.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset=self.config['charset'],
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                connect_timeout=10,  # 连接超时（10秒）
                read_timeout=30,      # 读取超时（30秒）
                write_timeout=30      # 写入超时（30秒）
            )
            return connection
        except pymysql.Error as e:
            logger.error(f"数据库连接失败: {e}", exc_info=True)
            logger.error(f"连接配置: host={self.config['host']}, port={self.config['port']}, database={self.config['database']}")
            raise
        except Exception as e:
            logger.error(f"数据库连接异常: {e}", exc_info=True)
            raise
    
    def get_active_stores(self) -> List[Dict[str, Any]]:
        """获取所有启用的店铺列表"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT id, shop_domain, access_token, is_active
                        FROM shoplazza_stores
                        WHERE is_active = TRUE
                        ORDER BY id
                    """
                    cursor.execute(sql)
                    stores = cursor.fetchall()
                    logger.info(f"获取到 {len(stores)} 个启用店铺")
                    return stores
        except Exception as e:
            logger.error(f"获取店铺列表失败: {e}")
            return []
    
    def get_all_stores(self) -> List[Dict[str, Any]]:
        """获取所有店铺列表（包括禁用的店铺）"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT id, shop_domain, access_token, is_active
                        FROM shoplazza_stores
                        ORDER BY id
                    """
                    cursor.execute(sql)
                    stores = cursor.fetchall()
                    logger.info(f"获取到 {len(stores)} 个店铺（包括禁用的店铺）")
                    return stores
        except Exception as e:
            logger.error(f"获取所有店铺列表失败: {e}")
            return []

    def get_store_access_token(self, shop_domain: str) -> str:
        """按店铺域名读取主系统 access_token。"""
        normalized_shop = (shop_domain or "").strip()
        if not normalized_shop:
            return ""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT access_token
                        FROM shoplazza_stores
                        WHERE shop_domain = %s
                        LIMIT 1
                        """,
                        (normalized_shop,),
                    )
                    row = cursor.fetchone() or {}
                    return str(row.get("access_token") or "").strip()
        except Exception as e:
            logger.error(
                "get_store_access_token 失败 shop=%s: %s",
                normalized_shop,
                e,
                exc_info=True,
            )
            return ""
    
    def disable_store(self, shop_domain: str, reason: str = None) -> bool:
        """
        禁用指定店铺
        
        Args:
            shop_domain: 店铺域名
            reason: 禁用原因（可选）
        
        Returns:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 检查店铺是否存在且已启用
                    check_sql = """
                        SELECT id, shop_domain, is_active
                        FROM shoplazza_stores
                        WHERE shop_domain = %s
                    """
                    cursor.execute(check_sql, (shop_domain,))
                    store = cursor.fetchone()
                    
                    if not store:
                        logger.warning(f"店铺 {shop_domain} 不存在，无法禁用")
                        return False
                    
                    if not store['is_active']:
                        logger.info(f"店铺 {shop_domain} 已经是禁用状态")
                        return True
                    
                    # 禁用店铺
                    update_sql = """
                        UPDATE shoplazza_stores
                        SET is_active = FALSE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE shop_domain = %s
                    """
                    cursor.execute(update_sql, (shop_domain,))
                    conn.commit()
                    
                    reason_msg = f"，原因：{reason}" if reason else ""
                    logger.warning(f"🔴 已自动禁用店铺: {shop_domain}{reason_msg}")
                    return True
                    
        except Exception as e:
            logger.error(f"禁用店铺失败 {shop_domain}: {e}")
            return False
    
    def insert_or_update_hourly_data(self, time_hour: datetime, total_gmv: float, 
                                     total_orders: int, total_visitors: int, 
                                     avg_order_value: float) -> bool:
        """插入或更新小时数据（增量更新）"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO shoplazza_overview_hourly 
                        (time_hour, total_gmv, total_orders, total_visitors, avg_order_value)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            total_gmv = VALUES(total_gmv),
                            total_orders = VALUES(total_orders),
                            total_visitors = VALUES(total_visitors),
                            avg_order_value = VALUES(avg_order_value),
                            updated_at = CURRENT_TIMESTAMP
                    """
                    cursor.execute(sql, (time_hour, total_gmv, total_orders, 
                                       total_visitors, avg_order_value))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"插入/更新小时数据失败: {e}")
            return False
    
    def get_hourly_data(self, start_time: datetime, end_time: datetime, 
                       start_hour: Optional[int] = None, 
                       end_hour: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取小时数据"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 构建查询条件
                    conditions = ["time_hour >= %s", "time_hour <= %s"]
                    params = [start_time, end_time]
                    
                    # 如果有日内时段筛选
                    if start_hour is not None and end_hour is not None:
                        conditions.append("HOUR(time_hour) >= %s")
                        conditions.append("HOUR(time_hour) < %s")
                        params.extend([start_hour, end_hour])
                    
                    sql = f"""
                        SELECT time_hour, total_gmv, total_orders, total_visitors, avg_order_value
                        FROM shoplazza_overview_hourly
                        WHERE {' AND '.join(conditions)}
                        ORDER BY time_hour ASC
                    """
                    cursor.execute(sql, params)
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取小时数据失败: {e}")
            return []

    def get_hourly_data_with_spend(self, start_time: datetime, end_time: datetime,
                                   start_hour: Optional[int] = None,
                                   end_hour: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取小时数据（聚合销售+花费），用于总店铺视图
        数据来源：
          - 销售：shoplazza_overview_hourly 按小时汇总
          - Facebook花费：fb_ad_account_spend_hourly 按小时汇总
          - TikTok花费：tt_ad_account_spend_hourly 按小时汇总
        ⚠️ 完全对齐旧系统逻辑，使用 shoplazza_overview_hourly 汇总表，不加映射表过滤
        
        ⚠️ 访客数说明：
          - 访客数是累计值（00:00:00到当前小时的累计值），同一天内不同小时是递增的
          - 使用MAX而不是SUM，因为访客数是累计值，不应该累加
          - 前端计算总访客数时会按天分组取最大值（即当天的总访客数），然后累加所有天
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 条件
                    conditions_sales = ["time_hour >= %s", "time_hour <= %s"]
                    conditions_spend = ["time_hour >= %s", "time_hour <= %s"]
                    params_sales = [start_time, end_time]
                    params_spend = [start_time, end_time]

                    if start_hour is not None and end_hour is not None:
                        conditions_sales.append("HOUR(time_hour) >= %s")
                        conditions_sales.append("HOUR(time_hour) < %s")
                        params_sales.extend([start_hour, end_hour])
                        conditions_spend.append("HOUR(time_hour) >= %s")
                        conditions_spend.append("HOUR(time_hour) < %s")
                        params_spend.extend([start_hour, end_hour])

                    # 小时聚合后再合并
                    # MySQL 无 FULL JOIN，这里用 UNION 后再聚合
                    # ⚠️ 完全对齐旧系统：使用 shoplazza_overview_hourly 汇总表，不加映射表过滤
                    # 参数顺序说明：
                    # 1. params_sales - 用于 shoplazza_overview_hourly 表的 WHERE 条件
                    # 2. params_spend - 用于 fb_ad_account_spend_hourly 表的 WHERE 条件
                    # 3. params_spend - 用于 tt_ad_account_spend_hourly 表的 WHERE 条件
                    # ⚠️ 访客数使用MAX而不是SUM：
                    # - 内层查询：同一个time_hour可能有多条记录（来自不同店铺），取MAX（累计值，最大值就是最新的累计值）
                    # - 外层查询：UNION ALL合并后，同一个time_hour最多只有一条记录有非零访客数（来自销售表），其他都是0，使用MAX确保取到正确的值
                    sql = f"""
                        SELECT 
                            t.time_hour,
                            SUM(t.total_gmv)      AS total_gmv,
                            SUM(t.total_orders)   AS total_orders,
                            MAX(t.total_visitors) AS total_visitors,
                            SUM(t.total_spend)    AS total_spend
                        FROM (
                            SELECT time_hour,
                                   SUM(total_gmv) AS total_gmv,
                                   SUM(total_orders) AS total_orders,
                                   MAX(total_visitors) AS total_visitors,
                                   0 AS total_spend
                            FROM shoplazza_overview_hourly
                            WHERE {' AND '.join(conditions_sales)}
                            GROUP BY time_hour
                            UNION ALL
                            SELECT time_hour,
                                   0 AS total_gmv,
                                   0 AS total_orders,
                                   0 AS total_visitors,
                                   SUM(spend) AS total_spend
                            FROM fb_ad_account_spend_hourly
                            WHERE {' AND '.join(conditions_spend)}
                            GROUP BY time_hour
                            UNION ALL
                            SELECT time_hour,
                                   0 AS total_gmv,
                                   0 AS total_orders,
                                   0 AS total_visitors,
                                   SUM(spend) AS total_spend
                            FROM tt_ad_account_spend_hourly
                            WHERE {' AND '.join(conditions_spend)}
                            GROUP BY time_hour
                        ) t
                        GROUP BY t.time_hour
                        ORDER BY t.time_hour ASC
                    """
                    # 参数顺序：销售表参数 + Facebook花费表参数 + TikTok花费表参数
                    all_params = params_sales + params_spend + params_spend
                    cursor.execute(sql, all_params)
                    result = cursor.fetchall()
                    logger.debug(f"获取带花费的小时数据成功，返回 {len(result)} 条记录（对齐旧系统逻辑）")
                    return result
        except Exception as e:
            logger.error(f"获取带花费的小时数据失败: {e}", exc_info=True)
            logger.error(f"SQL查询参数: start_time={start_time}, end_time={end_time}, start_hour={start_hour}, end_hour={end_hour}")
            # 与旧系统保持一致：返回空数组而不是抛出异常
            return []
    
    def get_data_date_range(self, shop_domain: Optional[str] = None) -> Optional[Tuple[datetime, datetime]]:
        """
        获取数据库中数据的日期范围（最早和最晚的日期）
        
        Args:
            shop_domain: 店铺域名，如果为None则查询汇总数据，否则查询单店铺数据
        
        Returns:
            (最早日期, 最晚日期) 元组，如果不存在则返回None
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    if shop_domain:
                        # 查询单店铺数据日期范围
                        sql = """
                            SELECT 
                                MIN(time_hour) as earliest_date,
                                MAX(time_hour) as latest_date
                            FROM shoplazza_store_hourly
                            WHERE shop_domain = %s
                        """
                        cursor.execute(sql, (shop_domain,))
                    else:
                        # 查询汇总数据日期范围
                        sql = """
                            SELECT 
                                MIN(time_hour) as earliest_date,
                                MAX(time_hour) as latest_date
                            FROM shoplazza_overview_hourly
                        """
                        cursor.execute(sql)
                    result = cursor.fetchone()
                    if result and result.get('earliest_date') and result.get('latest_date'):
                        return (result['earliest_date'], result['latest_date'])
                    return None
        except Exception as e:
            logger.error(f"获取数据日期范围失败 {shop_domain or '汇总数据'}: {e}")
            return None
    
    def get_daily_data(self, start_time: datetime, end_time: datetime,
                      start_hour: Optional[int] = None,
                      end_hour: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取按天聚合的数据"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    conditions = ["DATE(time_hour) >= DATE(%s)", "DATE(time_hour) <= DATE(%s)"]
                    params = [start_time, end_time]
                    
                    if start_hour is not None and end_hour is not None:
                        conditions.append("HOUR(time_hour) >= %s")
                        conditions.append("HOUR(time_hour) < %s")
                        params.extend([start_hour, end_hour])
                    
                    sql = f"""
                        SELECT 
                            DATE(time_hour) as date,
                            SUM(total_gmv) as total_gmv,
                            SUM(total_orders) as total_orders,
                            MAX(total_visitors) as total_visitors,
                            -- 不在这里计算客单价，在dashboard.py中重新计算（总销售额 / 总订单数）
                            0 as avg_order_value
                        FROM shoplazza_overview_hourly
                        WHERE {' AND '.join(conditions)}
                        GROUP BY DATE(time_hour)
                        ORDER BY date ASC
                    """
                    cursor.execute(sql, params)
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取天数据失败: {e}")
            return []

    def get_daily_data_with_spend(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        获取按天聚合的数据（销售+花费），用于总店铺视图。
        数据来源：owner_daily_summary（按天、按负责人聚合的日汇总）。
        返回 total_spend 为总广告花费（Facebook + TikTok）
        ⚠️ 完全对齐旧系统逻辑，不加映射表过滤
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 先尝试使用包含 tt_total_spend 的完整SQL（对齐旧系统）
                    sql_with_tt = """
                        SELECT 
                            date,
                            SUM(total_gmv)      AS total_gmv,
                            SUM(total_orders)   AS total_orders,
                            SUM(total_visitors) AS total_visitors,
                            SUM(total_spend + tt_total_spend) AS total_spend
                        FROM owner_daily_summary
                        WHERE date >= DATE(%s) AND date <= DATE(%s)
                        GROUP BY date
                        ORDER BY date ASC
                    """
                    try:
                        cursor.execute(sql_with_tt, (start_time, end_time))
                        return cursor.fetchall()
                    except Exception as sql_error:
                        # 如果SQL执行失败，检查是否是字段不存在的问题
                        error_msg = str(sql_error).lower()
                        if 'tt_total_spend' in error_msg or 'unknown column' in error_msg:
                            # 字段不存在，使用简化SQL（不包含 tt_total_spend）
                            logger.warning(f"表缺少 tt_total_spend 字段，使用简化SQL: {sql_error}")
                            sql_without_tt = """
                                SELECT 
                                    date,
                                    SUM(total_gmv)      AS total_gmv,
                                    SUM(total_orders)   AS total_orders,
                                    SUM(total_visitors) AS total_visitors,
                                    SUM(total_spend)    AS total_spend
                                FROM owner_daily_summary
                                WHERE date >= DATE(%s) AND date <= DATE(%s)
                                GROUP BY date
                                ORDER BY date ASC
                            """
                            cursor.execute(sql_without_tt, (start_time, end_time))
                            return cursor.fetchall()
                        else:
                            # 其他错误，重新抛出
                            raise
        except Exception as e:
            logger.error(f"获取带花费的天数据失败: {e}", exc_info=True)
            # 与旧系统保持一致：返回空数组而不是抛出异常
            return []
    
    def get_hourly_data_with_spend_filtered(
        self, 
        start_time: datetime, 
        end_time: datetime,
        allowed_owners: List[str],
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取小时粒度数据（按授权负责人过滤）
        
        ⚠️ 访客数计算逻辑：
        - 访客数是按天去重的累计值，同一天内不同小时是递增的
        - 不同店铺的访客是不同的IP，应该累加
        - 先按 owner, shop_domain, date 分组，取每个店铺当天的最大访客数
        - 然后按 owner, date 分组，累加所有店铺的访客数
        - 最后按 time_hour 分组，但同一天所有小时的访客数使用当天的最大值
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            allowed_owners: 授权负责人列表
            start_hour: 开始小时（可选）
            end_hour: 结束小时（可选）
        
        Returns:
            小时粒度数据列表（被授权负责人的聚合数据）
        """
        if not allowed_owners:
            return []
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 构建条件
                    placeholders = ','.join(['%s'] * len(allowed_owners))
                    conditions_sales = [
                        "s.time_hour >= %s",
                        "s.time_hour <= %s",
                        f"s.owner IN ({placeholders})"
                    ]
                    conditions_spend_fb = [
                        "f.time_hour >= %s",
                        "f.time_hour <= %s",
                        f"f.owner IN ({placeholders})"
                    ]
                    conditions_spend_tt = [
                        "t.time_hour >= %s",
                        "t.time_hour <= %s",
                        f"t.owner IN ({placeholders})"
                    ]
                    
                    params_sales = [start_time, end_time] + allowed_owners
                    params_spend_fb = [start_time, end_time] + allowed_owners
                    params_spend_tt = [start_time, end_time] + allowed_owners
                    
                    if start_hour is not None and end_hour is not None:
                        conditions_sales.append("HOUR(s.time_hour) >= %s")
                        conditions_sales.append("HOUR(s.time_hour) < %s")
                        params_sales.extend([start_hour, end_hour])
                        conditions_spend_fb.append("HOUR(f.time_hour) >= %s")
                        conditions_spend_fb.append("HOUR(f.time_hour) < %s")
                        params_spend_fb.extend([start_hour, end_hour])
                        conditions_spend_tt.append("HOUR(t.time_hour) >= %s")
                        conditions_spend_tt.append("HOUR(t.time_hour) < %s")
                        params_spend_tt.extend([start_hour, end_hour])
                    
                    # ⭐ 步骤1：查询销售数据（包含 owner, shop_domain, time_hour）
                    # 用于后续计算访客数
                    sql_sales_detail = f"""
                        SELECT 
                            s.owner,
                            s.shop_domain,
                            s.time_hour,
                            s.total_gmv,
                            s.total_orders,
                            s.total_visitors
                        FROM shoplazza_store_hourly s
                        WHERE {' AND '.join(conditions_sales)}
                        ORDER BY s.time_hour ASC, s.owner ASC, s.shop_domain ASC
                    """
                    cursor.execute(sql_sales_detail, params_sales)
                    sales_data = cursor.fetchall()
                    
                    # ⭐ 步骤2：在后端处理访客数
                    # 先按 owner, shop_domain, date 分组，取每个店铺当天的最大访客数
                    # 然后按 owner, date 分组，累加所有店铺的访客数
                    
                    # 存储每个店铺当天的最大访客数
                    shop_daily_visitors = defaultdict(int)  # {(owner, shop_domain, date): max_visitors}
                    # 存储每个负责人当天的总访客数
                    owner_daily_visitors = defaultdict(int)  # {(owner, date): total_visitors}
                    
                    for row in sales_data:
                        owner = row['owner']
                        shop_domain = row['shop_domain']
                        time_hour = row['time_hour']
                        if isinstance(time_hour, str):
                            time_hour = datetime.strptime(time_hour, "%Y-%m-%d %H:%M:%S")
                        elif isinstance(time_hour, date):
                            time_hour = datetime.combine(time_hour, datetime.min.time())
                        date_key = time_hour.date()
                        visitors = int(row['total_visitors'] or 0)
                        
                        # 取每个店铺当天的最大访客数
                        key = (owner, shop_domain, date_key)
                        shop_daily_visitors[key] = max(shop_daily_visitors[key], visitors)
                    
                    # 累加所有店铺的访客数，得到每个负责人当天的总访客数
                    for (owner, shop_domain, date_key), max_visitors in shop_daily_visitors.items():
                        owner_key = (owner, date_key)
                        owner_daily_visitors[owner_key] += max_visitors
                    
                    # ⭐ 步骤3：按 time_hour 聚合销售数据（GMV、订单数）
                    # 访客数使用每个负责人当天的总访客数
                    hourly_sales = defaultdict(lambda: {
                        'total_gmv': 0.0,
                        'total_orders': 0,
                        'total_visitors': 0,  # 会在后面设置
                        'total_spend': 0.0
                    })
                    
                    for row in sales_data:
                        time_hour = row['time_hour']
                        if isinstance(time_hour, str):
                            time_hour = datetime.strptime(time_hour, "%Y-%m-%d %H:%M:%S")
                        elif isinstance(time_hour, date):
                            time_hour = datetime.combine(time_hour, datetime.min.time())
                        
                        # 聚合 GMV 和订单数
                        hourly_sales[time_hour]['total_gmv'] += float(row['total_gmv'] or 0)
                        hourly_sales[time_hour]['total_orders'] += int(row['total_orders'] or 0)
                    
                    # 设置访客数：同一天所有小时的访客数使用当天的最大值
                    # 累加所有授权负责人的访客数
                    for time_hour in hourly_sales.keys():
                        date_key = time_hour.date()
                        total_visitors = 0
                        for owner in allowed_owners:
                            owner_key = (owner, date_key)
                            total_visitors += owner_daily_visitors.get(owner_key, 0)
                        hourly_sales[time_hour]['total_visitors'] = total_visitors
                    
                    # ⭐ 步骤4：查询广告花费数据
                    sql_spend = f"""
                        SELECT 
                            t.time_hour,
                            SUM(t.total_spend) AS total_spend
                        FROM (
                            SELECT 
                                f.time_hour,
                                SUM(f.spend) AS total_spend
                            FROM fb_ad_account_spend_hourly f
                            WHERE {' AND '.join(conditions_spend_fb)}
                            GROUP BY f.time_hour
                            
                            UNION ALL
                            
                            SELECT 
                                t.time_hour,
                                SUM(t.spend) AS total_spend
                            FROM tt_ad_account_spend_hourly t
                            WHERE {' AND '.join(conditions_spend_tt)}
                            GROUP BY t.time_hour
                        ) t
                        GROUP BY t.time_hour
                        ORDER BY t.time_hour ASC
                    """
                    all_params_spend = params_spend_fb + params_spend_tt
                    cursor.execute(sql_spend, all_params_spend)
                    spend_data = cursor.fetchall()
                    
                    # 合并广告花费数据
                    for row in spend_data:
                        time_hour = row['time_hour']
                        if isinstance(time_hour, str):
                            time_hour = datetime.strptime(time_hour, "%Y-%m-%d %H:%M:%S")
                        elif isinstance(time_hour, date):
                            time_hour = datetime.combine(time_hour, datetime.min.time())
                        
                        if time_hour in hourly_sales:
                            hourly_sales[time_hour]['total_spend'] += float(row['total_spend'] or 0)
                    
                    # ⭐ 步骤5：转换为列表格式
                    result = []
                    for time_hour in sorted(hourly_sales.keys()):
                        data = hourly_sales[time_hour]
                        result.append({
                            'time_hour': time_hour,
                            'total_gmv': data['total_gmv'],
                            'total_orders': data['total_orders'],
                            'total_visitors': data['total_visitors'],
                            'total_spend': data['total_spend']
                        })
                    
                    logger.debug(f"获取过滤后的小时数据成功，返回 {len(result)} 条记录（授权负责人：{allowed_owners}）")
                    return result
        except Exception as e:
            logger.error(f"获取过滤后的小时数据失败: {e}", exc_info=True)
            logger.error(f"授权负责人列表: {allowed_owners}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_daily_data_with_spend_filtered(
        self,
        start_time: datetime,
        end_time: datetime,
        allowed_owners: List[str]
    ) -> List[Dict[str, Any]]:
        """
        获取天粒度数据（按授权负责人过滤）
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            allowed_owners: 授权负责人列表
        
        Returns:
            天粒度数据列表（被授权负责人的聚合数据）
        """
        if not allowed_owners:
            return []
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 构建参数占位符
                    placeholders = ','.join(['%s'] * len(allowed_owners))
                    
                    # 先尝试使用包含 tt_total_spend 的完整SQL
                    sql_with_tt = f"""
                        SELECT 
                            date,
                            SUM(total_gmv)      AS total_gmv,
                            SUM(total_orders)   AS total_orders,
                            SUM(total_visitors) AS total_visitors,
                            SUM(total_spend + tt_total_spend) AS total_spend
                        FROM owner_daily_summary
                        WHERE date >= DATE(%s) 
                          AND date <= DATE(%s)
                          AND owner IN ({placeholders})
                        GROUP BY date
                        ORDER BY date ASC
                    """
                    try:
                        params = [start_time, end_time] + allowed_owners
                        cursor.execute(sql_with_tt, params)
                        result = cursor.fetchall()
                        logger.debug(f"获取过滤后的天数据成功，返回 {len(result)} 条记录（授权负责人：{allowed_owners}）")
                        return result
                    except Exception as sql_error:
                        # 如果SQL执行失败，检查是否是字段不存在的问题
                        error_msg = str(sql_error).lower()
                        if 'tt_total_spend' in error_msg or 'unknown column' in error_msg:
                            # 字段不存在，使用简化SQL（不包含 tt_total_spend）
                            logger.warning(f"表缺少 tt_total_spend 字段，使用简化SQL: {sql_error}")
                            sql_without_tt = f"""
                                SELECT 
                                    date,
                                    SUM(total_gmv)      AS total_gmv,
                                    SUM(total_orders)   AS total_orders,
                                    SUM(total_visitors) AS total_visitors,
                                    SUM(total_spend)    AS total_spend
                                FROM owner_daily_summary
                                WHERE date >= DATE(%s) 
                                  AND date <= DATE(%s)
                                  AND owner IN ({placeholders})
                                GROUP BY date
                                ORDER BY date ASC
                            """
                            params = [start_time, end_time] + allowed_owners
                            cursor.execute(sql_without_tt, params)
                            result = cursor.fetchall()
                            logger.debug(f"获取过滤后的天数据成功（简化SQL），返回 {len(result)} 条记录（授权负责人：{allowed_owners}）")
                            return result
                        else:
                            # 其他错误，重新抛出
                            raise
        except Exception as e:
            logger.error(f"获取过滤后的天数据失败: {e}", exc_info=True)
            logger.error(f"授权负责人列表: {allowed_owners}")
            return []

    def get_owner_daily_summary(self, start_date: date, end_date: date,
                                sort_by: str = 'owner', sort_order: str = 'asc') -> List[Dict[str, Any]]:
        """
        获取负责人维度的日汇总（合并多日）。
        ⚠️ 暂时使用 owner_daily_summary 表，确保能正常显示数据
        后续可以优化为直接从 shoplazza_store_hourly 计算，确保访客数逻辑正确
        只返回映射表中存在的 owner（避免显示残留的旧数据）
        返回字段：owner, total_gmv, total_orders, total_visitors, avg_order_value, total_spend, tt_total_spend, total_spend_all, roas
        """
        try:
            valid_sort = {
                'owner': 'owner',
                'gmv': 'total_gmv',
                'orders': 'total_orders',
                'visitors': 'total_visitors',
                'aov': 'avg_order_value',
                'spend': 'total_spend_all',  # 排序时使用总花费
                'roas': 'roas'
            }
            sort_col = valid_sort.get(sort_by, 'owner')
            sort_dir = 'ASC' if str(sort_order).lower() == 'asc' else 'DESC'

            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 先尝试使用包含 tt_total_spend 的完整SQL（与旧系统一致）
                    sql_with_tt = f"""
                        SELECT 
                            s.owner,
                            SUM(s.total_gmv)      AS total_gmv,
                            SUM(s.total_orders)   AS total_orders,
                            SUM(s.total_visitors) AS total_visitors,
                            SUM(s.total_spend)    AS total_spend,
                            SUM(s.tt_total_spend) AS tt_total_spend,
                            SUM(s.total_spend + s.tt_total_spend) AS total_spend_all,
                            CASE WHEN SUM(s.total_orders) > 0 
                                 THEN SUM(s.total_gmv) / SUM(s.total_orders) 
                                 ELSE 0 END        AS avg_order_value,
                            CASE WHEN SUM(s.total_spend + s.tt_total_spend) > 0 
                                 THEN SUM(s.total_gmv) / SUM(s.total_spend + s.tt_total_spend) 
                                 ELSE NULL END     AS roas,
                            CASE WHEN SUM(s.total_visitors) > 0 
                                 THEN SUM(s.total_orders) / SUM(s.total_visitors) * 100 
                                 ELSE 0 END        AS conversion_rate
                        FROM owner_daily_summary s
                        WHERE s.date >= DATE(%s) 
                          AND s.date <= DATE(%s)
                          AND (
                              EXISTS (
                                  SELECT 1 FROM store_owner_mapping m1 
                                  WHERE m1.owner = s.owner
                              )
                              OR EXISTS (
                                  SELECT 1 FROM ad_account_owner_mapping m2 
                                  WHERE m2.owner = s.owner
                              )
                              OR EXISTS (
                                  SELECT 1 FROM tt_ad_account_owner_mapping m3 
                                  WHERE m3.owner = s.owner
                              )
                          )
                        GROUP BY s.owner
                        ORDER BY {sort_col} {sort_dir}
                    """
                    try:
                        cursor.execute(sql_with_tt, (start_date, end_date))
                        return cursor.fetchall()
                    except Exception as sql_error:
                        # 如果SQL执行失败，检查是否是字段不存在的问题
                        error_msg = str(sql_error).lower()
                        if 'tt_total_spend' in error_msg or 'unknown column' in error_msg:
                            # 字段不存在，使用简化SQL（不包含 tt_total_spend）
                            logger.warning(f"表缺少 tt_total_spend 字段，使用简化SQL: {sql_error}")
                            sql_without_tt = f"""
                                SELECT 
                                    s.owner,
                                    SUM(s.total_gmv)      AS total_gmv,
                                    SUM(s.total_orders)   AS total_orders,
                                    SUM(s.total_visitors) AS total_visitors,
                                    SUM(s.total_spend)    AS total_spend,
                                    0                     AS tt_total_spend,
                                    SUM(s.total_spend)    AS total_spend_all,
                                    CASE WHEN SUM(s.total_orders) > 0 
                                         THEN SUM(s.total_gmv) / SUM(s.total_orders) 
                                         ELSE 0 END        AS avg_order_value,
                                    CASE WHEN SUM(s.total_spend) > 0 
                                         THEN SUM(s.total_gmv) / SUM(s.total_spend) 
                                         ELSE NULL END     AS roas,
                                    CASE WHEN SUM(s.total_visitors) > 0 
                                         THEN SUM(s.total_orders) / SUM(s.total_visitors) * 100 
                                         ELSE 0 END        AS conversion_rate
                                FROM owner_daily_summary s
                                WHERE s.date >= DATE(%s) 
                                  AND s.date <= DATE(%s)
                                  AND (
                                      EXISTS (
                                          SELECT 1 FROM store_owner_mapping m1 
                                          WHERE m1.owner = s.owner
                                      )
                                      OR EXISTS (
                                          SELECT 1 FROM ad_account_owner_mapping m2 
                                          WHERE m2.owner = s.owner
                                      )
                                      OR EXISTS (
                                          SELECT 1 FROM tt_ad_account_owner_mapping m3 
                                          WHERE m3.owner = s.owner
                                      )
                                  )
                                GROUP BY s.owner
                                ORDER BY {sort_col} {sort_dir}
                            """
                            cursor.execute(sql_without_tt, (start_date, end_date))
                            return cursor.fetchall()
                        else:
                            # 其他错误，重新抛出
                            raise
        except Exception as e:
            logger.error(f"获取负责人日汇总失败: {e}", exc_info=True)
            # 打印详细的错误信息，包括SQL语句
            logger.error(f"SQL查询失败，参数: start_date={start_date}, end_date={end_date}, sort_by={sort_by}, sort_order={sort_order}")
            # 与旧系统保持一致：返回空数组而不是抛出异常
            # 这样前端会显示"暂无数据"而不是500错误
            return []

    def get_owner_hourly_data(self, owner: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        获取负责人在时间范围内的小时级数据（销售+花费）。
        数据源：
          - 销售：shoplazza_store_hourly（按小时，过滤 owner）
          - Facebook花费：fb_ad_account_spend_hourly（按小时，过滤 owner）
          - TikTok花费：tt_ad_account_spend_hourly（按小时，过滤 owner）
        返回：time_hour, total_gmv, total_orders, total_visitors, total_spend, tt_total_spend, total_spend_all, avg_order_value, roas
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 销售数据
                    sql_sales = """
                        SELECT 
                            time_hour,
                            SUM(total_gmv)      AS total_gmv,
                            SUM(total_orders)   AS total_orders,
                            MAX(total_visitors) AS total_visitors
                        FROM shoplazza_store_hourly
                        WHERE owner = %s
                          AND time_hour >= %s AND time_hour <= %s
                        GROUP BY time_hour
                    """
                    cursor.execute(sql_sales, (owner, start_time, end_time))
                    sales_rows = cursor.fetchall()

                    # Facebook花费数据
                    sql_fb_spend = """
                        SELECT 
                            time_hour,
                            SUM(spend) AS total_spend
                        FROM fb_ad_account_spend_hourly
                        WHERE owner = %s
                          AND time_hour >= %s AND time_hour <= %s
                        GROUP BY time_hour
                    """
                    cursor.execute(sql_fb_spend, (owner, start_time, end_time))
                    fb_spend_rows = cursor.fetchall()

                    # TikTok花费数据
                    sql_tt_spend = """
                        SELECT 
                            time_hour,
                            SUM(spend) AS tt_total_spend
                        FROM tt_ad_account_spend_hourly
                        WHERE owner = %s
                          AND time_hour >= %s AND time_hour <= %s
                        GROUP BY time_hour
                    """
                    cursor.execute(sql_tt_spend, (owner, start_time, end_time))
                    tt_spend_rows = cursor.fetchall()

            # 合并销售与花费
            hourly_map: Dict[datetime, Dict[str, Any]] = {}

            for row in sales_rows:
                t = row['time_hour']
                hourly_map[t] = {
                    'time_hour': t,
                    'total_gmv': float(row.get('total_gmv') or 0),
                    'total_orders': int(row.get('total_orders') or 0),
                    'total_visitors': int(row.get('total_visitors') or 0),
                    'total_spend': 0.0,  # Facebook花费
                    'tt_total_spend': 0.0,  # TikTok花费
                }

            for row in fb_spend_rows:
                t = row['time_hour']
                if t not in hourly_map:
                    hourly_map[t] = {
                        'time_hour': t,
                        'total_gmv': 0.0,
                        'total_orders': 0,
                        'total_visitors': 0,
                        'total_spend': 0.0,
                        'tt_total_spend': 0.0,
                    }
                hourly_map[t]['total_spend'] = float(row.get('total_spend') or 0.0)

            for row in tt_spend_rows:
                t = row['time_hour']
                if t not in hourly_map:
                    hourly_map[t] = {
                        'time_hour': t,
                        'total_gmv': 0.0,
                        'total_orders': 0,
                        'total_visitors': 0,
                        'total_spend': 0.0,
                        'tt_total_spend': 0.0,
                    }
                hourly_map[t]['tt_total_spend'] = float(row.get('tt_total_spend') or 0.0)

            # 计算 AOV / ROAS / 转化率，并按时间排序
            result = []
            for t, row in hourly_map.items():
                total_gmv = float(row['total_gmv'])
                total_orders = int(row['total_orders'])
                total_visitors = int(row['total_visitors'])
                total_spend = float(row['total_spend'])  # Facebook花费
                tt_total_spend = float(row['tt_total_spend'])  # TikTok花费
                total_spend_all = total_spend + tt_total_spend  # 总花费
                avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
                roas = total_gmv / total_spend_all if total_spend_all > 0 else None
                conversion_rate = (total_orders / total_visitors * 100) if total_visitors > 0 else 0.0
                result.append({
                    'time_hour': t,
                    'total_gmv': total_gmv,
                    'total_orders': total_orders,
                    'total_visitors': total_visitors,
                    'total_spend': total_spend,  # Facebook花费
                    'tt_total_spend': tt_total_spend,  # TikTok花费
                    'total_spend_all': total_spend_all,  # 总花费（FB + TikTok）
                    'avg_order_value': avg_order_value,
                    'roas': roas,
                    'conversion_rate': conversion_rate
                })

            result.sort(key=lambda x: x['time_hour'])
            return result
        except Exception as e:
            logger.error(f"获取负责人小时数据失败 owner={owner}: {e}")
            return []
    
    def cleanup_old_data(self, retention_months: int = 3) -> int:
        """清理超过保留期的历史数据"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cutoff_date = datetime.now() - timedelta(days=retention_months * 30)
                    sql = """
                        DELETE FROM shoplazza_overview_hourly
                        WHERE time_hour < %s
                    """
                    cursor.execute(sql, (cutoff_date,))
                    deleted_count = cursor.rowcount
                    conn.commit()
                    logger.info(f"清理了 {deleted_count} 条超过 {retention_months} 个月的历史数据")
                    return deleted_count
        except Exception as e:
            logger.error(f"清理历史数据失败: {e}")
            return 0
    
    def log_operation(self, log_type: str, message: str, 
                     shop_domain: Optional[str] = None, 
                     status: str = 'success') -> bool:
        """
        记录操作日志到数据库
        
        Args:
            log_type: 日志类型（sync/error/info/warning）
            message: 日志消息
            shop_domain: 店铺域名（可选）
            status: 状态（success/error/warning）
        
        Returns:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO operation_logs 
                        (log_type, shop_domain, message, status)
                        VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(sql, (log_type, shop_domain, message, status))
                    conn.commit()
                    return True
        except Exception as e:
            # 记录日志失败时不抛出异常，避免影响主流程
            logger.error(f"记录日志到数据库失败: {e}")
            return False

    def log_mapping_audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        owner: Optional[str] = None,
        operator_user_id: Optional[int] = None,
        operator_username: Optional[str] = None,
        request_payload: Optional[Dict[str, Any]] = None,
        result_status: str = "success",
        result_message: Optional[str] = None,
    ) -> bool:
        """
        记录映射资源的结构化审计日志。

        设计原则：
        - 审计失败不影响主流程（返回 False，不抛异常）
        - payload 由调用方先脱敏后传入（例如 access_token 不得明文入库）
        """
        try:
            payload_text = json.dumps(request_payload, ensure_ascii=False) if request_payload is not None else None
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO mapping_resource_audit
                        (action, resource_type, resource_id, owner, operator_user_id, operator_username,
                         request_payload, result_status, result_message)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(
                        sql,
                        (
                            action,
                            resource_type,
                            resource_id,
                            owner,
                            operator_user_id,
                            operator_username,
                            payload_text,
                            result_status,
                            result_message,
                        ),
                    )
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"记录映射审计日志失败: {e}")
            return False

    def count_mapping_resource_audits(
        self,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        result_status: Optional[str] = None,
    ) -> int:
        """符合条件的映射审计总行数（用于分页）。"""
        where_clause, params = self._mapping_audit_where(resource_type, action, result_status)
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = f"SELECT COUNT(*) AS cnt FROM mapping_resource_audit WHERE {where_clause}"
                    cursor.execute(sql, params)
                    row = cursor.fetchone()
                    return int(row["cnt"]) if row else 0
        except Exception as e:
            logger.error(f"统计映射审计失败: {e}")
            return 0

    def get_mapping_resource_audits(
        self,
        limit: int = 50,
        offset: int = 0,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        result_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """分页查询映射审计记录，按 id 降序（最新在前）。"""
        where_clause, params = self._mapping_audit_where(resource_type, action, result_status)
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = f"""
                        SELECT id, action, resource_type, resource_id, owner,
                               operator_user_id, operator_username, request_payload,
                               result_status, result_message, created_at
                        FROM mapping_resource_audit
                        WHERE {where_clause}
                        ORDER BY id DESC
                        LIMIT %s OFFSET %s
                    """
                    cursor.execute(sql, tuple(list(params) + [limit, offset]))
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"查询映射审计失败: {e}")
            return []

    @staticmethod
    def _mapping_audit_where(
        resource_type: Optional[str],
        action: Optional[str],
        result_status: Optional[str],
    ) -> Tuple[str, List[Any]]:
        """构造 WHERE 子句与参数（调用方已对白名单值做过校验）。"""
        parts: List[str] = []
        params: List[Any] = []
        if resource_type:
            parts.append("resource_type = %s")
            params.append(resource_type)
        if action:
            parts.append("action = %s")
            params.append(action)
        if result_status:
            parts.append("result_status = %s")
            params.append(result_status)
        if not parts:
            return "1=1", params
        return " AND ".join(parts), params
    
    def cleanup_old_logs(self, file_log_days: int = 30, db_log_days: int = 90) -> Dict[str, int]:
        """
        清理过期日志
        
        Args:
            file_log_days: 文件日志保留天数（默认30天）
            db_log_days: 数据库日志保留天数（默认90天，即3个月）
        
        Returns:
            包含清理统计信息的字典
        """
        result = {'file_logs_deleted': 0, 'db_logs_deleted': 0}
        
        # 清理数据库日志
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cutoff_date = datetime.now() - timedelta(days=db_log_days)
                    sql = """
                        DELETE FROM operation_logs
                        WHERE created_at < %s
                    """
                    cursor.execute(sql, (cutoff_date,))
                    result['db_logs_deleted'] = cursor.rowcount
                    conn.commit()
                    logger.info(f"清理了 {result['db_logs_deleted']} 条超过 {db_log_days} 天的数据库日志")
        except Exception as e:
            logger.error(f"清理数据库日志失败: {e}")
        
        # 文件日志清理在外部处理（通过日志轮转配置实现）
        # 这里只返回统计信息
        
        return result
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户信息"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT id, username, password_hash, role
                        FROM users
                        WHERE username = %s
                    """
                    cursor.execute(sql, (username,))
                    return cursor.fetchone()
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None
    
    def get_sync_status(self, sync_type: str = 'five_minute_realtime') -> Optional[Dict[str, Any]]:
        """
        获取同步状态
        
        Args:
            sync_type: 同步类型，默认 'five_minute_realtime'
        
        Returns:
            同步状态字典，如果不存在则返回None
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT id, sync_type, last_sync_end_time, last_sync_date, 
                               last_visitor_cumulative, updated_at
                        FROM sync_status
                        WHERE sync_type = %s
                    """
                    cursor.execute(sql, (sync_type,))
                    return cursor.fetchone()
        except Exception as e:
            logger.error(f"获取同步状态失败: {e}")
            return None
    
    def update_sync_status(self, sync_type: str, last_sync_end_time: datetime, 
                          last_sync_date: datetime.date, 
                          last_visitor_cumulative: int = 0) -> bool:
        """
        更新同步状态
        
        Args:
            sync_type: 同步类型
            last_sync_end_time: 最后同步的结束时间（精确到秒）
            last_sync_date: 最后同步日期
            last_visitor_cumulative: 上次查询的累计访客数
        
        Returns:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO sync_status 
                        (sync_type, last_sync_end_time, last_sync_date, last_visitor_cumulative)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            last_sync_end_time = VALUES(last_sync_end_time),
                            last_sync_date = VALUES(last_sync_date),
                            last_visitor_cumulative = VALUES(last_visitor_cumulative),
                            updated_at = CURRENT_TIMESTAMP
                    """
                    cursor.execute(sql, (sync_type, last_sync_end_time, last_sync_date, last_visitor_cumulative))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"更新同步状态失败: {e}")
            return False
    
    def insert_or_update_hourly_data_incremental(self, time_hour: datetime, 
                                                  total_gmv: float, 
                                                  total_orders: int, 
                                                  total_visitors: int) -> bool:
        """
        插入或更新小时数据（增量累加模式，用于五分钟实时同步）
        
        ⭐ 修复：使用MySQL原子操作，避免并行写入时的竞争条件
        
        Args:
            time_hour: 小时时间点
            total_gmv: 新增销售额（累加到现有值）
            total_orders: 新增订单数（累加到现有值）
            total_visitors: 访客数（直接覆盖旧值，使用最新值）
        
        Returns:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # ⭐ 修复：使用 INSERT ... ON DUPLICATE KEY UPDATE 的原子操作
                    # 直接在数据库层面累加，避免并行写入时的竞争条件
                    # 访客数：直接覆盖旧值，使用最新收集的值（每次收集都是完整的按天去重值）
                    # 使用 CASE WHEN 避免除以0错误（当订单数为0时，客单价设为0）
                    sql = """
                        INSERT INTO shoplazza_overview_hourly 
                        (time_hour, total_gmv, total_orders, total_visitors, avg_order_value)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            total_gmv = total_gmv + VALUES(total_gmv),
                            total_orders = total_orders + VALUES(total_orders),
                            total_visitors = VALUES(total_visitors),
                            avg_order_value = CASE 
                                WHEN (total_orders + VALUES(total_orders)) > 0 
                                THEN (total_gmv + VALUES(total_gmv)) / (total_orders + VALUES(total_orders))
                                ELSE 0.0
                            END,
                            updated_at = CURRENT_TIMESTAMP
                    """
                    
                    # 计算初始客单价
                    avg_aov = total_gmv / total_orders if total_orders > 0 else 0.0
                    
                    cursor.execute(sql, (time_hour, total_gmv, total_orders, total_visitors, avg_aov))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"增量更新小时数据失败: {e}")
            return False
    
    def get_hourly_data_by_time(self, time_hour: datetime) -> Optional[Dict[str, Any]]:
        """
        根据时间点获取小时数据
        
        Args:
            time_hour: 小时时间点（例如：2025-12-02 00:00:00）
            
        Returns:
            小时数据字典，如果不存在返回None
            {
                'time_hour': datetime,
                'total_gmv': float,
                'total_orders': int,
                'total_visitors': int,
                'avg_order_value': float
            }
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT time_hour, total_gmv, total_orders, total_visitors, avg_order_value
                        FROM shoplazza_overview_hourly
                        WHERE time_hour = %s
                    """
                    cursor.execute(sql, (time_hour,))
                    return cursor.fetchone()
        except Exception as e:
            logger.error(f"获取小时数据失败: {e}")
            return None
    
    def insert_or_update_store_hourly(self, shop_domain: str, time_hour: datetime,
                                      total_gmv: float, total_orders: int, total_visitors: int,
                                      gmv_from_analysis: float = 0.0, orders_from_analysis: int = 0) -> bool:
        """
        插入或更新单店铺每小时明细数据（覆盖模式，用于历史同步）
        
        Args:
            shop_domain: 店铺域名
            time_hour: 小时时间点
            total_gmv: 销售额（来自订单接口）
            total_orders: 订单数（来自订单接口）
            total_visitors: 访客数（来自分析接口，按天去重）
            gmv_from_analysis: 销售额（来自分析接口，用于对比）
            orders_from_analysis: 订单数（来自分析接口，用于对比）
        
        Returns:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 查询 owner 映射
                    owner = None
                    owner_sql = "SELECT owner FROM store_owner_mapping WHERE shop_domain = %s"
                    cursor.execute(owner_sql, (shop_domain,))
                    owner_result = cursor.fetchone()
                    if owner_result:
                        owner = owner_result['owner']
                    
                    # 计算客单价
                    avg_order_value = (total_gmv / total_orders) if total_orders > 0 else 0.0
                    
                    # 计算差异
                    gmv_diff = total_gmv - gmv_from_analysis
                    orders_diff = total_orders - orders_from_analysis
                    
                    sql = """
                        INSERT INTO shoplazza_store_hourly 
                        (shop_domain, owner, time_hour, total_gmv, total_orders, total_visitors, 
                         avg_order_value, gmv_from_analysis, orders_from_analysis, 
                         gmv_diff, orders_diff)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            owner = VALUES(owner),
                            total_gmv = VALUES(total_gmv),
                            total_orders = VALUES(total_orders),
                            total_visitors = VALUES(total_visitors),
                            avg_order_value = VALUES(avg_order_value),
                            gmv_from_analysis = VALUES(gmv_from_analysis),
                            orders_from_analysis = VALUES(orders_from_analysis),
                            gmv_diff = VALUES(gmv_diff),
                            orders_diff = VALUES(orders_diff),
                            updated_at = CURRENT_TIMESTAMP
                    """
                    cursor.execute(sql, (
                        shop_domain, owner, time_hour, total_gmv, total_orders, total_visitors,
                        avg_order_value, gmv_from_analysis, orders_from_analysis,
                        gmv_diff, orders_diff
                    ))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"插入或更新单店铺明细数据失败: {e}")
            return False
    
    def insert_or_update_store_hourly_incremental(self, shop_domain: str, time_hour: datetime,
                                                   total_gmv: float, total_orders: int, 
                                                   total_visitors: int) -> bool:
        """
        插入或更新单店铺每小时明细数据（增量累加模式，用于5分钟实时同步）
        
        ⭐ 修复：使用MySQL原子操作，避免并行写入时的竞争条件
        
        Args:
            shop_domain: 店铺域名
            time_hour: 小时时间点
            total_gmv: 新增销售额（累加到现有值）
            total_orders: 新增订单数（累加到现有值）
            total_visitors: 访客数（直接覆盖旧值，使用最新值）
        
        Returns:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 查询 owner 映射
                    owner = None
                    owner_sql = "SELECT owner FROM store_owner_mapping WHERE shop_domain = %s"
                    cursor.execute(owner_sql, (shop_domain,))
                    owner_result = cursor.fetchone()
                    if owner_result:
                        owner = owner_result['owner']
                    
                    # ⭐ 修复：使用 INSERT ... ON DUPLICATE KEY UPDATE 的原子操作
                    # 直接在数据库层面累加，避免并行写入时的竞争条件
                    # 访客数：直接覆盖旧值，使用最新收集的值（每次收集都是完整的按天去重值）
                    # 使用 CASE WHEN 避免除以0错误（当订单数为0时，客单价设为0）
                    sql = """
                        INSERT INTO shoplazza_store_hourly 
                        (shop_domain, owner, time_hour, total_gmv, total_orders, total_visitors, avg_order_value)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            owner = COALESCE(VALUES(owner), owner),
                            total_gmv = total_gmv + VALUES(total_gmv),
                            total_orders = total_orders + VALUES(total_orders),
                            total_visitors = VALUES(total_visitors),
                            avg_order_value = CASE 
                                WHEN (total_orders + VALUES(total_orders)) > 0 
                                THEN (total_gmv + VALUES(total_gmv)) / (total_orders + VALUES(total_orders))
                                ELSE 0.0
                            END,
                            updated_at = CURRENT_TIMESTAMP
                    """
                    
                    # 计算初始客单价
                    avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
                    
                    cursor.execute(sql, (shop_domain, owner, time_hour, total_gmv, total_orders, total_visitors, avg_order_value))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"增量更新单店铺明细数据失败 {shop_domain}: {e}")
            return False
    
    def get_store_hourly_data(self, shop_domain: str, start_time: datetime, end_time: datetime,
                              start_hour: Optional[int] = None,
                              end_hour: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取单个店铺的小时数据
        
        Args:
            shop_domain: 店铺域名
            start_time: 开始时间
            end_time: 结束时间
            start_hour: 开始小时（可选，用于日内时段筛选）
            end_hour: 结束小时（可选，用于日内时段筛选）
        
        Returns:
            小时数据列表
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 构建查询条件
                    conditions = ["shop_domain = %s", "time_hour >= %s", "time_hour <= %s"]
                    params = [shop_domain, start_time, end_time]
                    
                    # 如果有日内时段筛选
                    if start_hour is not None and end_hour is not None:
                        conditions.append("HOUR(time_hour) >= %s")
                        conditions.append("HOUR(time_hour) < %s")
                        params.extend([start_hour, end_hour])
                    
                    sql = f"""
                        SELECT time_hour, total_gmv, total_orders, total_visitors, avg_order_value
                        FROM shoplazza_store_hourly
                        WHERE {' AND '.join(conditions)}
                        ORDER BY time_hour ASC
                    """
                    cursor.execute(sql, params)
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取单店铺小时数据失败 {shop_domain}: {e}")
            return []
    
    def get_store_daily_data(self, shop_domain: str, start_time: datetime, end_time: datetime,
                             start_hour: Optional[int] = None,
                             end_hour: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取单个店铺的按天聚合数据
        
        Args:
            shop_domain: 店铺域名
            start_time: 开始时间
            end_time: 结束时间
            start_hour: 开始小时（可选，用于日内时段筛选）
            end_hour: 结束小时（可选，用于日内时段筛选）
        
        Returns:
            按天聚合的数据列表
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    conditions = ["shop_domain = %s", "DATE(time_hour) >= DATE(%s)", "DATE(time_hour) <= DATE(%s)"]
                    params = [shop_domain, start_time, end_time]
                    
                    if start_hour is not None and end_hour is not None:
                        conditions.append("HOUR(time_hour) >= %s")
                        conditions.append("HOUR(time_hour) < %s")
                        params.extend([start_hour, end_hour])
                    
                    sql = f"""
                        SELECT 
                            DATE(time_hour) as date,
                            SUM(total_gmv) as total_gmv,
                            SUM(total_orders) as total_orders,
                            MAX(total_visitors) as total_visitors,
                            -- 不在这里计算客单价，在dashboard.py中重新计算（总销售额 / 总订单数）
                            0 as avg_order_value
                        FROM shoplazza_store_hourly
                        WHERE {' AND '.join(conditions)}
                        GROUP BY DATE(time_hour)
                        ORDER BY date ASC
                    """
                    cursor.execute(sql, params)
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取单店铺天数据失败 {shop_domain}: {e}")
            return []
    
    def get_store_display_name(self, shop_domain: str) -> str:
        """
        从店铺域名中提取显示名称
        例如：hipkastl.myshoplaza.com -> hipkastl
        
        Args:
            shop_domain: 店铺域名
        
        Returns:
            店铺显示名称（域名前缀部分）
        """
        # 提取域名前缀
        if '.' in shop_domain:
            return shop_domain.split('.')[0]
        return shop_domain
    
    def get_all_stores_for_display(self) -> List[Dict[str, Any]]:
        """
        获取所有店铺的显示信息（包括总店铺选项）
        
        Returns:
            店铺列表，包含：
            [
                {'shop_domain': 'ALL_STORES', 'display_name': '总店铺', 'is_total': True},
                {'shop_domain': 'hipkastl.myshoplaza.com', 'display_name': 'hipkastl', 'is_total': False},
                ...
            ]
        """
        try:
            stores = []
            
            # 添加"总店铺"选项（放在最前面）
            stores.append({
                'shop_domain': 'ALL_STORES',
                'display_name': '总店铺',
                'is_total': True
            })
            
            # 获取所有启用的店铺
            active_stores = self.get_active_stores()
            
            # 为每个店铺提取显示名称，并按显示名称排序
            store_list = []
            for store in active_stores:
                display_name = self.get_store_display_name(store['shop_domain'])
                store_list.append({
                    'shop_domain': store['shop_domain'],
                    'display_name': display_name,
                    'is_total': False
                })
            
            # 按显示名称排序
            store_list.sort(key=lambda x: x['display_name'])
            
            # 添加到结果列表
            stores.extend(store_list)
            
            logger.info(f"获取到 {len(stores)} 个店铺选项（包括总店铺）")
            return stores
        except Exception as e:
            logger.error(f"获取店铺显示信息失败: {e}")
            # 即使失败也返回总店铺选项
            return [{
                'shop_domain': 'ALL_STORES',
                'display_name': '总店铺',
                'is_total': True
            }]
    
    def get_all_stores_summary(self, start_date, end_date) -> List[Dict[str, Any]]:
        """
        获取所有店铺在指定日期范围内的汇总数据
        使用与单个店铺查询相同的逻辑，确保数据一致性
        
        Args:
            start_date: 开始日期（date类型，包含）
            end_date: 结束日期（date类型，包含）
        
        Returns:
            店铺汇总数据列表，每个店铺一行
            字段：store_id, shop_domain, store_name, total_gmv, total_orders, 
                  total_visitors, avg_order_value
        """
        try:
            # 转换为datetime（与单个店铺查询一致）
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            # 获取所有店铺（包括禁用的店铺，确保与总店铺汇总数据一致）
            stores = self.get_all_stores()
            results = []
            
            for store in stores:
                shop_domain = store['shop_domain']
                
                # 使用与单个店铺查询相同的方法（已验证正确）
                hourly_data = self.get_store_hourly_data(
                    shop_domain, start_datetime, end_datetime
                )
                
                # 在Python层面聚合（与get_store_daily_data的逻辑一致）
                if hourly_data:
                    # 按天聚合（处理访客数按天去重）
                    daily_data = {}
                    for h in hourly_data:
                        # 处理time_hour（可能是datetime对象或date对象）
                        time_hour = h['time_hour']
                        if isinstance(time_hour, datetime):
                            day_key = time_hour.date()
                        elif isinstance(time_hour, date):
                            day_key = time_hour
                        else:
                            # 如果是字符串，尝试解析
                            try:
                                time_hour_dt = datetime.strptime(str(time_hour), '%Y-%m-%d %H:%M:%S')
                                day_key = time_hour_dt.date()
                            except:
                                logger.warning(f"无法解析time_hour: {time_hour}")
                                continue
                        
                        if day_key not in daily_data:
                            daily_data[day_key] = {
                                'total_gmv': 0.0,
                                'total_orders': 0,
                                'total_visitors': 0
                            }
                        
                        # 累加销售额和订单数
                        daily_data[day_key]['total_gmv'] += float(h['total_gmv'])
                        daily_data[day_key]['total_orders'] += int(h['total_orders'])
                        # 访客数取最大值（按天去重）
                        daily_data[day_key]['total_visitors'] = max(
                            daily_data[day_key]['total_visitors'],
                            int(h['total_visitors'])
                        )
                    
                    # 汇总所有天的数据
                    total_gmv = sum(d['total_gmv'] for d in daily_data.values())
                    total_orders = sum(d['total_orders'] for d in daily_data.values())
                    total_visitors = sum(d['total_visitors'] for d in daily_data.values())
                else:
                    total_gmv = 0.0
                    total_orders = 0
                    total_visitors = 0
                
                # 计算客单价
                avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
                
                results.append({
                    'store_id': store['id'],
                    'shop_domain': shop_domain,
                    'store_name': self.get_store_display_name(shop_domain),
                    'total_gmv': total_gmv,
                    'total_orders': total_orders,
                    'total_visitors': total_visitors,
                    'avg_order_value': avg_order_value
                })
            
            # 按店铺名称排序
            results.sort(key=lambda x: x['store_name'])
            
            logger.info(f"获取到 {len(results)} 个店铺的汇总数据（日期范围：{start_date} 至 {end_date}）")
            return results
            
        except Exception as e:
            logger.error(f"获取所有店铺汇总数据失败: {e}")
            return []
    
    def get_store_owner_mappings(self) -> List[Dict[str, Any]]:
        """获取所有店铺-负责人映射"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT id, shop_domain, owner, created_at, updated_at
                        FROM store_owner_mapping
                        ORDER BY shop_domain
                    """
                    cursor.execute(sql)
                    mappings = cursor.fetchall()
                    logger.info(f"获取到 {len(mappings)} 条店铺映射")
                    return mappings
        except Exception as e:
            logger.error(f"获取店铺映射失败: {e}")
            return []
    
    def get_ad_account_owner_mappings(self) -> List[Dict[str, Any]]:
        """获取所有Facebook广告账户-负责人映射"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT id, ad_account_id, owner, created_at, updated_at
                        FROM ad_account_owner_mapping
                        ORDER BY ad_account_id
                    """
                    cursor.execute(sql)
                    mappings = cursor.fetchall()
                    logger.info(f"获取到 {len(mappings)} 条Facebook广告账户映射")
                    return mappings
        except Exception as e:
            logger.error(f"获取Facebook广告账户映射失败: {e}")
            return []
    
    def get_tt_ad_account_owner_mappings(self) -> List[Dict[str, Any]]:
        """获取所有TikTok广告账户-负责人映射"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT id, ad_account_id, owner, created_at, updated_at
                        FROM tt_ad_account_owner_mapping
                        ORDER BY ad_account_id
                    """
                    cursor.execute(sql)
                    mappings = cursor.fetchall()
                    logger.info(f"获取到 {len(mappings)} 条TikTok广告账户映射")
                    return mappings
        except Exception as e:
            logger.error(f"获取TikTok广告账户映射失败: {e}")
            return []

    def suggest_mapping_owners(self, query: str = "", limit: int = 40) -> List[str]:
        """
        店铺 / FB / TT 三表合并去重后的负责人名称，供新增映射联想。
        query 非空时按子串模糊匹配（与前端原先 String#includes 行为类似）。
        """
        lim = max(1, min(int(limit), 100))
        q = (query or "").strip()
        sub = """
            SELECT DISTINCT TRIM(owner) AS owner FROM store_owner_mapping
            WHERE owner IS NOT NULL AND TRIM(owner) <> ''
            UNION
            SELECT DISTINCT TRIM(owner) FROM ad_account_owner_mapping
            WHERE owner IS NOT NULL AND TRIM(owner) <> ''
            UNION
            SELECT DISTINCT TRIM(owner) FROM tt_ad_account_owner_mapping
            WHERE owner IS NOT NULL AND TRIM(owner) <> ''
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    if q:
                        sql = (
                            f"SELECT owner FROM ({sub}) AS u WHERE owner LIKE %s "
                            "ORDER BY owner ASC LIMIT %s"
                        )
                        cursor.execute(sql, (f"%{q}%", lim))
                    else:
                        sql = f"SELECT owner FROM ({sub}) AS u ORDER BY owner ASC LIMIT %s"
                        cursor.execute(sql, (lim,))
                    rows = cursor.fetchall()
                    return [r["owner"] for r in rows if r.get("owner")]
        except Exception as e:
            logger.error(f"suggest_mapping_owners 失败: {e}")
            return []

    def create_or_update_store_mapping(
        self,
        shop_domain: str,
        owner: str,
        access_token: str,
        is_active: bool = True,
    ) -> bool:
        """
        创建或更新店铺与负责人映射。
        同一事务内写入：
        1) shoplazza_stores（店铺凭证）
        2) store_owner_mapping（店铺负责人）
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO shoplazza_stores (shop_domain, access_token, is_active, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                          access_token = VALUES(access_token),
                          is_active = VALUES(is_active),
                          updated_at = NOW()
                        """,
                        (shop_domain, access_token, bool(is_active)),
                    )
                    cursor.execute(
                        """
                        INSERT INTO store_owner_mapping (shop_domain, owner, updated_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                          owner = VALUES(owner),
                          updated_at = NOW()
                        """,
                        (shop_domain, owner),
                    )
                    conn.commit()
                    logger.info("创建/更新店铺映射成功: %s -> %s", shop_domain, owner)
                    return True
        except Exception as e:
            logger.error("创建/更新店铺映射失败: %s", e)
            return False

    def create_or_update_facebook_mapping(self, ad_account_id: str, owner: str) -> bool:
        """创建或更新 Facebook 广告账户映射。"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO ad_account_owner_mapping (ad_account_id, owner, updated_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                          owner = VALUES(owner),
                          updated_at = NOW()
                        """,
                        (ad_account_id, owner),
                    )
                    conn.commit()
                    logger.info("创建/更新 Facebook 映射成功: %s -> %s", ad_account_id, owner)
                    return True
        except Exception as e:
            logger.error("创建/更新 Facebook 映射失败: %s", e)
            return False

    def create_or_update_tiktok_mapping(self, ad_account_id: str, owner: str) -> bool:
        """创建或更新 TikTok 广告账户映射。"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO tt_ad_account_owner_mapping (ad_account_id, owner, updated_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                          owner = VALUES(owner),
                          updated_at = NOW()
                        """,
                        (ad_account_id, owner),
                    )
                    conn.commit()
                    logger.info("创建/更新 TikTok 映射成功: %s -> %s", ad_account_id, owner)
                    return True
        except Exception as e:
            logger.error("创建/更新 TikTok 映射失败: %s", e)
            return False
    
    def update_store_owner_mapping(self, shop_domain: str, owner: str) -> Optional[List[date]]:
        """
        更新店铺-负责人映射（如果不存在则插入）
        同时更新历史数据表中的 owner 字段
        返回受影响的日期列表（用于重新聚合）
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. 更新映射表
                    sql = """
                        INSERT INTO store_owner_mapping (shop_domain, owner, updated_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            owner = VALUES(owner),
                            updated_at = NOW()
                    """
                    cursor.execute(sql, (shop_domain, owner))
                    
                    # 2. 获取受影响的日期列表（在更新前获取，避免更新后查询不到旧数据）
                    affected_dates_sql = """
                        SELECT DISTINCT DATE(time_hour) as affected_date
                        FROM shoplazza_store_hourly
                        WHERE shop_domain = %s
                        ORDER BY affected_date
                    """
                    cursor.execute(affected_dates_sql, (shop_domain,))
                    affected_dates = [row['affected_date'] for row in cursor.fetchall()]
                    
                    # 3. 更新历史数据表中的 owner 字段
                    update_sql = """
                        UPDATE shoplazza_store_hourly
                        SET owner = %s
                        WHERE shop_domain = %s
                    """
                    cursor.execute(update_sql, (owner, shop_domain))
                    updated_rows = cursor.rowcount
                    
                    conn.commit()
                    logger.info(f"更新店铺映射成功: {shop_domain} -> {owner}, 更新了 {updated_rows} 条历史记录, 影响 {len(affected_dates)} 个日期")
                    return affected_dates
        except Exception as e:
            logger.error(f"更新店铺映射失败: {e}")
            return None
    
    def update_ad_account_owner_mapping(self, ad_account_id: str, owner: str) -> Optional[List[date]]:
        """
        更新Facebook广告账户-负责人映射（如果不存在则插入）
        同时更新历史数据表中的 owner 字段
        返回受影响的日期列表（用于重新聚合）
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. 更新映射表
                    sql = """
                        INSERT INTO ad_account_owner_mapping (ad_account_id, owner, updated_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            owner = VALUES(owner),
                            updated_at = NOW()
                    """
                    cursor.execute(sql, (ad_account_id, owner))
                    
                    # 2. 获取受影响的日期列表（在更新前获取）
                    affected_dates_sql = """
                        SELECT DISTINCT DATE(time_hour) as affected_date
                        FROM fb_ad_account_spend_hourly
                        WHERE ad_account_id = %s
                        ORDER BY affected_date
                    """
                    cursor.execute(affected_dates_sql, (ad_account_id,))
                    affected_dates = [row['affected_date'] for row in cursor.fetchall()]
                    
                    # 3. 更新历史数据表中的 owner 字段
                    update_sql = """
                        UPDATE fb_ad_account_spend_hourly
                        SET owner = %s
                        WHERE ad_account_id = %s
                    """
                    cursor.execute(update_sql, (owner, ad_account_id))
                    updated_rows = cursor.rowcount
                    
                    conn.commit()
                    logger.info(f"更新Facebook广告账户映射成功: {ad_account_id} -> {owner}, 更新了 {updated_rows} 条历史记录, 影响 {len(affected_dates)} 个日期")
                    return affected_dates
        except Exception as e:
            logger.error(f"更新Facebook广告账户映射失败: {e}")
            return None
    
    def update_tt_ad_account_owner_mapping(self, ad_account_id: str, owner: str) -> Optional[List[date]]:
        """
        更新TikTok广告账户-负责人映射（如果不存在则插入）
        同时更新历史数据表中的 owner 字段
        返回受影响的日期列表（用于重新聚合）
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. 更新映射表
                    sql = """
                        INSERT INTO tt_ad_account_owner_mapping (ad_account_id, owner, updated_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            owner = VALUES(owner),
                            updated_at = NOW()
                    """
                    cursor.execute(sql, (ad_account_id, owner))
                    
                    # 2. 获取受影响的日期列表（在更新前获取）
                    affected_dates_sql = """
                        SELECT DISTINCT DATE(time_hour) as affected_date
                        FROM tt_ad_account_spend_hourly
                        WHERE ad_account_id = %s
                        ORDER BY affected_date
                    """
                    cursor.execute(affected_dates_sql, (ad_account_id,))
                    affected_dates = [row['affected_date'] for row in cursor.fetchall()]
                    
                    # 3. 更新历史数据表中的 owner 字段
                    update_sql = """
                        UPDATE tt_ad_account_spend_hourly
                        SET owner = %s
                        WHERE ad_account_id = %s
                    """
                    cursor.execute(update_sql, (owner, ad_account_id))
                    updated_rows = cursor.rowcount
                    
                    conn.commit()
                    logger.info(f"更新TikTok广告账户映射成功: {ad_account_id} -> {owner}, 更新了 {updated_rows} 条历史记录, 影响 {len(affected_dates)} 个日期")
                    return affected_dates
        except Exception as e:
            logger.error(f"更新TikTok广告账户映射失败: {e}")
            return None
    
    def aggregate_owner_daily_for_dates(self, dates: List[date]) -> bool:
        """
        重新聚合指定日期的负责人日汇总数据
        用于映射更新后重新聚合受影响日期的数据
        先删除受影响日期的所有数据，然后重新聚合，确保数据完全一致
        """
        try:
            with self.get_connection() as conn:
                for target_date in dates:
                    with conn.cursor() as cursor:
                        # 1. 先删除该日期的所有数据（避免旧数据残留）
                        delete_sql = """
                            DELETE FROM owner_daily_summary
                            WHERE date = %s
                        """
                        cursor.execute(delete_sql, (target_date,))
                        deleted_rows = cursor.rowcount
                        
                        # 2. 聚合店铺数据
                        # ⚠️ 访客数逻辑说明：
                        # - 访客数是按天去重的，同一天所有小时的访客数应该相同
                        # - 对于同一个店铺同一天的所有小时记录，total_visitors 值相同
                        # - 所以应该先按店铺取MAX（去重24小时），然后按负责人SUM（累加不同店铺）
                        # - 不同店铺的访客是不同的IP，应该累加
                        store_sql = """
                            SELECT 
                                owner,
                                SUM(total_gmv) as total_gmv,
                                SUM(total_orders) as total_orders,
                                SUM(shop_max_visitors) as total_visitors
                            FROM (
                                SELECT 
                                    owner,
                                    shop_domain,
                                    SUM(total_gmv) as total_gmv,
                                    SUM(total_orders) as total_orders,
                                    MAX(total_visitors) as shop_max_visitors
                                FROM shoplazza_store_hourly
                                WHERE DATE(time_hour) = %s
                                  AND owner IS NOT NULL
                                GROUP BY owner, shop_domain
                            ) AS shop_daily
                            GROUP BY owner
                        """
                        
                        # 3. 聚合Facebook广告花费数据
                        spend_sql = """
                            SELECT 
                                owner,
                                SUM(spend) as total_spend
                            FROM fb_ad_account_spend_hourly
                            WHERE DATE(time_hour) = %s
                            GROUP BY owner
                        """
                        
                        # 4. 聚合TikTok广告花费数据
                        tt_spend_sql = """
                            SELECT 
                                owner,
                                SUM(spend) as tt_total_spend
                            FROM tt_ad_account_spend_hourly
                            WHERE DATE(time_hour) = %s
                            GROUP BY owner
                        """
                        
                        # 获取店铺数据
                        cursor.execute(store_sql, (target_date,))
                        store_data = {row['owner']: row for row in cursor.fetchall()}
                        
                        # 获取Facebook广告花费数据
                        cursor.execute(spend_sql, (target_date,))
                        spend_data = {row['owner']: float(row['total_spend'] or 0) for row in cursor.fetchall()}
                        
                        # 获取TikTok广告花费数据
                        cursor.execute(tt_spend_sql, (target_date,))
                        tt_spend_data = {row['owner']: float(row['tt_total_spend'] or 0) for row in cursor.fetchall()}
                        
                        # 合并所有负责人
                        all_owners = set(store_data.keys()) | set(spend_data.keys()) | set(tt_spend_data.keys())
                        
                        # 5. 重新插入每个负责人的日汇总数据
                        for owner in all_owners:
                            store_info = store_data.get(owner, {
                                'total_gmv': 0.0,
                                'total_orders': 0,
                                'total_visitors': 0
                            })
                            
                            total_gmv = float(store_info.get('total_gmv', 0) or 0)
                            total_orders = int(store_info.get('total_orders', 0) or 0)
                            total_visitors = int(store_info.get('total_visitors', 0) or 0)
                            avg_order_value = total_gmv / total_orders if total_orders > 0 else 0.0
                            total_spend = spend_data.get(owner, 0.0)  # Facebook花费
                            tt_total_spend = tt_spend_data.get(owner, 0.0)  # TikTok花费
                            total_spend_all = total_spend + tt_total_spend  # 总花费
                            roas = total_gmv / total_spend_all if total_spend_all > 0 else None
                            
                            # 使用 INSERT INTO 插入新数据（包含TikTok花费字段）
                            insert_sql = """
                                INSERT INTO owner_daily_summary
                                  (date, owner, total_gmv, total_orders, total_visitors, 
                                   avg_order_value, total_spend, tt_total_spend, roas)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            cursor.execute(insert_sql, (
                                target_date, owner, total_gmv, total_orders, total_visitors,
                                avg_order_value, total_spend, tt_total_spend, roas
                            ))
                        
                        conn.commit()
                        logger.info(f"重新聚合日期 {target_date} 完成，删除了 {deleted_rows} 条旧记录，插入了 {len(all_owners)} 条新记录")
                
                return True
        except Exception as e:
            logger.error(f"重新聚合数据失败: {e}")
            return False

    def get_user_permissions(self, user_id: int) -> List[str]:
        """
        获取用户的授权负责人列表
        
        Args:
            user_id: 用户ID
        
        Returns:
            负责人名称列表，如果用户没有权限则返回空列表
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT owner
                        FROM user_owner_permissions
                        WHERE user_id = %s
                        ORDER BY owner
                    """
                    cursor.execute(sql, (user_id,))
                    results = cursor.fetchall()
                    # 提取负责人名称列表
                    return [row['owner'] for row in results]
        except Exception as e:
            logger.error(f"获取用户权限失败 (user_id={user_id}): {e}")
            return []
    
    def update_user_permissions(self, user_id: int, owners: List[str]) -> bool:
        """
        更新用户的权限（先删除旧权限，再插入新权限）
        
        Args:
            user_id: 用户ID
            owners: 负责人名称列表
        
        Returns:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 先删除该用户的所有旧权限
                    delete_sql = """
                        DELETE FROM user_owner_permissions
                        WHERE user_id = %s
                    """
                    cursor.execute(delete_sql, (user_id,))
                    
                    # 如果有新的权限，插入新权限
                    if owners:
                        insert_sql = """
                            INSERT INTO user_owner_permissions (user_id, owner)
                            VALUES (%s, %s)
                        """
                        # 批量插入
                        cursor.executemany(insert_sql, [(user_id, owner) for owner in owners])
                    
                    conn.commit()
                    logger.info(f"更新用户权限成功 (user_id={user_id}, owners={len(owners)}个)")
                    return True
        except Exception as e:
            logger.error(f"更新用户权限失败 (user_id={user_id}): {e}")
            return False
    
    def get_all_owners(self) -> List[str]:
        """
        获取所有负责人列表：店铺 / Facebook / TikTok 三表合并去重，与映射联想一致。
        供权限管理页展示可勾选的负责人，避免仅出现在广告侧映射的负责人无法被授权。
        """
        sql = """
            SELECT owner FROM (
                SELECT DISTINCT TRIM(owner) AS owner FROM store_owner_mapping
                WHERE owner IS NOT NULL AND TRIM(owner) <> ''
                UNION
                SELECT DISTINCT TRIM(owner) FROM ad_account_owner_mapping
                WHERE owner IS NOT NULL AND TRIM(owner) <> ''
                UNION
                SELECT DISTINCT TRIM(owner) FROM tt_ad_account_owner_mapping
                WHERE owner IS NOT NULL AND TRIM(owner) <> ''
            ) AS u
            ORDER BY owner
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    return [row["owner"] for row in results if row.get("owner")]
        except Exception as e:
            logger.error(f"获取负责人列表失败: {e}")
            return []
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        获取所有用户列表
        
        Returns:
            用户信息列表，包含id、username、role、can_view_dashboard、can_edit_mappings
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT id, username, role, 
                               COALESCE(can_view_dashboard, FALSE) as can_view_dashboard,
                               COALESCE(can_edit_mappings, FALSE) as can_edit_mappings,
                               COALESCE(can_view_store_ops, FALSE) as can_view_store_ops,
                               COALESCE(can_edit_store_ops_config, FALSE) as can_edit_store_ops_config
                        FROM users
                        ORDER BY id
                    """
                    cursor.execute(sql)
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return []
    
    def get_user_extended_permissions(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户的扩展权限
        
        Args:
            user_id: 用户ID
        
        Returns:
            扩展权限字典，包含 can_view_dashboard / can_edit_mappings /
            can_view_store_ops / can_edit_store_ops_config
        """
        default_perms = {
            "can_view_dashboard": False,
            "can_edit_mappings": False,
            "can_view_store_ops": False,
            "can_edit_store_ops_config": False,
        }
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT 
                            COALESCE(can_view_dashboard, FALSE) as can_view_dashboard,
                            COALESCE(can_edit_mappings, FALSE) as can_edit_mappings,
                            COALESCE(can_view_store_ops, FALSE) as can_view_store_ops,
                            COALESCE(can_edit_store_ops_config, FALSE) as can_edit_store_ops_config
                        FROM users
                        WHERE id = %s
                    """
                    cursor.execute(sql, (user_id,))
                    result = cursor.fetchone()
                    if result:
                        return {
                            "can_view_dashboard": bool(result.get("can_view_dashboard", False)),
                            "can_edit_mappings": bool(result.get("can_edit_mappings", False)),
                            "can_view_store_ops": bool(result.get("can_view_store_ops", False)),
                            "can_edit_store_ops_config": bool(
                                result.get("can_edit_store_ops_config", False)
                            ),
                        }
                    return dict(default_perms)
        except Exception as e:
            logger.error(f"获取用户扩展权限失败 (user_id={user_id}): {e}")
            return dict(default_perms)
    
    def update_user_extended_permissions(
        self,
        user_id: int,
        can_view_dashboard: bool,
        can_edit_mappings: bool,
        can_view_store_ops: bool = False,
        can_edit_store_ops_config: bool = False,
    ) -> bool:
        """
        更新用户的扩展权限
        
        Args:
            user_id: 用户ID
            can_view_dashboard: 是否可以查看看板总数据
            can_edit_mappings: 是否可以编辑映射
            can_view_store_ops: 是否可查看店铺运营/员工归因报表
            can_edit_store_ops_config: 是否可编辑店铺运营子系统配置
        
        Returns:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        UPDATE users
                        SET can_view_dashboard = %s,
                            can_edit_mappings = %s,
                            can_view_store_ops = %s,
                            can_edit_store_ops_config = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """
                    cursor.execute(
                        sql,
                        (
                            can_view_dashboard,
                            can_edit_mappings,
                            can_view_store_ops,
                            can_edit_store_ops_config,
                            user_id,
                        ),
                    )
                    conn.commit()
                    logger.info(
                        f"更新用户扩展权限成功 (user_id={user_id}, "
                        f"can_view_dashboard={can_view_dashboard}, can_edit_mappings={can_edit_mappings}, "
                        f"can_view_store_ops={can_view_store_ops}, "
                        f"can_edit_store_ops_config={can_edit_store_ops_config})"
                    )
                    return True
        except Exception as e:
            logger.error(f"更新用户扩展权限失败 (user_id={user_id}): {e}")
            return False

    def upsert_store_ops_order_attribution(self, row: Dict[str, Any]) -> bool:
        """
        写入或更新一条店铺运营订单归因明细（按 shop_domain + order_id 幂等）。
        """
        required = (
            "shop_domain",
            "order_id",
            "biz_date",
            "total_price",
            "attribution_type",
        )
        for k in required:
            if k not in row:
                logger.error(f"upsert_store_ops_order_attribution 缺少字段: {k}")
                return False
        raw_json = row.get("raw_json")
        if raw_json is not None and not isinstance(raw_json, str):
            raw_json = json.dumps(raw_json, ensure_ascii=False)
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO store_ops_order_attributions (
                            shop_domain, order_id, placed_at_raw, biz_date,
                            total_price, currency, financial_status,
                            attribution_type, employee_slug, utm_decision,
                            source_url, last_landing_url, raw_json, sync_run_id
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON DUPLICATE KEY UPDATE
                            placed_at_raw = VALUES(placed_at_raw),
                            biz_date = VALUES(biz_date),
                            total_price = VALUES(total_price),
                            currency = VALUES(currency),
                            financial_status = VALUES(financial_status),
                            attribution_type = VALUES(attribution_type),
                            employee_slug = VALUES(employee_slug),
                            utm_decision = VALUES(utm_decision),
                            source_url = VALUES(source_url),
                            last_landing_url = VALUES(last_landing_url),
                            raw_json = VALUES(raw_json),
                            sync_run_id = VALUES(sync_run_id),
                            updated_at = CURRENT_TIMESTAMP
                    """
                    cursor.execute(
                        sql,
                        (
                            row["shop_domain"],
                            row["order_id"],
                            row.get("placed_at_raw"),
                            row["biz_date"],
                            row["total_price"],
                            row.get("currency") or "USD",
                            row.get("financial_status"),
                            row["attribution_type"],
                            row.get("employee_slug"),
                            row.get("utm_decision"),
                            row.get("source_url"),
                            row.get("last_landing_url"),
                            raw_json,
                            row.get("sync_run_id"),
                        ),
                    )
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"upsert_store_ops_order_attribution 失败: {e}", exc_info=True)
            return False

    def get_enabled_store_ops_shop_domains(self) -> List[str]:
        """读取店铺运营已启用的店铺白名单。

        报表入口与同步入口都应复用这里，避免再次出现
        “配置中心已加店，但 API / 同步仍看旧常量”的口径分叉。
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT shop_domain
                        FROM store_ops_shop_whitelist
                        WHERE is_enabled = 1
                        ORDER BY shop_domain ASC
                        """
                    )
                    rows = cursor.fetchall() or []
                    return [
                        str(row["shop_domain"]).strip()
                        for row in rows
                        if row.get("shop_domain")
                    ]
        except Exception as e:
            logger.error(
                "get_enabled_store_ops_shop_domains 失败: %s", e, exc_info=True
            )
            return []

    def fetch_store_ops_daily_buckets(
        self,
        shop_domains: List[str],
        date_start: date,
        date_end: date,
    ) -> List[Dict[str, Any]]:
        """
        按店、按业务日、按归因类型与员工 slug 聚合的金额与订单数（用于阶段二报表）。
        """
        if not shop_domains:
            return []
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    placeholders = ",".join(["%s"] * len(shop_domains))
                    sql = f"""
                        SELECT
                            shop_domain,
                            biz_date,
                            attribution_type,
                            COALESCE(NULLIF(employee_slug, ''), '') AS employee_slug,
                            SUM(total_price) AS sum_price,
                            COUNT(*) AS order_count
                        FROM store_ops_order_attributions
                        WHERE shop_domain IN ({placeholders})
                          AND biz_date >= %s AND biz_date <= %s
                        GROUP BY shop_domain, biz_date, attribution_type, employee_slug
                        ORDER BY shop_domain, biz_date, attribution_type, employee_slug
                    """
                    cursor.execute(
                        sql, tuple(shop_domains) + (date_start, date_end)
                    )
                    return list(cursor.fetchall())
        except Exception as e:
            logger.error(f"fetch_store_ops_daily_buckets 失败: {e}", exc_info=True)
            return []

    def fetch_store_ops_fb_spend_by_shop_slug(
        self,
        shop_domain: str,
        date_start: date,
        date_end: date,
    ) -> Dict[str, Decimal]:
        """按店铺在区间内，从 fb_campaign_spend_daily 聚合系列花费并归因到运营 slug。

        B.4 重写口径：
          - 数据源：`fb_campaign_spend_daily` 按店铺启用的白名单账户过滤
          - 归因：Python 层 `match_employee_by_campaign(campaign_name, operators)`
            按 `store_ops_employee_config.sort_order` 子串匹配 `campaign_keyword`
          - 返回：{slug: Decimal, "_unattributed": Decimal}
            - 命中的运营合并到对应 slug
            - 未命中的系列花费累加到特殊 key `_unattributed`
          - 主系统表（fb_ad_account_spend_hourly / ad_account_owner_mapping）不再参与读取
        """
        from app.services.store_ops_attribution import (
            get_active_operators,
            match_employee_by_campaign,
        )

        sd = (shop_domain or "").strip()
        if not sd:
            return {}

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT c.campaign_id,
                               c.campaign_name,
                               COALESCE(SUM(c.spend), 0) AS total_spend
                        FROM fb_campaign_spend_daily c
                        INNER JOIN store_ops_shop_ad_whitelist w
                                ON w.ad_account_id COLLATE utf8mb4_unicode_ci
                                 = c.ad_account_id COLLATE utf8mb4_unicode_ci
                               AND w.is_enabled = 1
                               AND w.shop_domain COLLATE utf8mb4_unicode_ci = %s
                        WHERE c.stat_date >= %s AND c.stat_date <= %s
                        GROUP BY c.campaign_id, c.campaign_name
                    """
                    cursor.execute(sql, (sd, date_start, date_end))
                    rows = cursor.fetchall() or []
        except Exception as e:
            logger.error(
                "fetch_store_ops_fb_spend_by_shop_slug 失败 shop=%s: %s",
                shop_domain, e, exc_info=True,
            )
            return {}

        try:
            operators = get_active_operators()
        except Exception as e:
            logger.warning(
                "fetch_store_ops_fb_spend_by_shop_slug 无法加载运营配置，按未归属处理 shop=%s: %s",
                shop_domain, e,
            )
            operators = []

        out: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for r in rows:
            camp_name = (r.get("campaign_name") or "").strip()
            raw_spend = r.get("total_spend")
            try:
                spend = Decimal(str(raw_spend)) if raw_spend is not None else Decimal("0")
            except Exception:
                spend = Decimal("0")
            if spend < 0:
                spend = Decimal("0")
            slug = match_employee_by_campaign(camp_name, operators=operators) if operators else None
            key = slug if slug else "_unattributed"
            out[key] += spend
        return dict(out)

    def insert_store_ops_sync_run_running(
        self,
        sync_run_id: str,
        shops: List[str],
        biz_dates: List[str],
    ) -> bool:
        """同步开始时写入 running。"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO store_ops_sync_runs (
                            sync_run_id, status, shops_json, biz_dates_json,
                            orders_seen, orders_upserted_paid, orders_skipped_not_paid,
                            error_count
                        ) VALUES (
                            %s, 'running', %s, %s, 0, 0, 0, 0
                        )
                    """
                    cursor.execute(
                        sql,
                        (
                            sync_run_id,
                            json.dumps(shops, ensure_ascii=False),
                            json.dumps(biz_dates, ensure_ascii=False),
                        ),
                    )
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"insert_store_ops_sync_run_running 失败: {e}", exc_info=True)
            return False

    def finalize_store_ops_sync_run_from_stats(self, sync_run_id: str, stats: Dict[str, Any]) -> bool:
        """
        同步正常返回后落库：success（无错）或 partial（有错但任务跑完）。
        """
        errors = stats.get("errors") or []
        err_n = len(errors)
        status = "success" if err_n == 0 else "partial"
        per_shop = stats.get("per_shop") or []
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        UPDATE store_ops_sync_runs SET
                            status = %s,
                            orders_seen = %s,
                            orders_upserted_paid = %s,
                            orders_skipped_not_paid = %s,
                            error_count = %s,
                            errors_json = %s,
                            per_shop_json = %s,
                            finished_at = CURRENT_TIMESTAMP
                        WHERE sync_run_id = %s
                    """
                    cursor.execute(
                        sql,
                        (
                            status,
                            int(stats.get("orders_seen") or 0),
                            int(stats.get("orders_upserted_paid") or 0),
                            int(stats.get("orders_skipped_not_paid") or 0),
                            err_n,
                            json.dumps(errors, ensure_ascii=False),
                            json.dumps(per_shop, ensure_ascii=False),
                            sync_run_id,
                        ),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"finalize_store_ops_sync_run_from_stats 失败: {e}", exc_info=True)
            return False

    def finalize_store_ops_sync_run_failed(
        self, sync_run_id: str, exception_message: str
    ) -> bool:
        """后台任务抛异常时标记 failed。"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
                        UPDATE store_ops_sync_runs SET
                            status = 'failed',
                            exception_message = %s,
                            finished_at = CURRENT_TIMESTAMP
                        WHERE sync_run_id = %s
                    """
                    cursor.execute(sql, (exception_message[:65000], sync_run_id))
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"finalize_store_ops_sync_run_failed 失败: {e}", exc_info=True)
            return False

    def get_store_ops_sync_run(self, sync_run_id: str) -> Optional[Dict[str, Any]]:
        """按 UUID 查询一条同步批次。"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            sync_run_id, status, shops_json, biz_dates_json,
                            orders_seen, orders_upserted_paid, orders_skipped_not_paid,
                            error_count, errors_json, per_shop_json, exception_message,
                            started_at, finished_at
                        FROM store_ops_sync_runs
                        WHERE sync_run_id = %s
                        """,
                        (sync_run_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return None
                    return self._normalize_store_ops_sync_run_row(row)
        except Exception as e:
            logger.error(f"get_store_ops_sync_run 失败: {e}", exc_info=True)
            return None

    def list_store_ops_sync_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """最近若干条同步批次（含 running 与已结束）。"""
        lim = max(1, min(int(limit), 100))
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            sync_run_id, status, shops_json, biz_dates_json,
                            orders_seen, orders_upserted_paid, orders_skipped_not_paid,
                            error_count, errors_json, per_shop_json, exception_message,
                            started_at, finished_at
                        FROM store_ops_sync_runs
                        ORDER BY started_at DESC
                        LIMIT %s
                        """,
                        (lim,),
                    )
                    rows = cursor.fetchall()
                    return [self._normalize_store_ops_sync_run_row(r) for r in rows]
        except Exception as e:
            logger.error(f"list_store_ops_sync_runs 失败: {e}", exc_info=True)
            return []

    def _normalize_store_ops_sync_run_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """JSON 列与 datetime 转为前端友好格式。"""
        out = dict(row)
        for k in ("shops_json", "biz_dates_json", "errors_json", "per_shop_json"):
            v = out.get(k)
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                continue
            if isinstance(v, bytes):
                v = v.decode("utf-8", errors="replace")
            if isinstance(v, str):
                try:
                    out[k] = json.loads(v)
                except json.JSONDecodeError:
                    out[k] = v
        for k in ("started_at", "finished_at"):
            t = out.get(k)
            if hasattr(t, "isoformat"):
                out[k] = t.isoformat(sep=" ", timespec="seconds")
        return out