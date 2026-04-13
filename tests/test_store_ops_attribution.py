"""
店铺运营：match_employee_slug 子串匹配与 resolve_attribution 回归。

运行（项目根目录）：
    python -m pytest tests/test_store_ops_attribution.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.services.store_ops_attribution import (
    match_employee_slug,
    resolve_attribution,
)
from app.services.store_ops_constants import EMPLOYEE_SLUGS_ORDERED


class TestMatchEmployeeSlug:
    def test_legacy_prefix_with_dash(self):
        assert match_employee_slug("jieni-promo") == "jieni"

    def test_no_dash_substring(self):
        assert match_employee_slug("promo_jieni_nocode") == "jieni"

    def test_multiple_slugs_list_order_wins(self):
        # kiki 在 EMPLOYEE_SLUGS_ORDERED 中早于 jieni，两段子串均存在时取 kiki
        assert match_employee_slug("xx_kiki_yy_jieni_zz") == "kiki"

    def test_jieni_only_when_kiki_absent(self):
        assert match_employee_slug("sale_jieni_final") == "jieni"

    def test_empty_and_none(self):
        assert match_employee_slug(None) is None
        assert match_employee_slug("") is None
        assert match_employee_slug("   ") is None

    def test_no_employee_substring(self):
        assert match_employee_slug("facebook_organic") is None

    def test_case_insensitive(self):
        assert match_employee_slug("Promo_JieNi_X") == "jieni"

    def test_xiaoyang_before_kiki_in_order(self):
        hay = "prefix_xiaoyang_suffix_kiki"
        assert match_employee_slug(hay) == "xiaoyang"


class TestResolveAttributionIntegration:
    def test_first_touch_only_embedded_slug(self):
        src = "https://shop.com/?utm_source=campaign_jieni_extra"
        att, slug, dec = resolve_attribution(src, None)
        assert att == "employee"
        assert slug == "jieni"
        assert dec == "first"

    def test_last_branch_prefers_last_utm(self):
        first = "https://a.com/?utm_source=wanqiu_old"
        last = "https://b.com/p?utm_source=kiki_new"
        att, slug, dec = resolve_attribution(first, last)
        assert att == "employee"
        assert slug == "kiki"
        assert dec == "last"

    def test_last_branch_fallback_to_first(self):
        first = "https://a.com/?utm_source=jimi_campaign"
        last = "https://b.com/p?utm_source=unknown_text"
        att, slug, dec = resolve_attribution(first, last)
        assert att == "employee"
        assert slug == "jimi"
        assert dec == "first_fallback"

    def test_public_when_no_match(self):
        att, slug, dec = resolve_attribution(
            "https://a.com/?utm_source=organic",
            None,
        )
        assert att == "public_pool"
        assert slug is None
        assert dec == "public"


def test_employee_order_constant_length():
    assert len(EMPLOYEE_SLUGS_ORDERED) == 7
