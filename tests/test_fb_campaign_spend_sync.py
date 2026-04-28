"""
B.3 单元测试：fb_campaign_spend_sync 的纯函数行为。
只覆盖无 IO 的纯函数（parse_campaign_rows / compute_reconciliation_diff / date_range）。
真实 DB/FB API 的链路由 --dry-run 活体脚本覆盖。

运行（项目根目录）：
    python -m pytest tests/test_fb_campaign_spend_sync.py -v
"""
from __future__ import annotations

import datetime
import os
import sys
from decimal import Decimal

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fb_campaign_spend_sync import (
    compute_reconciliation_diff,
    date_range,
    parse_campaign_rows,
)


class TestParseCampaignRows:
    def test_empty_input(self):
        assert parse_campaign_rows([], "act_1", datetime.date(2026, 4, 22)) == []
        assert parse_campaign_rows(None, "act_1", datetime.date(2026, 4, 22)) == []

    def test_happy_path(self):
        day = datetime.date(2026, 4, 22)
        api = [
            {"campaign_id": "c1", "campaign_name": "A", "spend": "12.50",
             "account_currency": "USD", "date_start": "2026-04-22", "date_stop": "2026-04-22"},
            {"campaign_id": "c2", "campaign_name": "B", "spend": "0.30",
             "account_currency": "USD", "date_start": "2026-04-22", "date_stop": "2026-04-22"},
        ]
        rows = parse_campaign_rows(api, "act_1", day)
        assert len(rows) == 2
        rows_by_cid = {r[2]: r for r in rows}
        assert rows_by_cid["c1"] == (day, "act_1", "c1", "A", Decimal("12.50"), "USD")
        assert rows_by_cid["c2"] == (day, "act_1", "c2", "B", Decimal("0.30"), "USD")

    def test_filter_mismatched_date(self):
        day = datetime.date(2026, 4, 22)
        api = [
            {"campaign_id": "c1", "spend": "1", "date_start": "2026-04-22"},
            {"campaign_id": "c2", "spend": "2", "date_start": "2026-04-21"},
        ]
        rows = parse_campaign_rows(api, "act_x", day)
        assert [r[2] for r in rows] == ["c1"]

    def test_skip_rows_without_campaign_id(self):
        day = datetime.date(2026, 4, 22)
        api = [
            {"campaign_id": "", "spend": "1", "date_start": "2026-04-22"},
            {"spend": "1", "date_start": "2026-04-22"},
            {"campaign_id": "c1", "spend": "1", "date_start": "2026-04-22"},
        ]
        rows = parse_campaign_rows(api, "act_x", day)
        assert [r[2] for r in rows] == ["c1"]

    def test_negative_spend_clamped_to_zero(self):
        day = datetime.date(2026, 4, 22)
        api = [
            {"campaign_id": "c1", "spend": "-3.00", "date_start": "2026-04-22"},
        ]
        rows = parse_campaign_rows(api, "act_x", day)
        assert rows[0][4] == Decimal("0")

    def test_duplicate_campaign_id_keeps_max_spend(self):
        day = datetime.date(2026, 4, 22)
        api = [
            {"campaign_id": "c1", "spend": "5", "date_start": "2026-04-22"},
            {"campaign_id": "c1", "spend": "9", "date_start": "2026-04-22"},
            {"campaign_id": "c1", "spend": "3", "date_start": "2026-04-22"},
        ]
        rows = parse_campaign_rows(api, "act_x", day)
        assert len(rows) == 1
        assert rows[0][4] == Decimal("9")

    def test_invalid_spend_becomes_zero(self):
        day = datetime.date(2026, 4, 22)
        api = [{"campaign_id": "c1", "spend": "not-a-number", "date_start": "2026-04-22"}]
        rows = parse_campaign_rows(api, "act_x", day)
        assert rows[0][4] == Decimal("0")

    def test_currency_blank_becomes_none(self):
        day = datetime.date(2026, 4, 22)
        api = [{"campaign_id": "c1", "spend": "1", "date_start": "2026-04-22",
                "account_currency": "  "}]
        rows = parse_campaign_rows(api, "act_x", day)
        assert rows[0][5] is None


class TestComputeReconciliationDiff:
    def test_both_zero(self):
        abs_diff, ratio = compute_reconciliation_diff(Decimal("0"), Decimal("0"))
        assert abs_diff == Decimal("0")
        assert ratio == Decimal("0")

    def test_exact_match(self):
        abs_diff, ratio = compute_reconciliation_diff(Decimal("100"), Decimal("100"))
        assert abs_diff == Decimal("0")
        assert ratio == Decimal("0")

    def test_within_threshold(self):
        _abs, ratio = compute_reconciliation_diff(Decimal("99.5"), Decimal("100"))
        assert ratio < Decimal("0.01")

    def test_over_threshold(self):
        _abs, ratio = compute_reconciliation_diff(Decimal("90"), Decimal("100"))
        assert ratio > Decimal("0.01")

    def test_denominator_uses_max(self):
        abs_diff, ratio = compute_reconciliation_diff(Decimal("0"), Decimal("100"))
        assert abs_diff == Decimal("100")
        assert ratio == Decimal("1")


class TestDateRange:
    def test_single_day(self):
        d = datetime.date(2026, 4, 22)
        assert date_range(d, d) == [d]

    def test_inclusive_range(self):
        s = datetime.date(2026, 4, 20)
        e = datetime.date(2026, 4, 22)
        assert date_range(s, e) == [
            datetime.date(2026, 4, 20),
            datetime.date(2026, 4, 21),
            datetime.date(2026, 4, 22),
        ]
