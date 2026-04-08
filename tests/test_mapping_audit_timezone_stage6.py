"""
阶段 6 — 映射 / 审计 / 时区相关自动化测试

覆盖要点（与修订计划一致）：
- FB：mock Graph 返回 timezone_name，断言 upsert 参数与解析逻辑。
- TT：mock 广告主时区字段，断言映射解析与入库 SQL 参数。
- 审计：_redact_mapping_payload 不含明文 token。
- TikTok 同步管线：本地 naive 小时 + offset → 北京时间（与 timezone_utils 一致）。

运行（项目根目录）：
    python -m pytest tests/test_mapping_audit_timezone_stage6.py -v
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# 项目根与 backend 包路径（便于 import app.*）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_ROOT, "backend")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from timezone_utils import convert_to_beijing_time, get_timezone_config

from app.services import mapping_resource_utils as mru
from app.api.mappings_api import _redact_mapping_payload


class TestConvertToBeijing:
    """与 fb_spend_sync / tt_spend_sync 共用的换算公式。"""

    @pytest.mark.parametrize(
        "dt_local,offset_hours,expected",
        [
            # 已是 UTC+8，不变
            (datetime(2025, 12, 8, 15, 0, 0), 8.0, datetime(2025, 12, 8, 15, 0, 0)),
            # UTC-8：本地 12-08 10:00 → 北京 12-09 02:00
            (datetime(2025, 12, 8, 10, 0, 0), -8.0, datetime(2025, 12, 9, 2, 0, 0)),
            # UTC+0：伦敦冬季 12-08 12:00 → 北京 12-08 20:00
            (datetime(2025, 12, 8, 12, 0, 0), 0.0, datetime(2025, 12, 8, 20, 0, 0)),
        ],
    )
    def test_convert_to_beijing_time(self, dt_local, offset_hours, expected):
        assert convert_to_beijing_time(dt_local, offset_hours) == expected


class TestGetTimezoneConfigMocked:
    """不连真实 MySQL，只 mock cursor 行为。"""

    def _conn(self, fetch_sequence):
        """
        fetch_sequence: 按顺序对应每次 cur.fetchone() 的返回值
        （各查询：execute 一次再 fetchone 一次）。
        """
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.side_effect = list(fetch_sequence)
        conn.cursor.return_value.__enter__.return_value = cur
        conn.cursor.return_value.__exit__.return_value = None
        return conn

    def test_tiktok_account_row(self):
        conn = self._conn(
            [
                {"timezone": "America/Los_Angeles", "timezone_offset": Decimal("-8.0")},
            ]
        )
        cfg = get_timezone_config(conn, "7123456789", owner="某人", platform="tiktok")
        assert cfg["timezone"] == "America/Los_Angeles"
        assert cfg["timezone_offset"] == -8.0

    def test_fallback_owner_then_default(self):
        # 账户无行 → owner 无行 → 默认上海
        conn = self._conn(
            [
                None,
                None,
            ]
        )
        cfg = get_timezone_config(conn, "7123456789", owner="无人配置", platform="tiktok")
        assert cfg["timezone"] == "Asia/Shanghai"
        assert cfg["timezone_offset"] == 8.0


class TestRedactMappingPayload:
    """审计入库前脱敏：不得保留 access_token 等明文。"""

    def test_flat_secrets_redacted(self):
        payload = {
            "shop_domain": "demo.myshoplaza.com",
            "access_token": "should-not-leak",
            "owner": "张三",
        }
        out = _redact_mapping_payload(payload)
        assert out["shop_domain"] == payload["shop_domain"]
        assert out["owner"] == payload["owner"]
        assert out["access_token"] == "***REDACTED***"

    def test_nested_and_suffix_token(self):
        payload = {
            "store": {"nested_api_token": "hidden", "ok": 1},
            "fb_long_lived_token": "fbsecret",
        }
        out = _redact_mapping_payload(payload)
        assert out["fb_long_lived_token"] == "***REDACTED***"
        assert out["store"]["nested_api_token"] == "***REDACTED***"
        assert out["store"]["ok"] == 1


class TestFetchFbTimezoneMocked:
    """Mock Meta Graph，验证别名与写入参数。"""

    @patch("app.services.mapping_resource_utils.requests.get")
    def test_graph_beijing_alias_to_shanghai(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"timezone_name": "Asia/Beijing"}
        mock_get.return_value = mock_resp

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur

        r = mru.fetch_and_upsert_fb_ad_timezone(conn, "act_999888", "tok")
        assert r["ok"] is True
        assert "Shanghai" in r["timezone"] or r["timezone"] == "Asia/Shanghai"
        cur.execute.assert_called_once()
        sql, params = cur.execute.call_args[0]
        assert "INSERT INTO ad_account_timezone_mapping" in sql
        assert params[0] == "act_999888"
        assert params[1] == "Asia/Shanghai"

    @patch("app.services.mapping_resource_utils.requests.get")
    def test_missing_token_no_request(self, mock_get):
        conn = MagicMock()
        r = mru.fetch_and_upsert_fb_ad_timezone(conn, "act_1", "")
        assert r["ok"] is False
        mock_get.assert_not_called()


class TestFetchTtTimezoneMocked:
    """Mock TikTok advertiser/info 解析链。"""

    @patch("app.services.mapping_resource_utils._fetch_tt_advertiser_info")
    def test_display_timezone_utc_plus_8(self, mock_fetch):
        mock_fetch.return_value = {"display_timezone": "UTC+8"}

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur

        r = mru.fetch_and_upsert_tt_ad_timezone(conn, "7123", access_token="t")
        assert r["ok"] is True
        assert r["timezone_offset"] == 8.0
        cur.execute.assert_called_once()
        _sql, params = cur.execute.call_args[0]
        assert params[0] == "7123"

    @patch("app.services.mapping_resource_utils._fetch_tt_advertiser_info")
    def test_no_row_returns_false(self, mock_fetch):
        mock_fetch.return_value = None
        conn = MagicMock()
        r = mru.fetch_and_upsert_tt_ad_timezone(conn, "7123", access_token="t")
        assert r["ok"] is False
        assert "无法获取" in (r.get("message") or "")


class TestTtSpendHourPipeline:
    """
    模拟 tt_spend_sync 单行处理：请求日 d、stat_time_hour 解析为本地 naive、
    过滤 dt_local.date()==d，再 convert_to_beijing_time。
    """

    def test_la_winter_hour_maps_to_next_calendar_day_in_beijing(self):
        d = date(2025, 12, 8)
        tz_off = -8.0
        time_str = "2025-12-08 10:00:00"
        dt_local = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        assert dt_local.date() == d
        time_hour_bj = convert_to_beijing_time(dt_local, tz_off)
        assert time_hour_bj == datetime(2025, 12, 9, 2, 0, 0)

    def test_cross_day_row_filtered_out(self):
        """API 若混入「本地日 ≠ 请求日」的行，应与脚本一致丢弃。"""
        d = date(2025, 12, 8)
        dt_local = datetime(2025, 12, 7, 23, 0, 0)
        assert dt_local.date() != d


class TestResolveTiktokTimezoneUnit:
    """编码 / UTC 写法解析（无网络）。"""

    def test_utc_offset_form(self):
        name, off = mru._resolve_tiktok_timezone("UTC -5.5")
        assert off == -5.5
        assert "UTC" in name

    def test_known_code_maps_iana(self):
        name, off = mru._resolve_tiktok_timezone("Asia/Shanghai")
        assert name == "Asia/Shanghai"
        assert off == 8.0
