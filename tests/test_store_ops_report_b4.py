"""
B.4 阶段：store_ops_report 动态运营名单 + _unattributed 合并行为 单测。

覆盖点：
  1. 新字段 unattributed_fb_spend 正确透出（来自 spend 字典的 _unattributed key）
  2. active_operators 注入后，员工行按 sort_order 顺序出现
  3. 历史 slug（buckets 有、active 没有）不丢失
  4. 当日无直销时，公共池按 active 名单长度均摊；历史 slug 不参与
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from decimal import Decimal

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
for p in (_ROOT, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from app.services import store_ops_attribution as attr_mod
from app.services.store_ops_report import (
    build_store_ops_report_payload,
    merge_fb_spend_into_payload,
)


_FIXTURE_OPS = [
    {"id": 1, "employee_slug": "amao", "utm_keyword": "amao",
     "campaign_keyword": "amao-", "sort_order": 10},
    {"id": 2, "employee_slug": "jimi", "utm_keyword": "jimi",
     "campaign_keyword": "jimi-", "sort_order": 20},
    {"id": 3, "employee_slug": "xiaoyang", "utm_keyword": "xiaoyang",
     "campaign_keyword": "__unset_xiaoyang", "sort_order": 30},
]


@pytest.fixture(autouse=True)
def _mock_active_ops(monkeypatch):
    """所有 test 默认用 fixture 运营列表，隔离真实 DB。"""
    monkeypatch.setattr(
        attr_mod,
        "get_active_operators",
        lambda: [dict(op) for op in _FIXTURE_OPS],
    )
    attr_mod.reset_cache_for_tests()
    yield


# ============ merge 行为 ============

class TestUnattributedField:
    def _make_payload(self, shop: str = "shop_a.com") -> dict:
        return {
            "shops": [
                {
                    "shop_domain": shop,
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

    def test_unattributed_zero_when_absent(self):
        payload = self._make_payload()
        spend = {"shop_a.com": {"amao": Decimal("10")}}
        merge_fb_spend_into_payload(payload, spend)
        assert payload["shops"][0]["unattributed_fb_spend"] == 0.0
        assert payload["shops"][0]["employee_rows"][0]["fb_spend"] == 10.0

    def test_unattributed_extracted_correctly(self):
        payload = self._make_payload()
        spend = {
            "shop_a.com": {
                "amao": Decimal("20"),
                "_unattributed": Decimal("55.50"),
            }
        }
        merge_fb_spend_into_payload(payload, spend)
        shop = payload["shops"][0]
        assert shop["unattributed_fb_spend"] == 55.50
        assert shop["employee_rows"][0]["fb_spend"] == 20.0

    def test_unattributed_negative_clamped(self):
        payload = self._make_payload()
        spend = {"shop_a.com": {"_unattributed": Decimal("-99")}}
        merge_fb_spend_into_payload(payload, spend)
        assert payload["shops"][0]["unattributed_fb_spend"] == 0.0

    def test_unattributed_not_injected_into_employee_rows(self):
        """_unattributed 不应被当作某个员工的 slug 写入 employee_rows.fb_spend。"""
        payload = self._make_payload()
        spend = {
            "shop_a.com": {"amao": Decimal("10"), "_unattributed": Decimal("99")}
        }
        merge_fb_spend_into_payload(payload, spend)
        slugs = {r["employee_slug"] for r in payload["shops"][0]["employee_rows"]}
        assert "_unattributed" not in slugs


# ============ build payload 动态行为 ============

class TestDynamicOperators:
    @staticmethod
    def _bucket(shop, biz_date, slug, amount, orders=1, public=False):
        return {
            "shop_domain": shop,
            "biz_date": biz_date,
            "attribution_type": "public_pool" if public else "employee",
            "employee_slug": None if public else slug,
            "sum_price": amount,
            "order_count": orders,
        }

    def test_active_operators_drive_rows(self):
        bd = dt.date(2026, 4, 21)
        buckets = [self._bucket("shop_a.com", bd, "amao", 100)]
        payload = build_store_ops_report_payload(
            ["shop_a.com"], bd, bd, buckets, active_operators=_FIXTURE_OPS,
        )
        rows = payload["shops"][0]["employee_rows"]
        slugs = [r["employee_slug"] for r in rows]
        assert slugs == ["amao", "jimi", "xiaoyang"]

    def test_historical_slug_preserved(self):
        """buckets 含已离职 slug leaver，但不在 active 名单里 -> 应保留其行。"""
        bd = dt.date(2026, 4, 21)
        buckets = [
            self._bucket("shop_a.com", bd, "amao", 50),
            self._bucket("shop_a.com", bd, "leaver_ghost", 30, orders=2),
        ]
        payload = build_store_ops_report_payload(
            ["shop_a.com"], bd, bd, buckets, active_operators=_FIXTURE_OPS,
        )
        rows = payload["shops"][0]["employee_rows"]
        slugs = [r["employee_slug"] for r in rows]
        assert slugs[: len(_FIXTURE_OPS)] == ["amao", "jimi", "xiaoyang"]
        assert "leaver_ghost" in slugs
        leaver_row = next(r for r in rows if r["employee_slug"] == "leaver_ghost")
        assert leaver_row["direct_sales"] == 30.0
        assert leaver_row["direct_order_count"] == 2

    def test_public_pool_even_split_uses_active_count(self):
        """当日无直销：公共池均摊分母 = active 数量（不是硬编码 8，不是包含历史的总数）。"""
        bd = dt.date(2026, 4, 21)
        buckets = [
            self._bucket("shop_a.com", bd, None, 300, orders=3, public=True),
        ]
        payload = build_store_ops_report_payload(
            ["shop_a.com"], bd, bd, buckets, active_operators=_FIXTURE_OPS,
        )
        rows = payload["shops"][0]["employee_rows"]
        total_allocated = sum(r["allocated_from_public_pool"] for r in rows)
        assert abs(total_allocated - 300.0) < 0.01
        per = 300.0 / len(_FIXTURE_OPS)
        for r in rows:
            assert abs(r["allocated_from_public_pool"] - per) < 0.01

    def test_historical_slug_not_in_public_pool_split(self):
        bd = dt.date(2026, 4, 21)
        buckets = [
            self._bucket("shop_a.com", bd, None, 300, orders=3, public=True),
            self._bucket("shop_a.com", dt.date(2026, 4, 20), "leaver", 10),
        ]
        payload = build_store_ops_report_payload(
            ["shop_a.com"], dt.date(2026, 4, 20), bd, buckets,
            active_operators=_FIXTURE_OPS,
        )
        rows = payload["shops"][0]["employee_rows"]
        leaver = next(r for r in rows if r["employee_slug"] == "leaver")
        assert leaver["direct_sales"] == 10.0
        assert leaver["allocated_from_public_pool"] == 0.0

    def test_totals_conserved(self):
        """多日多员工场景：sum(direct_sales) + sum(allocated_from_public_pool)
        应等于 sum(buckets)。"""
        bd1 = dt.date(2026, 4, 20)
        bd2 = dt.date(2026, 4, 21)
        buckets = [
            self._bucket("shop_a.com", bd1, "amao", 100),
            self._bucket("shop_a.com", bd1, "jimi", 50),
            self._bucket("shop_a.com", bd1, None, 75, orders=2, public=True),
            self._bucket("shop_a.com", bd2, "xiaoyang", 40),
            self._bucket("shop_a.com", bd2, None, 60, orders=1, public=True),
        ]
        payload = build_store_ops_report_payload(
            ["shop_a.com"], bd1, bd2, buckets, active_operators=_FIXTURE_OPS,
        )
        rows = payload["shops"][0]["employee_rows"]
        total_direct = sum(r["direct_sales"] for r in rows)
        total_alloc = sum(r["allocated_from_public_pool"] for r in rows)
        grand = total_direct + total_alloc
        expected = 100 + 50 + 75 + 40 + 60
        assert abs(grand - expected) < 0.01
