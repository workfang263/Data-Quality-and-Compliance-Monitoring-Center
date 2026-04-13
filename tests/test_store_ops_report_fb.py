"""
店铺运营报表：FB 花费与 ROAS 合并逻辑单测。
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.services.store_ops_report import merge_fb_spend_into_payload


def test_merge_fb_spend_roas_zero_spend_shows_null_roas():
    payload = {
        "shops": [
            {
                "shop_domain": "shutiaoes.myshoplaza.com",
                "employee_rows": [
                    {
                        "employee_slug": "amao",
                        "total_sales": 100.0,
                        "direct_sales": 100.0,
                        "allocated_from_public_pool": 0.0,
                        "direct_order_count": 1,
                    }
                ],
            }
        ]
    }
    spend = {"shutiaoes.myshoplaza.com": {"amao": Decimal("0")}}
    merge_fb_spend_into_payload(payload, spend)
    row = payload["shops"][0]["employee_rows"][0]
    assert row["fb_spend"] == 0.0
    assert row["roas"] is None


def test_merge_fb_spend_roas_positive_spend_zero_sales():
    payload = {
        "shops": [
            {
                "shop_domain": "newgges.myshoplaza.com",
                "employee_rows": [
                    {
                        "employee_slug": "jimi",
                        "total_sales": 0.0,
                        "direct_sales": 0.0,
                        "allocated_from_public_pool": 0.0,
                        "direct_order_count": 0,
                    }
                ],
            }
        ]
    }
    spend = {"newgges.myshoplaza.com": {"jimi": Decimal("50.00")}}
    merge_fb_spend_into_payload(payload, spend)
    row = payload["shops"][0]["employee_rows"][0]
    assert row["fb_spend"] == 50.0
    assert row["roas"] == 0.0


def test_merge_fb_spend_roas_normal_ratio():
    payload = {
        "shops": [
            {
                "shop_domain": "shutiaoes.myshoplaza.com",
                "employee_rows": [
                    {
                        "employee_slug": "xiaoyang",
                        "total_sales": 100.0,
                        "direct_sales": 100.0,
                        "allocated_from_public_pool": 0.0,
                        "direct_order_count": 2,
                    }
                ],
            }
        ]
    }
    spend = {"shutiaoes.myshoplaza.com": {"xiaoyang": Decimal("40")}}
    merge_fb_spend_into_payload(payload, spend)
    row = payload["shops"][0]["employee_rows"][0]
    assert row["fb_spend"] == 40.0
    assert row["roas"] == 2.5
