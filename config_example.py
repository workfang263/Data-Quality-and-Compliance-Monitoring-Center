"""
配置文件模板（脱敏版本）
⚠️ 这是用于 GitHub 的模板文件，真实配置请使用 config.py（已加入 .gitignore）

使用方法：
1. 复制此文件为 config.py
2. 填入您的真实配置信息
3. 或者使用环境变量（推荐）
"""
import os
from typing import Dict, Any

# ==================== 数据库配置 ====================
# 优先从环境变量读取，如果没有则使用默认值（用于 Demo 模式）
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'shoplazza_user'),
    'password': os.getenv('DB_PASSWORD', 'demo_password'),  # ⚠️ Demo 模式默认密码
    'database': os.getenv('DB_NAME', 'shoplazza_dashboard'),
    'charset': 'utf8mb4'
}

# ==================== Streamlit配置 ====================
STREAMLIT_CONFIG = {
    'port': int(os.getenv('STREAMLIT_PORT', '8502')),
    'host': os.getenv('STREAMLIT_HOST', '0.0.0.0')  # 监听所有网络接口，支持局域网访问
}

# ==================== API配置 ====================
API_CONFIG = {
    'base_url_template': 'https://{shop_domain}/openapi/2022-01',
    'data_analysis_endpoint': '/data/analysis',
    'orders_endpoint': '/orders',
    'timeout': 30,  # 请求超时时间（秒）
    'max_retries': 2,  # 最大重试次数
    'retry_delay': 30,  # 重试间隔（秒）
    'page_limit': 200,  # 每页最大记录数
}

# ==================== 数据抓取配置 ====================
SYNC_CONFIG = {
    'tz': 8.0,  # 北京时间 UTC+8
    'filter_crawler_type': 'official_crawler',  # 过滤爬虫流量
    # 注意：不再使用 financial_status 筛选
    # 根据Shoplazza客服确认：
    # - 后台统计逻辑：统计周期内成功支付的订单数量，含已申请/申请中退款的订单（去掉COD订单）
    # - 因此不筛选 financial_status，直接使用 placed_at_min/placed_at_max 拉取
    # - 在代码中过滤COD订单和礼品卡订单
    'page_limit': 200,  # 每页最大记录数
    'data_retention_months': 3,  # 数据保留月数（已禁用自动清理，此参数不再使用，保留以便未来需要）
    
    # ========== 方案1+方案2：减少数据差异的配置 ==========
    # 方案1：同步时间延迟配置
    # 建议在Windows任务计划程序中设置为凌晨5点执行（而不是凌晨3点）
    # 这样可以给API足够的时间更新数据，减少数据延迟导致的差异
    'sync_hour': 5,  # 建议的同步时间（小时），例如5表示凌晨5点
    'sync_delay_hours': 2,  # 同步延迟小时数（相对于凌晨3点），例如2表示延迟到凌晨5点
    
    # 方案2：时间窗口扩展配置
    # 查询数据时扩大时间窗口，可以抓到边界订单，减少时间边界导致的差异
    'query_window_extension_hours': 2,  # 查询时间窗口扩展小时数（默认2小时，可调整为1-3）
    # 说明：
    # - 当查询28号数据时，实际查询范围为：28号 00:00:00 到 29号 02:00:00（扩展2小时）
    # - 但在统计和写入数据库时，只统计订单创建时间在28号范围内的数据
    # - 这样可以抓到那些在28号23:59创建、29号01:59之前支付的边界订单
    # - 建议值：1-3小时（超过3小时意义不大，还会增加API调用）
}

# ==================== 时区配置 ====================
TIMEZONE = 'Asia/Shanghai'  # 北京时间

# ==================== 日志配置 ====================
LOG_CONFIG = {
    'log_dir': 'logs',
    'log_file': 'logs/app.log',
    'max_bytes': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
    'rotation_midnight': '00:00',
    'retention': '30 days',
    'enable_json_log': False,
    'error_diagnose': False,
    'log_level': 'INFO'
}

# ==================== TikTok Marketing API 配置 ====================
# ⚠️ Demo 模式：如果环境变量不存在，使用模拟数据
TT_CONFIG = {
    # 代理配置（从环境变量读取，如果需要）
    'proxies': None,  # 默认不使用代理，可通过环境变量 HTTP_PROXY/HTTPS_PROXY 设置
    
    # API 基础配置
    'base_url': 'https://business-api.tiktok.com/open_api/v1.3',
    'timeout': 20,
    'max_retries': 2,
    'retry_delay': 30,
    
    # Business Center 账户配置
    # ⚠️ Demo 模式：所有 Token 和 ID 都使用占位符
    'business_centers': [
        {
            'name': 'Demo_Business_Center_01',  # 脱敏：原 'GARRY INTERNATIONAL TRADING CO.. LIMITED'
            'access_token': os.getenv('TIKTOK_ACCESS_TOKEN_1', 'your_tiktok_token_here'),  # ⚠️ 从环境变量读取
            'advertiser_ids': [
                'demo_advertiser_001',  # 脱敏：原真实 ID
                'demo_advertiser_002',
                'demo_advertiser_003',
                'demo_advertiser_004',
                'demo_advertiser_005',
            ]
        },
        {
            'name': 'Demo_Business_Center_02',  # 脱敏：原 'AlylikeFs01'
            'access_token': os.getenv('TIKTOK_ACCESS_TOKEN_2', 'your_tiktok_token_here'),  # ⚠️ 从环境变量读取
            'advertiser_ids': [
                'demo_advertiser_006',
                'demo_advertiser_007',
                'demo_advertiser_008',
                'demo_advertiser_009',
                'demo_advertiser_010',
            ]
        }
    ]
}

# ==================== Mock 模式配置 ====================
# 如果设置为 True，系统将返回模拟数据而不是调用真实 API
MOCK_MODE = os.getenv('MOCK_MODE', 'false').lower() == 'true'

