"""
数据库连接和操作模块
"""
import pymysql
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, date
from config import DB_CONFIG

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
                autocommit=False
            )
            return connection
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
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
                          AND shop_domain NOT LIKE '%test%'  -- 过滤测试店铺
                        ORDER BY id
                    """
                    cursor.execute(sql)
                    stores = cursor.fetchall()
                    logger.info(f"获取到 {len(stores)} 个启用店铺（已过滤测试店铺）")
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
                    # 参数顺序说明：
                    # 1. params_sales - 用于 shoplazza_overview_hourly 表的 WHERE 条件
                    # 2. params_spend - 用于 fb_ad_account_spend_hourly 表的 WHERE 条件
                    # 3. params_spend - 用于 tt_ad_account_spend_hourly 表的 WHERE 条件
                    sql = f"""
                        SELECT 
                            t.time_hour,
                            SUM(t.total_gmv)      AS total_gmv,
                            SUM(t.total_orders)   AS total_orders,
                            SUM(t.total_visitors) AS total_visitors,
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
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取带花费的小时数据失败: {e}")
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
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = """
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
                    cursor.execute(sql, (start_time, end_time))
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取带花费的天数据失败: {e}")
            return []

    def get_owner_daily_summary(self, start_date: date, end_date: date,
                                sort_by: str = 'owner', sort_order: str = 'asc') -> List[Dict[str, Any]]:
        """
        获取负责人维度的日汇总（合并多日）。
        数据源：owner_daily_summary
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
                    sql = f"""
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
                    cursor.execute(sql, (start_date, end_date))
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取负责人日汇总失败: {e}")
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
                        store_sql = """
                            SELECT 
                                owner,
                                SUM(total_gmv) as total_gmv,
                                SUM(total_orders) as total_orders,
                                SUM(total_visitors) as total_visitors
                            FROM shoplazza_store_hourly
                            WHERE DATE(time_hour) = %s
                              AND owner IS NOT NULL
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


