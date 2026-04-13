"""
店铺运营 / 员工归因：内部同步接口 + 报表 API。
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    Header,
    HTTPException,
    Query,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.api.auth_api import get_current_user, verify_token

# 确保加载 backend/config_new 中的根目录 .env 后再读变量
from config_new import store_ops_https_verify

from app.services.database_new import Database
from app.services.store_ops_constants import STORE_OPS_SHOP_DOMAINS
from app.services.store_ops_report import (
    build_store_ops_report_payload,
    merge_fb_spend_into_payload,
)
from app.services.store_ops_sync import default_sync_biz_dates, run_store_ops_sync

logger = logging.getLogger(__name__)

router = APIRouter()
_optional_bearer = HTTPBearer(auto_error=False)


def get_db() -> Database:
    return Database()


def _resolve_sync_scope(
    biz_dates: Optional[List[date]],
    shop_domains: Optional[List[str]],
) -> Tuple[List[date], List[str]]:
    """与 run_store_ops_sync 相同的默认店铺与日期范围（用于落库 running 记录）。"""
    dates = biz_dates if biz_dates else default_sync_biz_dates()
    shops = shop_domains if shop_domains else list(STORE_OPS_SHOP_DOMAINS)
    return dates, shops


def _sync_run_row_to_api(row: Dict[str, Any]) -> Dict[str, Any]:
    """统一对外字段名（JSON 列转为 shops / errors / per_shop）。"""
    return {
        "sync_run_id": row.get("sync_run_id"),
        "status": row.get("status"),
        "shops": row.get("shops_json"),
        "biz_dates": row.get("biz_dates_json"),
        "orders_seen": row.get("orders_seen"),
        "orders_upserted_paid": row.get("orders_upserted_paid"),
        "orders_skipped_not_paid": row.get("orders_skipped_not_paid"),
        "error_count": row.get("error_count"),
        "errors": row.get("errors_json"),
        "per_shop": row.get("per_shop_json"),
        "exception_message": row.get("exception_message"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
    }


def _user_from_bearer(credentials: HTTPAuthorizationCredentials) -> Dict[str, Any]:
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效或已过期",
        )
    username = payload.get("username")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token无效")
    user = get_db().get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


async def require_internal_key_or_store_ops_user(
    x_internal_key: Optional[str] = Header(default=None, alias="X-Internal-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
) -> None:
    """
    Cron：携带与 STORE_OPS_SYNC_SECRET 一致的 X-Internal-Key。
    人工：Bearer JWT，且为管理员或 can_view_store_ops。
    """
    secret = (os.getenv("STORE_OPS_SYNC_SECRET") or "").strip()
    if secret and x_internal_key == secret:
        return
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要 X-Internal-Key（服务间密钥）或 Bearer 登录",
        )
    user = _user_from_bearer(credentials)
    if user.get("role") == "admin":
        return
    ext = get_db().get_user_extended_permissions(user["id"])
    if not ext.get("can_view_store_ops"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无店铺运营同步权限",
        )


def require_can_view_store_ops(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if current_user.get("role") == "admin":
        return current_user
    ext = get_db().get_user_extended_permissions(current_user["id"])
    if not ext.get("can_view_store_ops"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无店铺运营报表权限",
        )
    return current_user


class StoreOpsSyncRequest(BaseModel):
    """不传则同步北京「昨日+今日」、两店。"""

    biz_dates: Optional[List[date]] = Field(default=None, description="北京日历日列表")
    shop_domains: Optional[List[str]] = Field(
        default=None, description="店铺域名，默认两店"
    )


def _run_sync_background(
    sync_run_id: str,
    biz_dates: Optional[List[date]],
    shop_domains: Optional[List[str]],
    verify_ssl: bool,
) -> None:
    """仅执行拉单与落库结果；running 行已在 POST 返回前写入。"""
    db = Database()
    try:
        stats = run_store_ops_sync(
            sync_run_id,
            biz_dates=biz_dates,
            shop_domains=shop_domains,
            verify_ssl=verify_ssl,
        )
        if not db.finalize_store_ops_sync_run_from_stats(sync_run_id, stats):
            logger.warning(
                "store_ops 同步结果未落库（无对应 running 行？）run=%s", sync_run_id
            )
    except Exception as e:
        logger.error("store_ops 后台同步异常 run=%s: %s", sync_run_id, e, exc_info=True)
        db.finalize_store_ops_sync_run_failed(sync_run_id, repr(e))


@router.post(
    "/api/internal/store-ops/sync",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Dict[str, Any],
)
async def trigger_store_ops_sync(
    background_tasks: BackgroundTasks,
    body: StoreOpsSyncRequest = Body(default_factory=StoreOpsSyncRequest),
    _auth: None = Depends(require_internal_key_or_store_ops_user),
) -> Dict[str, Any]:
    """
    触发店匠拉单与归因写库。立即返回，实际工作在 BackgroundTasks 中执行。
    先写入 running 记录，便于客户端立刻轮询状态。
    """
    sync_run_id = str(uuid.uuid4())
    dates, shops = _resolve_sync_scope(body.biz_dates, body.shop_domains)
    if not get_db().insert_store_ops_sync_run_running(
        sync_run_id, shops, [str(d) for d in dates]
    ):
        logger.warning(
            "store_ops 未写入 sync_run running（是否已执行迁移 store_ops_sync_runs？）run=%s",
            sync_run_id,
        )
    background_tasks.add_task(
        _run_sync_background,
        sync_run_id,
        body.biz_dates,
        body.shop_domains,
        store_ops_https_verify(),
    )
    return {
        "code": 200,
        "message": "accepted",
        "data": {
            "status": "accepted",
            "sync_run_id": sync_run_id,
            "message": "同步任务已提交后台执行",
        },
    }


@router.get("/api/store-ops/report")
async def get_store_ops_report(
    start_date: date = Query(..., description="开始日期（北京业务日）"),
    end_date: date = Query(..., description="结束日期（含）"),
    shop_domain: Optional[str] = Query(
        None, description="仅看单店；不传则返回两店独立区块"
    ),
    _user: Dict[str, Any] = Depends(require_can_view_store_ops),
) -> Dict[str, Any]:
    """阶段二读时聚合：直接销售额、公共池分摊、合计（按方案按日累加）。"""
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date 不能早于 start_date")
    if shop_domain:
        if shop_domain not in STORE_OPS_SHOP_DOMAINS:
            raise HTTPException(status_code=400, detail="shop_domain 不在支持列表中")
        shops = [shop_domain]
    else:
        shops = list(STORE_OPS_SHOP_DOMAINS)

    db = get_db()
    buckets = db.fetch_store_ops_daily_buckets(shops, start_date, end_date)
    payload = build_store_ops_report_payload(shops, start_date, end_date, buckets)
    spend_by_shop_slug: Dict[str, Dict[str, Decimal]] = {}
    for s in shops:
        spend_by_shop_slug[s] = db.fetch_store_ops_fb_spend_by_shop_slug(
            s, start_date, end_date
        )
    merge_fb_spend_into_payload(payload, spend_by_shop_slug)
    return {"code": 200, "message": "success", "data": payload}


@router.get("/api/store-ops/sync-run/{sync_run_id}")
async def get_store_ops_sync_run(
    sync_run_id: str,
    _user: Dict[str, Any] = Depends(require_can_view_store_ops),
) -> Dict[str, Any]:
    """查询某次同步批次的明细（含错误列表、按店错误）。"""
    row = get_db().get_store_ops_sync_run(sync_run_id.strip())
    if not row:
        raise HTTPException(status_code=404, detail="未找到该同步批次")
    return {"code": 200, "message": "success", "data": _sync_run_row_to_api(row)}


@router.get("/api/store-ops/sync-runs")
async def list_store_ops_sync_runs(
    limit: int = Query(20, ge=1, le=100, description="返回条数上限"),
    _user: Dict[str, Any] = Depends(require_can_view_store_ops),
) -> Dict[str, Any]:
    """最近若干次同步批次摘要。"""
    rows = get_db().list_store_ops_sync_runs(limit=limit)
    return {
        "code": 200,
        "message": "success",
        "data": {"items": [_sync_run_row_to_api(r) for r in rows]},
    }
