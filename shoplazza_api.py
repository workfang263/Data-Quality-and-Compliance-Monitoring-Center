"""
Shoplazza API 调用模块
"""
import requests
import logging
import time
import urllib3
from typing import Dict, Any, List, Optional
from datetime import datetime
from config import API_CONFIG, SYNC_CONFIG

# 禁用SSL警告（用于内网环境）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class ShoplazzaAPI:
    """Shoplazza API 调用类"""
    
    def __init__(self, shop_domain: str, access_token: str):
        """
        初始化API客户端
        
        Args:
            shop_domain: 店铺域名（例如：jaymiart.myshoplaza.com）
            access_token: API访问令牌
        """
        # 清理域名，移除 https:// 和末尾的 /
        shop_domain = shop_domain.replace('https://', '').replace('http://', '').rstrip('/')
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.base_url = API_CONFIG['base_url_template'].format(shop_domain=shop_domain)
        # 使用正确的认证方式（根据Shoplazza文档）
        self.headers = {
            'Access-Token': access_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        # 记录最后一次API失败信息（用于自动禁用店铺）
        self._last_api_failure = None
        # 单次 _make_request 内连续两次 HTTP 404 时置位，由 data_sync 调用 disable_store
        self._auto_disable_double_404 = False
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     max_retries: int = None) -> Optional[Dict[str, Any]]:
        """
        发送API请求
        
        Args:
            method: HTTP方法（GET/POST）
            endpoint: API端点路径
            params: 请求参数
            max_retries: 最大重试次数
            
        Returns:
            API响应数据，失败返回None
        """
        if max_retries is None:
            max_retries = API_CONFIG['max_retries']
        
        url = f"{self.base_url}{endpoint}"
        consecutive_404 = 0
        
        for attempt in range(max_retries + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    timeout=API_CONFIG['timeout'],
                    verify=False  # 禁用SSL验证（内网环境）
                )
                status_code = response.status_code
                
                if status_code == 404:
                    consecutive_404 += 1
                    err_text = f"404 Client Error: Not Found for url: {url}"
                    self._last_api_failure = {
                        'url': url,
                        'error': err_text,
                        'endpoint': endpoint,
                        'status_code': 404,
                    }
                    if consecutive_404 >= 2:
                        self._auto_disable_double_404 = True
                        logger.warning(
                            f"店铺 {self.shop_domain} OpenAPI 连续两次返回 HTTP 404，"
                            f"已标记自动禁用: {endpoint}"
                        )
                        return None
                    if attempt < max_retries:
                        wait_time = API_CONFIG['retry_delay'] * (attempt + 1)
                        logger.warning(
                            f"API返回404（尝试 {attempt + 1}/{max_retries + 1}）: {url}，{wait_time}秒后重试"
                        )
                        time.sleep(wait_time)
                        continue
                    logger.error(
                        f"API请求最终失败（重试{max_retries}次后仍失败）: {url}, 错误: {err_text}"
                    )
                    return None
                
                consecutive_404 = 0
                response.raise_for_status()
                self._last_api_failure = None
                return response.json()
            except requests.exceptions.RequestException as e:
                consecutive_404 = 0
                if attempt < max_retries:
                    wait_time = API_CONFIG['retry_delay'] * (attempt + 1)
                    logger.warning(f"API请求失败（尝试 {attempt + 1}/{max_retries + 1}）: {e}，{wait_time}秒后重试")
                    time.sleep(wait_time)
                else:
                    # 记录最后一次失败的信息，用于后续禁用店铺
                    self._last_api_failure = {
                        'url': url,
                        'error': str(e),
                        'endpoint': endpoint
                    }
                    logger.error(f"API请求最终失败（重试{max_retries}次后仍失败）: {url}, 错误: {e}")
                    return None
    
    def get_data_analysis(self, begin_time: int, end_time: int, 
                         dt_by: str = 'dt_by_hour', page: int = 1, 
                         limit: int = 200, indicator: list = None,
                         filter_crawler_type: str = None,
                         max_retries: int = None) -> Optional[Dict[str, Any]]:
        """
        调用数据分析接口
        
        Args:
            begin_time: 起始时间戳（Unix时间戳，秒）
            end_time: 结束时间戳（Unix时间戳，秒）
            dt_by: 时间粒度（dt_by_hour 或 dt_by_day）
            page: 页码
            limit: 每页记录数（最大200）
            indicator: 指标列表，例如 ['uv', 'orders', 'sales']，默认 ['uv']（只获取访客数）
            filter_crawler_type: 爬虫流量过滤类型，None或空字符串表示不过滤爬虫流量
            
        Returns:
            API响应数据
        """
        if indicator is None:
            indicator = ['uv']  # 默认只获取访客数
        
        params = {
            'begin_time': begin_time,
            'end_time': end_time,
            'tz': SYNC_CONFIG['tz'],
            'dt_by': dt_by,
            'indicator': indicator,  # 必需参数
            'page': str(page),  # 必须显式传递，且为字符串格式
            'limit': str(min(limit, API_CONFIG['page_limit']))  # 字符串格式
        }
        
        # 如果指定了filter_crawler_type，添加到参数中
        # 如果为None或空字符串，不传此参数（不过滤爬虫流量）
        if filter_crawler_type is not None and filter_crawler_type != '':
            params['filter_crawler_type'] = filter_crawler_type
        
        return self._make_request('GET', API_CONFIG['data_analysis_endpoint'], params, max_retries=max_retries)
    
    def get_data_analysis_all_pages(self, begin_time: int, end_time: int,
                                    dt_by: str = 'dt_by_hour', indicator: list = None,
                                    filter_crawler_type: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取数据分析接口的所有分页数据（自动翻页）
        
        Args:
            begin_time: 起始时间戳
            end_time: 结束时间戳
            dt_by: 时间粒度
            indicator: 指标列表，默认 ['uv']（只获取访客数）
            filter_crawler_type: 爬虫流量过滤类型，None或空字符串表示不过滤爬虫流量
        
        Returns:
            所有页面的数据列表
        """
        if indicator is None:
            indicator = ['uv']  # 默认只获取访客数
        
        all_data = []
        page = 1
        limit = API_CONFIG['page_limit']
        
        while True:
            # 清除之前的失败标记
            self._last_api_failure = None
            response = self.get_data_analysis(begin_time, end_time, dt_by, page, limit, indicator, filter_crawler_type)
            
            # 如果response是None，说明API调用失败（重试后仍失败）
            if not response:
                # 检查是否是API失败
                if self._last_api_failure and page == 1:
                    # 第一页就失败，返回None表示API调用失败
                    return None
                # 如果不是第一页，说明之前成功过，可能是后续页面失败
                break
            
            # 提取数据
            data_list = response.get('data', [])
            if not data_list:
                break
            
            all_data.extend(data_list)
            
            # 检查是否还有下一页
            total_count = response.get('count', 0)
            current_count = len(all_data)
            
            if current_count >= total_count:
                break
            
            page += 1
            time.sleep(0.5)  # 避免请求过快
        
        logger.info(f"店铺 {self.shop_domain} 获取到 {len(all_data)} 条数据分析记录")
        return all_data
    
    def get_orders(self, placed_at_min: str = None, placed_at_max: str = None,
                   created_at_min: str = None, created_at_max: str = None,
                   page: int = 1, limit: int = 200) -> Optional[Dict[str, Any]]:
        """
        调用订单列表接口
        
        优先使用 placed_at 参数（按支付时间查询，与数据概览一致）
        如果未提供 placed_at 参数，则使用 created_at 参数（向后兼容）
        
        重要说明（根据Shoplazza客服确认）：
        - 不筛选 financial_status，直接使用 placed_at_min/placed_at_max 拉取
        - 后台统计逻辑：统计周期内成功支付的订单数量，含已申请/申请中退款的订单（去掉COD订单）
        - 因此需要包含所有已支付订单（包括退款订单），在代码中过滤COD订单和礼品卡订单
        
        Args:
            placed_at_min: 订单支付起始时间（ISO 8601格式，北京时间）- 推荐使用
            placed_at_max: 订单支付结束时间（ISO 8601格式，北京时间）- 推荐使用
            created_at_min: 订单创建起始时间（ISO 8601格式，北京时间）- 向后兼容
            created_at_max: 订单创建结束时间（ISO 8601格式，北京时间）- 向后兼容
            page: 页码
            limit: 每页记录数（最大200）
            
        Returns:
            API响应数据
        """
        params = {
            # 移除 financial_status 参数
            # 根据客服建议：直接使用 placed_at_min 和 placed_at_max 拉取即可
            # 后台统计逻辑包含已申请/申请中退款的订单，所以不筛选 financial_status
            'page': str(page),  # 字符串格式
            'limit': str(min(limit, API_CONFIG['page_limit']))  # 字符串格式
        }
        
        # 优先使用 placed_at 参数（按支付时间查询，与数据概览一致）
        if placed_at_min and placed_at_max:
            params['placed_at_min'] = placed_at_min
            params['placed_at_max'] = placed_at_max
        elif created_at_min and created_at_max:
            # 向后兼容：如果没有提供 placed_at 参数，使用 created_at 参数
            params['created_at_min'] = created_at_min
            params['created_at_max'] = created_at_max
        else:
            raise ValueError("必须提供 placed_at 或 created_at 参数")
        
        return self._make_request('GET', API_CONFIG['orders_endpoint'], params)
    
    def get_orders_all_pages(self, placed_at_min: str = None, placed_at_max: str = None,
                            created_at_min: str = None, created_at_max: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取订单列表接口的所有分页数据（自动翻页）
        
        优先使用 placed_at 参数（按支付时间查询，与数据概览一致）
        
        Args:
            placed_at_min: 订单支付起始时间（ISO 8601格式，北京时间）- 推荐使用
            placed_at_max: 订单支付结束时间（ISO 8601格式，北京时间）- 推荐使用
            created_at_min: 订单创建起始时间（ISO 8601格式，北京时间）- 向后兼容
            created_at_max: 订单创建结束时间（ISO 8601格式，北京时间）- 向后兼容
        
        Returns:
            所有页面的订单列表，如果API调用失败返回None（而不是空列表），用于区分"没有数据"和"API失败"
        """
        all_orders = []
        page = 1
        limit = API_CONFIG['page_limit']
        
        while True:
            # 清除之前的失败标记
            self._last_api_failure = None
            response = self.get_orders(
                placed_at_min=placed_at_min,
                placed_at_max=placed_at_max,
                created_at_min=created_at_min,
                created_at_max=created_at_max,
                page=page,
                limit=limit
            )
            
            # 如果response是None，说明API调用失败（重试后仍失败）
            if not response:
                # 检查是否是API失败
                if self._last_api_failure and page == 1:
                    # 第一页就失败，返回None表示API调用失败
                    return None
                # 如果不是第一页，说明之前成功过，可能是后续页面失败
                break
            
            # 提取订单数据
            orders = response.get('orders', [])
            if not orders:
                # 没有订单了，退出
                break
            
            all_orders.extend(orders)
            
            # ⭐ 关键修复：完全依赖返回的订单数量判断是否还有下一页（不依赖count字段）
            # count字段可能不准确，会导致订单遗漏
            # 只有当返回的订单数 < limit 时，才确定是最后一页
            
            # 如果返回的订单数 < limit，说明已经是最后一页，退出
            if len(orders) < limit:
                logger.debug(
                    f"店铺 {self.shop_domain} 第{page}页返回{len(orders)}条订单（小于limit={limit}），"
                    f"已是最后一页，总共获取{len(all_orders)}条订单"
                )
                break
            
            # 如果返回的订单数 == limit，继续获取下一页（不管count字段）
            # 这样可以确保获取所有订单，即使count字段不准确
            total_count = response.get('count', 0)
            logger.debug(
                f"店铺 {self.shop_domain} 第{page}页: "
                f"返回{len(orders)}条订单 (=limit), API count={total_count}, 已累计获取{len(all_orders)}条订单，"
                f"继续获取下一页（不依赖count字段判断）"
            )
            
            # 记录count字段信息（用于调试，但不用于判断）
            if total_count > 0 and len(all_orders) > total_count:
                # 已获取数量 > count，说明count不准确，记录警告但继续获取
                logger.warning(
                    f"店铺 {self.shop_domain} 第{page}页: "
                    f"已获取订单数({len(all_orders)}) > API返回count({total_count})，"
                    f"count字段不准确，继续获取下一页以确保获取所有订单"
                )
            
            page += 1
            time.sleep(0.5)  # 避免请求过快
        
        logger.info(f"店铺 {self.shop_domain} 获取到 {len(all_orders)} 条订单记录（分{page}页）")
        return all_orders

