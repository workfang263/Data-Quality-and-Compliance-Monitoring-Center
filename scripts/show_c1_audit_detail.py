"""Show structured before/after/changes in store_ops_config_audit."""
from __future__ import annotations
import json, os, sys
try:
    import requests
except Exception:
    print("pip install requests"); sys.exit(2)

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
USER = os.environ.get("ADMIN_USER", "admin")
PWD = os.environ.get("ADMIN_PASSWORD", "admin123")


def main() -> int:
    r = requests.post(f"{API_BASE}/api/auth/login",
                      json={"username": USER, "password": PWD}, timeout=15)
    r.raise_for_status()
    token = (r.json().get("data") or {}).get("token")
    h = {"Authorization": f"Bearer {token}"}

    r = requests.get(f"{API_BASE}/api/store-ops/config/audit", headers=h,
                     params={"resource_type": "operator", "action": "update",
                             "page_size": 10}, timeout=15)
    r.raise_for_status()
    items = (r.json().get("data") or {}).get("items") or []
    print(f"Audit rows (operator/update): {len(items)}")
    for it in items[:10]:
        rp = it.get("request_payload")
        if isinstance(rp, str):
            try:
                rp = json.loads(rp)
            except Exception:
                pass
        changes = (rp or {}).get("changes") if isinstance(rp, dict) else None
        print(f"\n  [{it.get('created_at')}] resource={it.get('resource_key')} actor={it.get('actor_username')}")
        if changes:
            for k, v in changes.items():
                if isinstance(v, dict):
                    print(f"    {k}: {v.get('from')!r} -> {v.get('to')!r}")
                elif isinstance(v, list) and len(v) == 2:
                    print(f"    {k}: {v[0]!r} -> {v[1]!r}")
                else:
                    print(f"    {k}: {v!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
