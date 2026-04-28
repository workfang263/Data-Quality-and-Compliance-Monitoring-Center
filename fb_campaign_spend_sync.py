"""
店铺运营子系统：Facebook 系列级日花费同步（B.3）

与 fb_spend_sync.py 并列（不动老脚本）：
  - 账户来源：store_ops_shop_ad_whitelist WHERE is_enabled=1
  - API 粒度：level=campaign（一日一条/账户/系列，而非小时）
  - 落库：REPLACE INTO fb_campaign_spend_daily
  - 对账：当日该账户 SUM(campaign.spend) vs fb_ad_account_spend_hourly 同日 SUM(spend)
          差值比例 > 1% 时写 operation_logs 的 warning 日志

使用方式（示例）：
  # 默认拉取今天
  python fb_campaign_spend_sync.py
  # 拉取指定日期
  python fb_campaign_spend_sync.py --date 2026-04-22
  # 区间（闭区间，按天循环）
  python fb_campaign_spend_sync.py --start 2026-04-15 --end 2026-04-22
  # 增量模式（不先删旧数据，直接 REPLACE 覆盖）
  python fb_campaign_spend_sync.py --incremental
  # 仅演练（读 DB + 调 FB API，但不写 DB）
  python fb_campaign_spend_sync.py --date 2026-04-22 --dry-run
  # 仅取前 N 个启用账户（用于首轮 smoke test）
  python fb_campaign_spend_sync.py --date 2026-04-22 --limit 1 --dry-run

前置要求：
  1) 环境变量 FB_LONG_LIVED_TOKEN 已配置
  2) 表已存在：store_ops_shop_ad_whitelist、fb_campaign_spend_daily、operation_logs
  3) store_ops_shop_ad_whitelist 内账户需已在主系统 ad_account_owner_mapping 存在（回填脚本已校验）
"""
from __future__ import annotations

import argparse
import datetime
import os
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import pymysql
import requests

from config import DB_CONFIG


API_VERSION = "v19.0"
MAX_RETRY = 3
RETRY_SLEEP = 3
RECON_DIFF_THRESHOLD = Decimal("0.01")


def get_db_conn():
    """沿用主系统 fb_spend_sync.py 的连接方式（pymysql + DictCursor + autocommit=False）。"""
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def fetch_enabled_accounts(conn) -> List[Dict[str, Any]]:
    """读取子系统白名单里"启用"的账户，附带所属店铺域名。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.id AS whitelist_id,
                   w.ad_account_id,
                   w.shop_domain,
                   w.is_enabled
            FROM store_ops_shop_ad_whitelist w
            JOIN store_ops_shop_whitelist s
                 ON s.shop_domain COLLATE utf8mb4_unicode_ci
                  = w.shop_domain COLLATE utf8mb4_unicode_ci
                AND s.is_enabled = 1
            WHERE w.is_enabled = 1
            ORDER BY w.shop_domain, w.ad_account_id
            """
        )
        return cur.fetchall() or []


def fetch_account_hourly_daily_total(
    conn, ad_account_id: str, stat_date: datetime.date
) -> Decimal:
    """从主系统 fb_ad_account_spend_hourly 取某账户某北京日 SUM(spend)。
    
    说明：该表 time_hour 为北京时间；此处使用 Beijing-day 口径做对账，对于
    UTC-8 类账户会有一天的偏移，属于"对账仅用于异常发现"的可接受误差。
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(spend), 0) AS total
            FROM fb_ad_account_spend_hourly
            WHERE ad_account_id = %s
              AND DATE(time_hour) = %s
            """,
            (ad_account_id, stat_date),
        )
        row = cur.fetchone() or {}
    total = row.get("total") or 0
    return Decimal(str(total))


def _build_proxies() -> Optional[Dict[str, str]]:
    """代理配置：优先环境变量，否则 None（与 fb_spend_sync.py 保持一致）。"""
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if http_proxy or https_proxy:
        return {
            "http": http_proxy or https_proxy,
            "https": https_proxy or http_proxy,
        }
    return None


def poll_report_result(
    account_id: str, report_run_id: str, token: str, proxies: Optional[Dict]
) -> List[Dict]:
    """轮询 FB 异步报告（与 fb_spend_sync.py 保持行为一致，仅用于极少数异步返回场景）。"""
    url = f"https://graph.facebook.com/{API_VERSION}/{report_run_id}"
    params = {"access_token": token}
    max_polls = 30
    poll_interval = 5
    for i in range(max_polls):
        try:
            time.sleep(poll_interval)
            resp = requests.get(url, params=params, timeout=30, proxies=proxies)
            resp.raise_for_status()
            data = resp.json()
            async_percent = data.get("async_percent_completion", 0)
            status = data.get("async_status") or data.get("status")
            if status == "Job Completed" and async_percent == 100:
                result_url = f"https://graph.facebook.com/{API_VERSION}/{report_run_id}/insights"
                result_resp = requests.get(
                    result_url, params={"access_token": token}, timeout=30, proxies=proxies
                )
                result_resp.raise_for_status()
                return result_resp.json().get("data", [])
            elif status in ("Job Skipped", "Job Failed"):
                print(f"[WARN] {account_id} 异步报告状态: {status}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"[WARN] {account_id} 轮询异步报告失败 ({i+1}/{max_polls}): {e}")
        except Exception as e:
            print(f"[ERR ] {account_id} 轮询异步报告异常 ({i+1}/{max_polls}): {e}")
    print(f"[WARN] {account_id} 异步报告轮询超时")
    return []


def call_campaign_insights(
    account_id: str, since: str, until: str, token: str,
    proxies: Optional[Dict] = None,
) -> List[Dict]:
    """调 Graph API 拿某账户某日的系列级 spend。

    字段：campaign_id / campaign_name / spend / account_currency / date_start / date_stop
    level=campaign，不加 breakdowns。
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{account_id}/insights"
    params = {
        "fields": "campaign_id,campaign_name,spend,account_currency,date_start,date_stop",
        "time_range": f'{{"since":"{since}","until":"{until}"}}',
        "level": "campaign",
        "limit": "500",
        "access_token": token,
    }
    if proxies is None:
        proxies = _build_proxies()

    for i in range(MAX_RETRY):
        try:
            resp = requests.get(url, params=params, timeout=60, proxies=proxies)
            if resp.status_code == 200:
                data = resp.json()
                if "report_run_id" in data:
                    rid = data["report_run_id"]
                    print(f"[INFO] {account_id} {since} 异步报告 {rid} 开始轮询...")
                    return poll_report_result(account_id, rid, token, proxies)
                result = data.get("data", [])
                if not result:
                    print(f"[DEBUG] {account_id} {since} 返回空系列")
                return result
            else:
                print(
                    f"[WARN] {account_id} {since}~{until} level=campaign "
                    f"status={resp.status_code} resp={resp.text[:300]}"
                )
        except Exception as e:
            print(f"[ERR ] {account_id} {since}~{until} level=campaign error={e}")
        time.sleep(RETRY_SLEEP)
    return []


def parse_campaign_rows(
    api_data: List[Dict[str, Any]],
    ad_account_id: str,
    stat_date: datetime.date,
) -> List[Tuple[datetime.date, str, str, str, Decimal, Optional[str]]]:
    """把 FB API 返回的系列级数据拍平成入库元组列表。

    过滤：
      - date_start 与入参 stat_date 不一致：跳过（API 偶尔返回邻日数据）
      - 无 campaign_id：跳过
      - spend < 0：纠正为 0
    去重：同 (campaign_id, stat_date) 仅保留 spend 最大值（稳妥侧保留）。
    """
    expected = stat_date.strftime("%Y-%m-%d")
    by_camp: Dict[str, Tuple[datetime.date, str, str, str, Decimal, Optional[str]]] = {}
    for r in api_data or []:
        cid = (r.get("campaign_id") or "").strip()
        if not cid:
            continue
        date_start = (r.get("date_start") or "").strip()
        if date_start and date_start != expected:
            continue
        cname = (r.get("campaign_name") or "").strip()
        currency = (r.get("account_currency") or "").strip() or None
        try:
            spend_dec = Decimal(str(r.get("spend", 0) or 0))
        except Exception:
            spend_dec = Decimal("0")
        if spend_dec < 0:
            spend_dec = Decimal("0")
        row = (stat_date, ad_account_id, cid, cname, spend_dec, currency)
        prev = by_camp.get(cid)
        if prev is None or spend_dec > prev[4]:
            by_camp[cid] = row
    return list(by_camp.values())


def compute_reconciliation_diff(
    campaign_sum: Decimal, account_total: Decimal
) -> Tuple[Decimal, Decimal]:
    """返回 (绝对差, 相对差比例)。相对差分母为 max(account_total, campaign_sum)；
    两侧都为 0 时相对差为 0。"""
    denom = max(account_total, campaign_sum)
    abs_diff = (campaign_sum - account_total).copy_abs()
    if denom <= 0:
        return abs_diff, Decimal("0")
    return abs_diff, (abs_diff / denom)


def clean_old_campaign_data(
    conn, start_date: datetime.date, end_date: datetime.date,
    ad_account_ids: Optional[List[str]] = None,
) -> int:
    """非增量模式下，先清理区间内旧数据（避免残留/改名导致的僵尸行）。"""
    with conn.cursor() as cur:
        if ad_account_ids:
            placeholders = ",".join(["%s"] * len(ad_account_ids))
            sql = (
                f"DELETE FROM fb_campaign_spend_daily "
                f"WHERE stat_date BETWEEN %s AND %s "
                f"AND ad_account_id IN ({placeholders})"
            )
            params = [start_date, end_date] + list(ad_account_ids)
        else:
            sql = (
                "DELETE FROM fb_campaign_spend_daily "
                "WHERE stat_date BETWEEN %s AND %s"
            )
            params = [start_date, end_date]
        cur.execute(sql, params)
        deleted = cur.rowcount
    conn.commit()
    print(f"[清理] fb_campaign_spend_daily {start_date} ~ {end_date} 删除 {deleted} 条旧数据")
    return deleted


def upsert_campaign_rows(
    conn, rows: List[Tuple[datetime.date, str, str, str, Decimal, Optional[str]]]
) -> None:
    """REPLACE INTO 写入系列级日花费。"""
    if not rows:
        return
    sql = """
    REPLACE INTO fb_campaign_spend_daily
      (stat_date, ad_account_id, campaign_id, campaign_name, spend, currency)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()


def log_operation(
    conn, log_type: str, message: str, status: str = "warning",
    shop_domain: Optional[str] = None,
) -> None:
    """写一行 operation_logs（表定义见 db/schema.sql）。"""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO operation_logs (log_type, shop_domain, message, status)
                VALUES (%s, %s, %s, %s)
                """,
                (log_type, shop_domain, message[:4000], status),
            )
        conn.commit()
    except Exception as e:
        print(f"[ERR ] 写 operation_logs 失败（吞掉）: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def date_range(start: datetime.date, end: datetime.date) -> List[datetime.date]:
    days = (end - start).days
    return [start + datetime.timedelta(days=i) for i in range(days + 1)]


def sync_one_account_one_day(
    conn, token: str, proxies: Optional[Dict], account: Dict[str, Any],
    day: datetime.date, dry_run: bool,
) -> Dict[str, Any]:
    """对一个账户在一天内：拉系列花费 → 写库 → 对账。返回摘要字典。"""
    act_id = account["ad_account_id"]
    shop = account["shop_domain"]
    since = until = day.strftime("%Y-%m-%d")
    summary = {
        "ad_account_id": act_id, "shop_domain": shop, "stat_date": day,
        "api_rows": 0, "written_rows": 0, "campaign_sum": Decimal("0"),
        "account_total": Decimal("0"), "diff_ratio": Decimal("0"),
        "reconciled": True, "error": None,
    }

    try:
        data = call_campaign_insights(act_id, since, until, token, proxies=proxies)
        summary["api_rows"] = len(data)
        rows = parse_campaign_rows(data, act_id, day)
        summary["written_rows"] = len(rows)
        campaign_sum = sum((r[4] for r in rows), Decimal("0"))
        summary["campaign_sum"] = campaign_sum

        if not dry_run and rows:
            upsert_campaign_rows(conn, rows)

        account_total = fetch_account_hourly_daily_total(conn, act_id, day)
        summary["account_total"] = account_total
        _abs, ratio = compute_reconciliation_diff(campaign_sum, account_total)
        summary["diff_ratio"] = ratio
        if ratio > RECON_DIFF_THRESHOLD:
            summary["reconciled"] = False
            msg = (
                f"[对账] {act_id} {day} campaign_sum={campaign_sum} "
                f"hourly_sum={account_total} diff={ratio*100:.2f}% > 1%"
            )
            print("[WARN] " + msg)
            if not dry_run:
                log_operation(
                    conn, log_type="fb_campaign_spend_sync",
                    message=msg, status="warning", shop_domain=shop,
                )
    except Exception as e:
        summary["error"] = str(e)
        print(f"[ERR ] {act_id} {day} 同步异常: {e}")

    return summary


def _print_run_summary(all_summaries: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 80)
    print("本轮同步汇总")
    print("=" * 80)
    total_api = sum(s["api_rows"] for s in all_summaries)
    total_written = sum(s["written_rows"] for s in all_summaries)
    total_spend = sum((s["campaign_sum"] for s in all_summaries), Decimal("0"))
    failed = [s for s in all_summaries if s["error"]]
    warnings_ = [s for s in all_summaries if not s["reconciled"]]
    print(f"  处理单元：{len(all_summaries)} 个 (账户×日)")
    print(f"  API 返回系列行：{total_api}")
    print(f"  实际写入（含 dry-run 跳过）：{total_written}")
    print(f"  系列花费合计：{total_spend}")
    print(f"  对账 warning：{len(warnings_)} 个")
    print(f"  异常失败：{len(failed)} 个")
    if warnings_:
        print("\n  对账偏差 TOP 5：")
        for s in sorted(warnings_, key=lambda x: x["diff_ratio"], reverse=True)[:5]:
            print(
                f"    - {s['ad_account_id']} {s['stat_date']} "
                f"campaign_sum={s['campaign_sum']} hourly_sum={s['account_total']} "
                f"diff={s['diff_ratio']*100:.2f}%"
            )
    if failed:
        print("\n  失败 TOP 5：")
        for s in failed[:5]:
            print(f"    - {s['ad_account_id']} {s['stat_date']} error={s['error']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="店铺运营：FB 系列级日花费同步")
    parser.add_argument("--date", help="指定日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--incremental", action="store_true",
                        help="增量模式：不清理旧数据，直接 REPLACE 覆盖")
    parser.add_argument("--dry-run", action="store_true",
                        help="演练：读 DB + 调 FB API，但不写任何表")
    parser.add_argument("--limit", type=int, default=0,
                        help="仅处理前 N 个启用账户（0=不限制）")
    args = parser.parse_args()

    os.environ.setdefault("HTTP_PROXY", "socks5h://127.0.0.1:10808")
    os.environ.setdefault("HTTPS_PROXY", "socks5h://127.0.0.1:10808")

    token = os.getenv("FB_LONG_LIVED_TOKEN")
    if not token:
        print("[FATAL] 缺少环境变量 FB_LONG_LIVED_TOKEN")
        return 2
    proxies = _build_proxies()

    today = datetime.date.today()
    if args.date:
        start_date = end_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    elif args.start and args.end:
        start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        start_date = end_date = today

    if start_date > end_date:
        print("[FATAL] --start 必须 <= --end")
        return 2

    days = date_range(start_date, end_date)
    print(f"同步日期范围：{start_date} ~ {end_date} 共 {len(days)} 天 "
          f"(dry_run={args.dry_run}, incremental={args.incremental}, limit={args.limit})")
    print("=" * 80)

    conn = get_db_conn()
    all_summaries: List[Dict[str, Any]] = []
    try:
        accounts = fetch_enabled_accounts(conn)
        if args.limit and args.limit > 0:
            accounts = accounts[: args.limit]
        if not accounts:
            print("[INFO] store_ops_shop_ad_whitelist 无启用账户，退出")
            return 0
        print(f"启用账户数：{len(accounts)}")

        if not args.incremental and not args.dry_run:
            print("\n步骤1：清理旧数据（当前仅启用账户的范围内）")
            print("-" * 80)
            clean_old_campaign_data(
                conn, start_date, end_date,
                ad_account_ids=[a["ad_account_id"] for a in accounts],
            )
        else:
            reason = "dry-run 模式" if args.dry_run else "增量模式"
            print(f"\n步骤1：跳过清理（{reason}）")

        print("\n步骤2：逐天逐账户拉系列 insights + 写库 + 对账")
        print("-" * 80)
        for d in days:
            for acc in accounts:
                s = sync_one_account_one_day(
                    conn, token, proxies, acc, d, dry_run=args.dry_run,
                )
                all_summaries.append(s)
                flag = "DRY" if args.dry_run else "OK "
                print(
                    f"[{flag}] {acc['ad_account_id']} {d} "
                    f"api={s['api_rows']} write={s['written_rows']} "
                    f"spend={s['campaign_sum']} "
                    f"hourly={s['account_total']} "
                    f"diff={(s['diff_ratio']*100):.2f}%"
                )
    finally:
        conn.close()
        _print_run_summary(all_summaries)

    has_fatal = any(s["error"] for s in all_summaries)
    return 1 if has_fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
