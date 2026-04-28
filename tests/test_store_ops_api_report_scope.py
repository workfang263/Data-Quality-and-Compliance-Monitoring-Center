"""
report-scope-db：报表店铺范围必须从 DB 白名单解析。
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import HTTPException

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
for p in (_ROOT, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.api.store_ops_api import _resolve_report_scope


class _FakeDb:
    def __init__(self, shops):
        self._shops = shops

    def get_enabled_store_ops_shop_domains(self):
        return list(self._shops)


def test_resolve_report_scope_returns_all_enabled_shops():
    db = _FakeDb(["newgges.myshoplaza.com", "natie1.myshoplaza.com"])

    shops = _resolve_report_scope(db, None)

    assert shops == ["newgges.myshoplaza.com", "natie1.myshoplaza.com"]


def test_resolve_report_scope_accepts_enabled_single_shop_with_trim():
    db = _FakeDb(["natie1.myshoplaza.com"])

    shops = _resolve_report_scope(db, "  natie1.myshoplaza.com  ")

    assert shops == ["natie1.myshoplaza.com"]


def test_resolve_report_scope_rejects_shop_outside_enabled_whitelist():
    db = _FakeDb(["newgges.myshoplaza.com"])

    with pytest.raises(HTTPException) as exc:
        _resolve_report_scope(db, "natie1.myshoplaza.com")

    assert exc.value.status_code == 400
    assert exc.value.detail == "shop_domain 不在启用白名单中"
