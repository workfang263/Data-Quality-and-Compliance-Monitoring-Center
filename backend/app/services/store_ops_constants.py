"""
店铺运营 / 员工归因：固定店铺列表、utm 白名单、环境变量中的 access-token 键名。
"""
import logging
import os
from typing import Dict, List

from app.services.database_new import Database

logger = logging.getLogger(__name__)

# 与方案一致：两店数据绝不合并；同步与报表均按列表迭代
STORE_OPS_SHOP_DOMAINS: List[str] = [
    "shutiaoes.myshoplaza.com",
    "newgges.myshoplaza.com",
]

# utm 首段（第一个 '-' 之前）与白名单比对，大小写不敏感 → 统一存小写
EMPLOYEE_SLUGS_ORDERED: List[str] = [
    "xiaoyang",
    "kiki",
    "jieni",
    "amao",
    "jimi",
    "xiaozhang",
    "wanqiu",
    "quqi",
]

EMPLOYEE_SLUG_SET = frozenset(EMPLOYEE_SLUGS_ORDERED)

OPENAPI_VERSION_STORE_OPS = "2025-06"

# .env 中按店映射 token（仅保留短期兜底，不再是主链路事实来源）
_ENV_TOKEN_BY_SHOP: Dict[str, str] = {
    "shutiaoes.myshoplaza.com": "SHOPLAZZA_ACCESS_TOKEN_SHUTIAOES",
    "newgges.myshoplaza.com": "SHOPLAZZA_ACCESS_TOKEN_NEWGGES",
}


def _get_env_token_for_shop(shop_domain: str) -> str:
    key = _ENV_TOKEN_BY_SHOP.get(shop_domain)
    if not key:
        return ""
    return (os.getenv(key) or "").strip()


def get_store_ops_token_for_shop(shop_domain: str) -> str:
    """优先读主系统表 token，缺失时短期 fallback 到 env。"""
    normalized_shop = (shop_domain or "").strip()
    if not normalized_shop:
        return ""

    db_token = Database().get_store_access_token(normalized_shop)
    if db_token:
        return db_token

    env_token = _get_env_token_for_shop(normalized_shop)
    if env_token:
        logger.info("store_ops token 使用 env fallback: %s", normalized_shop)
    return env_token
