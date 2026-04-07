"""
店铺运营 / 员工归因：固定店铺列表、utm 白名单、环境变量中的 access-token 键名。
"""
import os
from typing import Dict, List

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
]

EMPLOYEE_SLUG_SET = frozenset(EMPLOYEE_SLUGS_ORDERED)

OPENAPI_VERSION_STORE_OPS = "2025-06"

# .env 中按店映射 token（仅本模块读取，不用 shoplazza_stores）
_ENV_TOKEN_BY_SHOP: Dict[str, str] = {
    "shutiaoes.myshoplaza.com": "SHOPLAZZA_ACCESS_TOKEN_SHUTIAOES",
    "newgges.myshoplaza.com": "SHOPLAZZA_ACCESS_TOKEN_NEWGGES",
}


def get_store_ops_token_for_shop(shop_domain: str) -> str:
    """从环境变量读取该店专用 token；未配置则返回空字符串。"""
    key = _ENV_TOKEN_BY_SHOP.get(shop_domain.strip())
    if not key:
        return ""
    return (os.getenv(key) or "").strip()
