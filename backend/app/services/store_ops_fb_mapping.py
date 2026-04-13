"""
店铺运营报表：Facebook 广告账户与店铺、员工 slug 的映射。

与 db/migrations/20260408_fb_ad_accounts_sunelva_bertlove_batch.sql 保持一致；
增删账户时请同步修改迁移/映射表与本模块。
"""
from __future__ import annotations

from typing import Dict, List

from app.services.store_ops_constants import STORE_OPS_SHOP_DOMAINS

# Sunelva 批次 → 店铺2 newgges
_FB_ACT_IDS_SUNELVA: List[str] = [
    "act_1251009527180377",
    "act_1477243063804898",
    "act_832525359903650",
    "act_882617628155388",
    "act_971610118743796",
    "act_1419981400142746",
    "act_875355238849957",
]

# Bertlove 批次 → 店铺1 shutiaoes
_FB_ACT_IDS_BERTLOVE: List[str] = [
    "act_4395028554063117",
    "act_1619760595811637",
    "act_1023279760861216",
    "act_1222839759338297",
    "act_925374940441429",
    "act_879029751433363",
    "act_1220832883465993",
    "act_1337449094814463",
    "act_1221981739454062",
    "act_909816892005999",
]

# shutiaoes = 店铺1, newgges = 店铺2（与 STORE_OPS_SHOP_DOMAINS 顺序一致）
STORE_OPS_FB_ACT_IDS_BY_SHOP: Dict[str, List[str]] = {
    STORE_OPS_SHOP_DOMAINS[0]: list(_FB_ACT_IDS_BERTLOVE),
    STORE_OPS_SHOP_DOMAINS[1]: list(_FB_ACT_IDS_SUNELVA),
}

# ad_account_owner_mapping.owner（中文）→ employee_slug；「无」不入表
STORE_OPS_OWNER_CN_TO_SLUG: Dict[str, str] = {
    "小杨": "xiaoyang",
    "kiki": "kiki",
    "杰尼": "jieni",
    "阿毛": "amao",
    "基米": "jimi",
    "校长": "xiaozhang",
    "晚秋": "wanqiu",
}
