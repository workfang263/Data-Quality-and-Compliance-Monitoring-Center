"""
C.1 全链路冒烟：通过 HTTP 调用，验证新增的 9 个写接口 + 1 个审计 GET。

流程（使用一个临时运营 `__smoke_${ts}` 做闭环，结束时软删）：
    [鉴权]     登录拿到 JWT
    [READ]     GET /operators 记录基线
    [POST]     新增一个临时运营 -> 201
    [GET]      再列，能看到新加的
    [PATCH]    改 display_name + campaign_keyword -> 200 changed=True
    [PATCH]    重复相同值 -> 200 changed=False（幂等）
    [PATCH]    status=blocked -> action=block
    [DELETE]   软删 -> deleted_at 非空；再次 DELETE -> changed=False
    [GET]      审计查询，确认刚才的 create/update/block/delete 都入库了

然后再对 shop / ad_account 各跑一个最简闭环（404 / 409 / 幂等几个关键分支）。

前提：
    - uvicorn 在 http://127.0.0.1:8000 运行
    - 有一个 admin 账号用来登录（env USER / PASS；默认 admin / 123456，不符请改）
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional

import requests

BASE = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8000")
USER = os.environ.get("SMOKE_USER", "admin")
PASS = os.environ.get("SMOKE_PASS", "123456")

PASS_COUNT = 0
FAIL_COUNT = 0
FAIL_DETAIL = []


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n  {title}\n{'=' * 70}")


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS_COUNT, FAIL_COUNT
    mark = "[PASS]" if ok else "[FAIL]"
    print(f"  {mark} {name}" + (f"   ({detail})" if detail else ""))
    if ok:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
        FAIL_DETAIL.append(f"{name} :: {detail}")


def login() -> str:
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": USER, "password": PASS},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    tok = (data.get("data") or {}).get("token") or data.get("token")
    assert tok, f"登录未返回 token: {data}"
    return tok


def _req(
    token: str, method: str, path: str,
    json_body: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> requests.Response:
    url = f"{BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    return requests.request(
        method, url, headers=headers, json=json_body, params=params, timeout=15,
    )


def main() -> int:
    _hr("[0] 登录")
    token = login()
    print(f"  登录成功，user={USER}")

    # ---------- 无权限路径 ----------
    _hr("[1] 未登录调用写接口 → 应 401")
    r = requests.post(f"{BASE}/api/store-ops/config/operators",
                      json={"employee_slug": "xxxx", "display_name": "x"},
                      timeout=10)
    check("POST /operators 无 token → 401", r.status_code == 401,
          f"status={r.status_code}")

    # ---------- Operator 闭环 ----------
    ts = int(time.time())
    tmp_slug = f"smoke_{ts}"
    tmp_display = "冒烟测试运营"
    tmp_utm = f"smoke_utm_{ts}"
    tmp_cmp = ""  # 故意留空，测自动填 __unset_

    _hr(f"[2] Operator CRUD (slug={tmp_slug})")

    r = _req(token, "GET", "/api/store-ops/config/operators")
    check("GET /operators 200", r.status_code == 200)
    baseline = len((r.json().get("data") or []))

    r = _req(token, "POST", "/api/store-ops/config/operators", json_body={
        "employee_slug": tmp_slug, "display_name": tmp_display,
        "utm_keyword": tmp_utm, "campaign_keyword": tmp_cmp,
        "sort_order": 9999,
    })
    ok = r.status_code == 201
    d = r.json().get("data") if ok else r.json()
    check("POST /operators 201", ok, f"{r.status_code} / {d}")
    op_id = d.get("id") if ok else None
    check("自动填充 campaign_keyword=__unset_slug",
          ok and d.get("campaign_keyword") == f"__unset_{tmp_slug}",
          f"cmp_kw={d.get('campaign_keyword') if ok else None}")

    r = _req(token, "POST", "/api/store-ops/config/operators", json_body={
        "employee_slug": tmp_slug, "display_name": "dup",
    })
    check("重复 POST slug 冲突 → 409", r.status_code == 409, f"status={r.status_code}")

    r = _req(token, "GET", "/api/store-ops/config/operators")
    after_list = r.json().get("data") or []
    check("GET /operators 列表 +1",
          len(after_list) == baseline + 1,
          f"baseline={baseline}, now={len(after_list)}")

    if op_id is not None:
        r = _req(token, "PATCH", f"/api/store-ops/config/operators/{op_id}",
                 json_body={"display_name": "冒烟测试·改名",
                            "campaign_keyword": f"smoke_camp_{ts}"})
        dj = r.json()
        check("PATCH /operators 200 changed=True",
              r.status_code == 200 and (dj.get("data") or {}).get("changed") is True,
              f"{r.status_code} / changed={(dj.get('data') or {}).get('changed')}")

        r = _req(token, "PATCH", f"/api/store-ops/config/operators/{op_id}",
                 json_body={"display_name": "冒烟测试·改名"})
        check("PATCH /operators 幂等 changed=False",
              r.status_code == 200 and (r.json().get("data") or {}).get("changed") is False,
              f"{r.status_code} / {(r.json().get('data') or {}).get('changed')}")

        r = _req(token, "PATCH", f"/api/store-ops/config/operators/{op_id}",
                 json_body={"operator_status": "blocked"})
        check("PATCH status=blocked 200",
              r.status_code == 200 and (r.json().get("data") or {}).get("status") == "blocked")

        r = _req(token, "PATCH", f"/api/store-ops/config/operators/{op_id}",
                 json_body={"operator_status": "active"})
        check("PATCH status=active 200",
              r.status_code == 200 and (r.json().get("data") or {}).get("status") == "active")

        r = _req(token, "DELETE", f"/api/store-ops/config/operators/{op_id}")
        dj = r.json()
        check("DELETE /operators 200 changed=True",
              r.status_code == 200 and (dj.get("data") or {}).get("changed") is True
              and (dj.get("data") or {}).get("deleted_at") is not None,
              str(dj))

        r = _req(token, "DELETE", f"/api/store-ops/config/operators/{op_id}")
        check("重复 DELETE 幂等 changed=False",
              r.status_code == 200 and (r.json().get("data") or {}).get("changed") is False)

    # 404 路径
    r = _req(token, "PATCH", "/api/store-ops/config/operators/99999999",
             json_body={"display_name": "x"})
    check("PATCH 不存在 id → 404", r.status_code == 404, f"status={r.status_code}")

    # ---------- Shop 闭环 ----------
    _hr("[3] Shop POST/PATCH/DELETE 关键分支")
    r = _req(token, "POST", "/api/store-ops/config/shops",
             json_body={"shop_domain": "this-shop-not-exist.invalid"})
    check("POST 不存在主系统店 → 400", r.status_code == 400, f"status={r.status_code}")

    r = _req(token, "GET", "/api/store-ops/config/shops")
    shops = r.json().get("data") or []
    if shops:
        s0 = shops[0]
        sid = s0["id"]
        orig_en = int(s0["is_enabled"])

        r = _req(token, "POST", "/api/store-ops/config/shops",
                 json_body={"shop_domain": s0["shop_domain"]})
        check("POST 已存在 shop → 409", r.status_code == 409, f"status={r.status_code}")

        target = 0 if orig_en == 1 else 1
        r = _req(token, "PATCH", f"/api/store-ops/config/shops/{sid}",
                 json_body={"is_enabled": bool(target)})
        check("PATCH is_enabled 切换 200",
              r.status_code == 200 and
              int((r.json().get("data") or {}).get("is_enabled")) == target)

        r = _req(token, "PATCH", f"/api/store-ops/config/shops/{sid}",
                 json_body={"is_enabled": bool(orig_en)})
        check("PATCH 还原 is_enabled 200",
              r.status_code == 200 and
              int((r.json().get("data") or {}).get("is_enabled")) == orig_en)
    else:
        print("  (跳过 Shop 冒烟：当前白名单为空)")

    # ---------- Ad Account 闭环 ----------
    _hr("[4] AdAccount POST/PATCH/DELETE 关键分支")
    r = _req(token, "POST", "/api/store-ops/config/ad-accounts",
             json_body={"shop_domain": "nope.invalid", "ad_account_id": "act_fake_999"})
    check("POST 店铺不存在 → 400", r.status_code == 400, f"status={r.status_code}")

    r = _req(token, "GET", "/api/store-ops/config/ad-accounts")
    accs = r.json().get("data") or []
    if accs:
        a0 = accs[0]
        aid = a0["id"]
        r = _req(token, "POST", "/api/store-ops/config/ad-accounts",
                 json_body={"shop_domain": a0["shop_domain"],
                            "ad_account_id": a0["ad_account_id"]})
        check("POST 已存在 ad_account_id → 409",
              r.status_code == 409, f"status={r.status_code}")

        orig_en = int(a0["is_enabled"])
        target = 0 if orig_en == 1 else 1
        r = _req(token, "PATCH", f"/api/store-ops/config/ad-accounts/{aid}",
                 json_body={"is_enabled": bool(target)})
        check("PATCH ad-account is_enabled 200",
              r.status_code == 200 and
              int((r.json().get("data") or {}).get("is_enabled")) == target)

        r = _req(token, "PATCH", f"/api/store-ops/config/ad-accounts/{aid}",
                 json_body={"is_enabled": bool(orig_en)})
        check("PATCH ad-account 还原 200",
              r.status_code == 200 and
              int((r.json().get("data") or {}).get("is_enabled")) == orig_en)
    else:
        print("  (跳过 AdAccount 冒烟：当前账户白名单为空)")

    # ---------- 审计查询 ----------
    _hr("[5] 审计 GET /audit")
    r = _req(token, "GET", "/api/store-ops/config/audit",
             params={"resource_type": "operator", "resource_key": tmp_slug})
    ok = r.status_code == 200
    dj = r.json().get("data") or {}
    items = dj.get("items") or []
    check("GET /audit 200", ok, f"status={r.status_code}")
    actions = [it.get("action") for it in items]
    for need in ("create", "update", "block", "unblock", "delete"):
        check(f"  审计包含 action={need}", need in actions, f"actions={actions}")

    # 随便取最新一条，确认 request_payload 被解析成 dict
    r = _req(token, "GET", "/api/store-ops/config/audit", params={"limit": 1})
    if (r.json().get("data") or {}).get("items"):
        top = r.json()["data"]["items"][0]
        check("  request_payload 解析为对象",
              isinstance(top.get("request_payload"), (dict, type(None))),
              f"type={type(top.get('request_payload'))}")

    # ---------- 汇总 ----------
    _hr("汇总")
    print(f"  通过: {PASS_COUNT}")
    print(f"  失败: {FAIL_COUNT}")
    if FAIL_DETAIL:
        print("  失败明细：")
        for d in FAIL_DETAIL:
            print(f"    - {d}")
    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
