"""
店铺运营：match_employee_slug 子串匹配与 resolve_attribution 回归。

B.2 重构后，归因读路径已切到数据库：
- 所有用例通过 autouse fixture 注入固定的 operators 列表来模拟 DB 状态
- 该 fixture 反映"已执行 UPDATE quqi.utm_keyword='cookie'"后的生产状态
- 同时覆盖新增函数 match_employee_by_campaign 的行为

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

from app.services import store_ops_attribution as attr_mod
from app.services.store_ops_attribution import (
    match_employee_by_campaign,
    match_employee_slug,
    resolve_attribution,
)
from app.services.store_ops_constants import EMPLOYEE_SLUGS_ORDERED


# 模拟 store_ops_employee_config 的生产快照：quqi.utm_keyword='cookie'，
# 其他运营 utm_keyword = slug 本身；按 sort_order 递增排序
_FIXTURE_OPERATORS = [
    {"id": 1, "employee_slug": "xiaoyang",  "utm_keyword": "xiaoyang",  "campaign_keyword": "__unset_xiaoyang",  "sort_order": 10},
    {"id": 2, "employee_slug": "kiki",      "utm_keyword": "kiki",      "campaign_keyword": "__unset_kiki",      "sort_order": 20},
    {"id": 3, "employee_slug": "jieni",     "utm_keyword": "jieni",     "campaign_keyword": "__unset_jieni",     "sort_order": 30},
    {"id": 4, "employee_slug": "amao",      "utm_keyword": "amao",      "campaign_keyword": "__unset_amao",      "sort_order": 40},
    {"id": 5, "employee_slug": "jimi",      "utm_keyword": "jimi",      "campaign_keyword": "__unset_jimi",      "sort_order": 50},
    {"id": 6, "employee_slug": "xiaozhang", "utm_keyword": "xiaozhang", "campaign_keyword": "__unset_xiaozhang", "sort_order": 60},
    {"id": 7, "employee_slug": "wanqiu",    "utm_keyword": "wanqiu",    "campaign_keyword": "__unset_wanqiu",    "sort_order": 70},
    {"id": 8, "employee_slug": "quqi",      "utm_keyword": "cookie",    "campaign_keyword": "__unset_quqi",      "sort_order": 80},
]


@pytest.fixture(autouse=True)
def _mock_active_operators(monkeypatch):
    """所有测试统一使用固定运营列表，避免依赖 DB。每个用例前清空缓存。"""
    monkeypatch.setattr(
        attr_mod,
        "get_active_operators",
        lambda: [dict(op) for op in _FIXTURE_OPERATORS],
    )
    attr_mod.reset_cache_for_tests()
    yield


class TestMatchEmployeeSlug:
    def test_legacy_prefix_with_dash(self):
        assert match_employee_slug("jieni-promo") == "jieni"

    def test_no_dash_substring(self):
        assert match_employee_slug("promo_jieni_nocode") == "jieni"

    def test_multiple_slugs_list_order_wins(self):
        # kiki(sort=20) 早于 jieni(sort=30)，两段子串均存在时取 kiki
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

    def test_cookie_maps_to_quqi(self):
        # 新版：靠 quqi.utm_keyword='cookie' 行数据承担，而非代码硬编码
        assert match_employee_slug("cookie") == "quqi"
        assert match_employee_slug("Promo-Cookie-2026") == "quqi"

    def test_other_slug_priority_over_cookie(self):
        # jieni(sort=30) 早于 quqi(sort=80)，串中同时有 jieni 与 cookie 时取 jieni
        assert match_employee_slug("jieni_cookie_mix") == "jieni"

    def test_bare_quqi_no_longer_matches(self):
        # B.2 口径变更：utm_keyword 由 'quqi' 改为 'cookie'，裸 "quqi" 子串不再命中
        assert match_employee_slug("promo_quqi_only") is None

    def test_injected_operators_override_cache(self):
        # 直接传入 operators 应绕过缓存/默认查询，按传入列表匹配
        custom = [
            {"id": 1, "employee_slug": "solo", "utm_keyword": "solo", "campaign_keyword": "", "sort_order": 1},
        ]
        assert match_employee_slug("prefix_solo_suffix", operators=custom) == "solo"
        assert match_employee_slug("prefix_kiki_suffix", operators=custom) is None


class TestMatchEmployeeByCampaign:
    def test_none_and_empty(self):
        assert match_employee_by_campaign(None) is None
        assert match_employee_by_campaign("") is None
        assert match_employee_by_campaign("   ") is None

    def test_unset_placeholder_skipped(self):
        # 默认 fixture 中所有 campaign_keyword 都是 __unset_* 占位符，应全部跳过
        assert match_employee_by_campaign("Campaign_jieni_2026") is None

    def test_matches_configured_keyword(self):
        custom = [
            {"id": 1, "employee_slug": "jieni", "utm_keyword": "jieni", "campaign_keyword": "促销王", "sort_order": 10},
            {"id": 2, "employee_slug": "kiki",  "utm_keyword": "kiki",  "campaign_keyword": "节日款", "sort_order": 20},
        ]
        assert match_employee_by_campaign("双11_促销王_男鞋", operators=custom) == "jieni"
        assert match_employee_by_campaign("春季_节日款_新品", operators=custom) == "kiki"
        assert match_employee_by_campaign("通用_无关键词_广告", operators=custom) is None

    def test_sort_order_priority(self):
        custom = [
            {"id": 1, "employee_slug": "a", "utm_keyword": "a", "campaign_keyword": "促销", "sort_order": 10},
            {"id": 2, "employee_slug": "b", "utm_keyword": "b", "campaign_keyword": "促销王", "sort_order": 20},
        ]
        # "促销" 子串先命中 a
        assert match_employee_by_campaign("双11_促销王_男鞋", operators=custom) == "a"


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

    def test_cookie_utm_resolves_to_quqi(self):
        src = "https://shop.com/?utm_source=cookie"
        att, slug, dec = resolve_attribution(src, None)
        assert att == "employee"
        assert slug == "quqi"
        assert dec == "first"


def test_employee_order_constant_length():
    # 常量文件保留不动（稳定后 B.4/C 再清理）
    assert len(EMPLOYEE_SLUGS_ORDERED) == 8
