"""
sync-scope-db：同步默认店铺范围必须与 DB 白名单保持同源。
"""
from __future__ import annotations

import datetime as dt
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
for p in (_ROOT, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.api.store_ops_api import _resolve_sync_scope
from app.services.store_ops_sync import _resolve_sync_shops


class _FakeDb:
    def __init__(self, shops):
        self._shops = shops

    def get_enabled_store_ops_shop_domains(self):
        return list(self._shops)


def test_resolve_sync_shops_uses_explicit_scope_first():
    db = _FakeDb(["db-shop.myshoplaza.com"])

    shops = _resolve_sync_shops(
        db,
        ["manual-1.myshoplaza.com", "manual-2.myshoplaza.com"],
    )

    assert shops == ["manual-1.myshoplaza.com", "manual-2.myshoplaza.com"]


def test_resolve_sync_shops_defaults_to_enabled_whitelist():
    db = _FakeDb(["newgges.myshoplaza.com", "natie1.myshoplaza.com"])

    shops = _resolve_sync_shops(db, None)

    assert shops == ["newgges.myshoplaza.com", "natie1.myshoplaza.com"]


def test_resolve_sync_scope_reuses_same_db_shop_source():
    db = _FakeDb(["natie1.myshoplaza.com"])
    biz_dates = [dt.date(2026, 4, 22)]

    dates, shops = _resolve_sync_scope(biz_dates, None, db=db)

    assert dates == biz_dates
    assert shops == ["natie1.myshoplaza.com"]
