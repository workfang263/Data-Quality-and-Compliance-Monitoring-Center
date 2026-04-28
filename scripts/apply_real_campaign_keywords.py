"""
M3: Write real campaign_keyword via C.1 API, then verify via report API.

  --dry-run   (default) only prints the PATCH plan
  --apply     PATCH via /api/store-ops/config/operators/{id}; backs up old
              values to _tmp_campaign_keyword_backup.json; then calls
              /api/store-ops/report to verify spend distribution.
  --rollback  restore campaign_keyword from backup file.
  --report-only  no changes, just print current /api/store-ops/report state.

All writes go through the C.1 endpoint, so each PATCH writes an audit row
to store_ops_config_audit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:
    print("Please pip install requests first"); sys.exit(2)


API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
BACKUP_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "_tmp_campaign_keyword_backup.json",
)

TARGET_KEYWORDS: Dict[str, str] = {
    "xiaoyang":  "xiaoyang",
    "kiki":      "__unset_kiki",
    "jieni":     "jieni",
    "amao":      "amao",
    "jimi":      "jimi",
    "xiaozhang": "xiaozhang",
    "wanqiu":    "wanqiu",
    "quqi":      "cookie",
}

TARGET_DATE = "2026-04-21"


def _login() -> str:
    r = requests.post(
        f"{API_BASE}/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    r.raise_for_status()
    j = r.json()
    token = (j.get("data") or {}).get("token") or j.get("token")
    if not token:
        raise SystemExit(f"login failed: {j}")
    return token


def _auth(headers: Dict[str, str], token: str) -> Dict[str, str]:
    return {**headers, "Authorization": f"Bearer {token}"}


def _list_operators(token: str) -> List[Dict[str, Any]]:
    r = requests.get(
        f"{API_BASE}/api/store-ops/config/operators",
        headers=_auth({}, token),
        timeout=15,
    )
    r.raise_for_status()
    j = r.json()
    data = j.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or []
    return []


def _patch_operator(token: str, op_id: int, new_kw: str) -> Dict[str, Any]:
    r = requests.patch(
        f"{API_BASE}/api/store-ops/config/operators/{op_id}",
        headers=_auth({"Content-Type": "application/json"}, token),
        data=json.dumps({"campaign_keyword": new_kw}),
        timeout=15,
    )
    if r.status_code >= 400:
        print(f"  !! PATCH {op_id} failed HTTP {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
    return r.json()


def _report(token: str, date_s: str = TARGET_DATE, date_e: str = TARGET_DATE) -> Dict[str, Any]:
    r = requests.get(
        f"{API_BASE}/api/store-ops/report",
        headers=_auth({}, token),
        params={"start_date": date_s, "end_date": date_e},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _print_report(payload: Dict[str, Any], label: str) -> None:
    data = payload.get("data") or payload
    print(f"\n--- Report ({label}) {data.get('date_start')} ~ {data.get('date_end')} ---")
    for shop in data.get("shops", []):
        print(f"  [{shop['shop_domain']}]")
        print(f"    unattributed_fb_spend = {float(shop.get('unattributed_fb_spend', 0)):.2f}")
        rows = shop.get("employee_rows", [])
        print(f"    {'slug':<12} {'fb_spend':>10} {'total_sales':>12} {'roas':>8}")
        for row in rows:
            fb = float(row.get("fb_spend") or 0)
            sales = float(row.get("total_sales") or 0)
            roas_v = row.get("roas")
            roas_s = f"{float(roas_v):.2f}" if roas_v is not None else "-"
            print(f"    {row['employee_slug']:<12} {fb:>10.2f} {sales:>12.2f} {roas_s:>8}")


def _diff_fb(before: Dict[str, Any], after: Dict[str, Any]) -> None:
    print("\n--- Diff (fb_spend) ---")
    bef = before.get("data") or before
    aft = after.get("data") or after
    for b_shop, a_shop in zip(bef.get("shops", []), aft.get("shops", [])):
        name = a_shop["shop_domain"]
        b_un = float(b_shop.get("unattributed_fb_spend", 0))
        a_un = float(a_shop.get("unattributed_fb_spend", 0))
        print(f"  [{name}]")
        print(f"    unattributed_fb_spend: {b_un:.2f} -> {a_un:.2f}  delta={a_un - b_un:+.2f}")
        b_map = {r["employee_slug"]: float(r.get("fb_spend") or 0) for r in b_shop.get("employee_rows", [])}
        a_map = {r["employee_slug"]: float(r.get("fb_spend") or 0) for r in a_shop.get("employee_rows", [])}
        keys = sorted(set(b_map) | set(a_map))
        for k in keys:
            bv, av = b_map.get(k, 0), a_map.get(k, 0)
            if bv == 0 and av == 0:
                continue
            print(f"    {k:<12} {bv:>10.2f} -> {av:>10.2f}  delta={av - bv:+.2f}")


def _save_backup(ops: List[Dict[str, Any]]) -> None:
    backup = [
        {
            "id": op["id"],
            "employee_slug": op["employee_slug"],
            "campaign_keyword_before": op.get("campaign_keyword"),
        }
        for op in ops
    ]
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    print(f"[backup] saved {len(backup)} entries to {BACKUP_FILE}")


def _load_backup() -> Optional[List[Dict[str, Any]]]:
    if not os.path.exists(BACKUP_FILE):
        return None
    with open(BACKUP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_dry_run(token: str) -> int:
    ops = _list_operators(token)
    print(f"[dry-run] current active operators: {len(ops)}")
    print(f"  {'id':>3}  {'slug':<12} {'current':<28} -> {'target':<24}")
    changes = 0
    for op in ops:
        slug = op.get("employee_slug") or ""
        cur = op.get("campaign_keyword") or ""
        target = TARGET_KEYWORDS.get(slug, cur)
        mark = "  " if cur == target else "**"
        if cur != target:
            changes += 1
        print(f"  {mark}{op['id']:>3}  {slug:<12} {cur!r:<28} -> {target!r:<24}")
    print(f"\nexpected PATCH count: {changes}")
    return 0


def cmd_apply(token: str) -> int:
    ops = _list_operators(token)
    _save_backup(ops)

    print("\n[step 1] snapshot report BEFORE apply")
    report_before = _report(token)
    _print_report(report_before, "before apply")

    print("\n[step 2] PATCH campaign_keyword for each operator")
    patched = 0
    for op in ops:
        slug = op.get("employee_slug") or ""
        cur = op.get("campaign_keyword") or ""
        target = TARGET_KEYWORDS.get(slug)
        if target is None or cur == target:
            continue
        print(f"  PATCH id={op['id']} slug={slug}: {cur!r} -> {target!r}")
        _patch_operator(token, int(op["id"]), target)
        patched += 1
    print(f"  PATCH done: {patched}")

    print("\n[step 3] snapshot report AFTER apply")
    report_after = _report(token)
    _print_report(report_after, "after apply")
    _diff_fb(report_before, report_after)

    print("\n[step 4] conservation check")
    bef = report_before.get("data") or report_before
    aft = report_after.get("data") or report_after
    for b_shop, a_shop in zip(bef.get("shops", []), aft.get("shops", [])):
        b_total = float(b_shop.get("unattributed_fb_spend", 0)) + sum(
            float(r.get("fb_spend") or 0) for r in b_shop.get("employee_rows", [])
        )
        a_total = float(a_shop.get("unattributed_fb_spend", 0)) + sum(
            float(r.get("fb_spend") or 0) for r in a_shop.get("employee_rows", [])
        )
        diff = abs(b_total - a_total)
        status_s = "[PASS]" if diff < 0.01 else "[FAIL]"
        print(f"  [{a_shop['shop_domain']}] total before={b_total:.2f}  after={a_total:.2f}  diff={diff:.4f}  {status_s}")

    print("\n[step 5] latest 10 audit rows (operator)")
    r = requests.get(
        f"{API_BASE}/api/store-ops/config/audit",
        headers=_auth({}, token),
        params={"resource_type": "operator", "page_size": 10},
        timeout=15,
    )
    if r.status_code == 200:
        items = (r.json().get("data") or {}).get("items") or []
        print(f"  total {len(items)} rows, showing up to 10:")
        for it in items[:10]:
            print(
                f"    {it.get('created_at')}  {it.get('action'):<10} "
                f"resource={it.get('resource_key'):<12} actor={it.get('actor_username')}"
            )
    else:
        print(f"  audit API returned {r.status_code}: {r.text[:200]}")

    return 0


def cmd_rollback(token: str) -> int:
    backup = _load_backup()
    if not backup:
        print(f"[rollback] no backup at {BACKUP_FILE}, abort"); return 1
    print(f"[rollback] loaded {len(backup)} entries; restoring")
    ops = _list_operators(token)
    by_id = {int(op["id"]): op for op in ops}

    rolled = 0
    for b in backup:
        op = by_id.get(int(b["id"]))
        if not op:
            print(f"  !! operator id={b['id']} not found, skip"); continue
        cur = op.get("campaign_keyword") or ""
        old = b.get("campaign_keyword_before") or ""
        if cur == old:
            print(f"  id={b['id']} slug={b['employee_slug']} unchanged, skip"); continue
        print(f"  PATCH id={b['id']} slug={b['employee_slug']}: {cur!r} -> {old!r}")
        _patch_operator(token, int(b["id"]), old)
        rolled += 1
    print(f"  rollback done: {rolled}")
    return 0


def cmd_report_only(token: str) -> int:
    payload = _report(token)
    _print_report(payload, "current DB state")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    g.add_argument("--rollback", action="store_true")
    g.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    token = _login()

    if args.rollback:
        return cmd_rollback(token)
    if args.report_only:
        return cmd_report_only(token)
    if args.apply:
        return cmd_apply(token)
    return cmd_dry_run(token)


if __name__ == "__main__":
    sys.exit(main())
