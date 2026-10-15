"""管理中心 API：总览、用户、功能、AI、审计与导出。

- 全部接口经 get_admin_user 依赖在服务端校验管理员角色（普通用户 403，未登录 401）；
- 统计逻辑在 services/admin_stats.py，这里只做参数解析、编排与审计；
- 敏感管理操作（账号状态变更、数据导出）写入 admin_audit_logs。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user
from app.models import AdminAuditLog, User, UserSession, utcnow
from app.services import admin_stats
from app.services.admin_stats import RangeError

logger = logging.getLogger("aurel.admin")

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class StatusUpdateRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _check(cls, value: str) -> str:
        if value not in {"active", "disabled"}:
            raise ValueError("状态仅支持 active / disabled")
        return value


def _range_or_400(start: str | None, end: str | None):
    try:
        return admin_stats.parse_range(start, end)
    except RangeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/overview")
def overview(
    start: str | None = Query(None, description="起始日期 YYYY-MM-DD（UTC+8）"),
    end: str | None = Query(None, description="结束日期 YYYY-MM-DD（UTC+8）"),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    utc_start, utc_end, start_iso, end_iso = _range_or_400(start, end)
    data = admin_stats.overview(db, start=utc_start, end=utc_end, start_iso=start_iso, end_iso=end_iso)
    data["recent_activity"] = admin_stats.recent_activity(db, limit=12)
    data["admin"] = {"nickname": _admin.nickname or _admin.username}
    return data


@router.get("/trends")
def trends(
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    utc_start, utc_end, start_iso, end_iso = _range_or_400(start, end)
    return admin_stats.trends(db, start=utc_start, end=utc_end, start_iso=start_iso, end_iso=end_iso)


@router.get("/users")
def users(
    start: str | None = Query(None),
    end: str | None = Query(None),
    q: str | None = Query(None, max_length=60),
    status: str | None = Query(None),
    registered_start: str | None = Query(None),
    registered_end: str | None = Query(None),
    sort: str = Query("created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    utc_start, utc_end, _, _ = _range_or_400(start, end)
    try:
        return admin_stats.users_page(
            db,
            start=utc_start,
            end=utc_end,
            q=q,
            status=status,
            registered_start=registered_start,
            registered_end=registered_end,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    except RangeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/users/{user_id}")
def user_detail(
    user_id: int,
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    utc_start, utc_end, start_iso, end_iso = _range_or_400(start, end)
    return admin_stats.user_detail(
        db, target=target, start=utc_start, end=utc_end, start_iso=start_iso, end_iso=end_iso
    )


@router.post("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    body: StatusUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """暂停/恢复账号（敏感操作：服务端校验 + 审计 + 真实撤销会话）。"""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="不能变更自己的账号状态")
    old_status = target.status
    if old_status == body.status:
        return {"ok": True, "status": target.status, "changed": False}

    target.status = body.status
    if body.status == "disabled":
        # 真实生效：撤销该用户全部会话
        for session in db.scalars(
            select(UserSession).where(
                UserSession.user_id == target.id, UserSession.revoked_at.is_(None)
            )
        ):
            session.revoked_at = utcnow()
    db.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="user_status_update",
            target_type="user",
            target_id=str(target.id),
            detail={"from": old_status, "to": body.status, "username": target.username},
        )
    )
    db.commit()
    return {"ok": True, "status": target.status, "changed": True}


@router.get("/modules")
def modules(
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    utc_start, utc_end, start_iso, end_iso = _range_or_400(start, end)
    return admin_stats.module_stats(
        db, start=utc_start, end=utc_end, start_iso=start_iso, end_iso=end_iso
    )


@router.get("/ai")
def ai(
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    utc_start, utc_end, start_iso, end_iso = _range_or_400(start, end)
    return admin_stats.ai_stats(
        db, start=utc_start, end=utc_end, start_iso=start_iso, end_iso=end_iso, limit=limit
    )


@router.get("/audit")
def audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    return admin_stats.audit_list(db, page=page, page_size=page_size)


@router.get("/export")
def export(
    kind: str = Query("overview"),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """导出脱敏统计数据 CSV（敏感操作：审计留痕）。"""
    utc_start, utc_end, start_iso, end_iso = _range_or_400(start, end)
    try:
        filename, content = admin_stats.export_csv(
            db, kind=kind, start=utc_start, end=utc_end, start_iso=start_iso, end_iso=end_iso
        )
    except RangeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="export_stats",
            target_type="stats",
            target_id=kind,
            detail={"start": start_iso, "end": end_iso, "kind": kind},
        )
    )
    db.commit()
    logger.info("admin export: kind=%s range=%s..%s admin=%s", kind, start_iso, end_iso, admin.id)
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
