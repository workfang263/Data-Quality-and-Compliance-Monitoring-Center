"""
token-source-unify：店铺 token 必须优先读取主系统表，env 仅作短期兜底。
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
for p in (_ROOT, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services import store_ops_constants as const_mod


class _FakeDbWithToken:
    def __init__(self, token: str):
        self._token = token

    def get_store_access_token(self, shop_domain: str) -> str:
        return self._token


def test_get_store_ops_token_prefers_db_token(monkeypatch):
    monkeypatch.setattr(
        const_mod,
        "Database",
        lambda: _FakeDbWithToken("db-token-123"),
    )
    monkeypatch.setenv("SHOPLAZZA_ACCESS_TOKEN_SHUTIAOES", "env-token-456")

    token = const_mod.get_store_ops_token_for_shop("shutiaoes.myshoplaza.com")

    assert token == "db-token-123"


def test_get_store_ops_token_falls_back_to_env_when_db_empty(monkeypatch):
    monkeypatch.setattr(
        const_mod,
        "Database",
        lambda: _FakeDbWithToken(""),
    )
    monkeypatch.setenv("SHOPLAZZA_ACCESS_TOKEN_NEWGGES", "env-token-456")

    token = const_mod.get_store_ops_token_for_shop("newgges.myshoplaza.com")

    assert token == "env-token-456"


def test_get_store_ops_token_returns_empty_when_db_and_env_both_missing(monkeypatch):
    monkeypatch.setattr(
        const_mod,
        "Database",
        lambda: _FakeDbWithToken(""),
    )
    monkeypatch.delenv("SHOPLAZZA_ACCESS_TOKEN_NEWGGES", raising=False)

    token = const_mod.get_store_ops_token_for_shop("newgges.myshoplaza.com")

    assert token == ""
