"""
映射资源操作审计 API
GET /api/audit/mapping-resources — 分页列表（与映射编辑权限一致：admin 或 can_edit_mappings）
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth_api import get_current_user
from app.services.database_new import Database

logger = logging.getLogger(__name__)

router = APIRouter()
db = Database()

_ALLOWED_RESOURCE_TYPES = frozenset({"store", "facebook", "tiktok"})
_ALLOWED_ACTIONS = frozenset({"create", "update"})
_ALLOWED_RESULT_STATUS = frozenset({"success", "warning", "error"})


def _require_mapping_audit_permission(current_user: Dict[str, Any]) -> None:
    if current_user.get("role") == "admin":
        return
    if current_user.get("can_edit_mappings") is True:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="无权查看映射操作记录",
    )


def _normalize_filter(value: Optional[str], allowed: frozenset) -> Optional[str]:
    if value is None or value == "":
        return None
    v = value.strip().lower()
    if v not in allowed:
        raise HTTPException(status_code=400, detail=f"非法筛选参数: {value}")
    return v


def _format_audit_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        created = r.get("created_at")
        out.append(
            {
                "id": r.get("id"),
                "action": r.get("action"),
                "resource_type": r.get("resource_type"),
                "resource_id": r.get("resource_id"),
                "owner": r.get("owner"),
                "operator_user_id": r.get("operator_user_id"),
                "operator_username": r.get("operator_username"),
                "request_payload": r.get("request_payload"),
                "result_status": r.get("result_status"),
                "result_message": r.get("result_message"),
                "created_at": created.isoformat() if created else None,
            }
        )
    return out


@router.get("/api/audit/mapping-resources")
async def list_mapping_resource_audits(
    limit: int = Query(50, ge=1, le=200, description="每页条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    resource_type: Optional[str] = Query(None, description="store|facebook|tiktok"),
    action: Optional[str] = Query(None, description="create|update"),
    result_status: Optional[str] = Query(None, description="success|warning|error"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    分页返回 mapping_resource_audit 记录（最新在前）。
    """
    _require_mapping_audit_permission(current_user)

    rt = _normalize_filter(resource_type, _ALLOWED_RESOURCE_TYPES)
    act = _normalize_filter(action, _ALLOWED_ACTIONS)
    st = _normalize_filter(result_status, _ALLOWED_RESULT_STATUS)

    total = db.count_mapping_resource_audits(
        resource_type=rt,
        action=act,
        result_status=st,
    )
    rows = db.get_mapping_resource_audits(
        limit=limit,
        offset=offset,
        resource_type=rt,
        action=act,
        result_status=st,
    )
    items = _format_audit_rows(rows)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }
