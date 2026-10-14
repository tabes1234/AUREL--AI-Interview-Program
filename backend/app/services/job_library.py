"""知潮：真实岗位资料库服务。

数据真实性原则：
- 种子数据与用户导入都必须带真实来源；绝不编造岗位。
- 来源未提供发布时间 → published_at 为空，如实标注，不伪造时间。
- 无法确认招聘状态 → hiring_status="unconfirmed"，不默认「正在招聘」。
- 公开展示遵循 display_permission：默认 summary_only（事实性摘要 + 原文链接），
  完整 JD 原文不进入公开目录展示，仅用于知岗解析。
- 来源链接核验为单次适度访问（用户触发），不做定时批量抓取；
  超过 STALE_AFTER_DAYS 未核验的岗位在列表中标注「可能已过期」。
"""

import hashlib
import ipaddress
import json
import socket
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import JobFavorite, JobPosition, JobPositionChange, utcnow
from app.services import catalog

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "job_seed.json"
STALE_AFTER_DAYS = 30
VERIFY_TIMEOUT_SECONDS = 10
MAX_VERIFY_BYTES = 2 * 1024 * 1024

SOURCE_TYPES = {"official_seed", "user_import", "manual"}
HIRING_STATUSES = {"unconfirmed", "open", "closed"}
MAX_IMPORT_CHARS = 20_000


def content_fingerprint(*parts: str) -> str:
    """内容哈希：岗位关键内容变化时哈希随之变化，用于重复检测与变化识别。"""
    normalized = "\n".join(p.strip() for p in parts if p).lower()
    return hashlib.sha256("".join(normalized.split()).encode("utf-8")).hexdigest()


def position_fingerprint(position: JobPosition) -> str:
    return content_fingerprint(
        position.company, position.title, position.location,
        position.responsibilities_summary, position.required_skills_summary,
    )


# ---------- 种子导入（幂等） ----------


def seed_job_positions(db: Session) -> int:
    """把官方页面人工核对过的种子岗位导入资料库；按内容指纹幂等跳过。"""
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    verified_on = raw.get("verified_on", "")
    created = 0
    for item in raw["positions"]:
        fingerprint = content_fingerprint(
            item["company"], item["title"], item.get("location", ""),
            item.get("responsibilities_summary", ""), item.get("required_skills_summary", ""),
        )
        exists = db.scalar(
            select(JobPosition.id).where(JobPosition.content_hash == fingerprint)
        )
        if exists:
            continue
        verified_at = datetime.fromisoformat(verified_on) if verified_on else None
        fallback_note = (
            f"{verified_on} 人工核对官方招聘页面" if verified_on else None
        )
        position = JobPosition(
            company=item["company"][:80],
            company_url=item.get("company_url"),
            title=item["title"][:120],
            industry_id=item.get("industry_id"),
            occupation_id=item.get("occupation_id"),
            location=item.get("location", "")[:200],
            level=item.get("level", "")[:40],
            published_at=None,
            published_note=item.get("published_note", "来源未提供发布时间")[:60],
            source_updated_at=(
                datetime.fromisoformat(item["source_updated_at"])
                if item.get("source_updated_at") else None
            ),
            source_url=item.get("source_url"),
            source_type="official_seed",
            display_permission=item.get("display_permission", "summary_only"),
            responsibilities_summary=item.get("responsibilities_summary", ""),
            required_skills_summary=item.get("required_skills_summary", ""),
            preferred_skills_summary=item.get("preferred_skills_summary", ""),
            experience_summary=item.get("experience_summary", "")[:300],
            jd_full_text=None,
            content_hash=fingerprint,
            hiring_status="unconfirmed",
            link_status="ok" if item.get("source_url") else "unverified",
            last_verified_at=verified_at,
            verified_note=item.get("verified_note") or fallback_note,
        )
        db.add(position)
        db.flush()
        db.add(JobPositionChange(
            position_id=position.id,
            change_type="created",
            content_hash=fingerprint,
            note=f"种子导入（官方页面人工核对，来源类型 official_seed）",
        ))
        created += 1
    db.commit()
    return created


# ---------- 查询与展示 ----------


def stale_hint(position: JobPosition) -> bool:
    """长期未核验的岗位视为「可能已过期」（仅提示，不改动数据）。"""
    if position.link_status == "dead":
        return True
    if position.last_verified_at is None:
        return False
    return (utcnow() - position.last_verified_at) > timedelta(days=STALE_AFTER_DAYS)


def get_position(db: Session, position_id: int) -> JobPosition:
    position = db.get(JobPosition, position_id)
    if position is None:
        raise HTTPException(status_code=404, detail="岗位不存在或已被移除")
    return position


def search_positions(
    db: Session,
    *,
    q: str | None = None,
    industry_id: str | None = None,
    occupation_id: str | None = None,
    location: str | None = None,
    level: str | None = None,
    company: str | None = None,
    stage: str | None = None,
    favorite_user_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[JobPosition], int]:
    """多条件检索岗位目录；任何条件组合无数据时返回空列表（前端显示空状态）。"""
    statement = select(JobPosition)
    if favorite_user_id is not None:
        favorite_ids = select(JobFavorite.position_id).where(
            JobFavorite.user_id == favorite_user_id
        )
        statement = statement.where(JobPosition.id.in_(favorite_ids))
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            JobPosition.title.ilike(pattern)
            | JobPosition.company.ilike(pattern)
            | JobPosition.location.ilike(pattern)
            | JobPosition.responsibilities_summary.ilike(pattern)
            | JobPosition.required_skills_summary.ilike(pattern)
        )
    if industry_id:
        statement = statement.where(JobPosition.industry_id == industry_id)
    if occupation_id:
        statement = statement.where(JobPosition.occupation_id == occupation_id)
    if location:
        statement = statement.where(JobPosition.location.ilike(f"%{location.strip()}%"))
    if level:
        statement = statement.where(JobPosition.level.ilike(f"%{level.strip()}%"))
    if company:
        statement = statement.where(JobPosition.company.ilike(f"%{company.strip()}%"))
    if stage == "campus":
        statement = statement.where(JobPosition.level.ilike("%校招%") | JobPosition.level.ilike("%实习%"))
    elif stage == "experienced":
        statement = statement.where(JobPosition.level.ilike("%社招%"))

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(
        statement.order_by(
            JobPosition.source_updated_at.desc().nullslast(),
            JobPosition.created_at.desc(),
        ).limit(min(max(limit, 1), 100)).offset(max(offset, 0))
    )
    return list(rows), int(total)


def industry_name(industry_id: str | None) -> str | None:
    if not industry_id:
        return None
    for item in catalog.list_industries():
        if item["id"] == industry_id:
            return item["name"]
    return None


def occupation_name(occupation_id: str | None) -> str | None:
    if not occupation_id:
        return None
    for item in catalog.list_occupations():
        if item["id"] == occupation_id:
            return item["name"]
    return None


# ---------- 导入 ----------


def _validate_catalog_refs(industry_id: str | None, occupation_id: str | None) -> None:
    if industry_id and industry_name(industry_id) is None:
        raise HTTPException(status_code=422, detail="所属行业不在目录中，请从行业目录选择")
    if occupation_id and occupation_name(occupation_id) is None:
        raise HTTPException(status_code=422, detail="职业分类不在目录中，请从职业目录选择")


def import_position(
    db: Session,
    *,
    company: str,
    title: str,
    location: str = "",
    level: str = "",
    industry_id: str | None = None,
    occupation_id: str | None = None,
    source_url: str | None = None,
    responsibilities_summary: str = "",
    required_skills_summary: str = "",
    preferred_skills_summary: str = "",
    experience_summary: str = "",
    jd_full_text: str | None = None,
    hiring_status: str = "unconfirmed",
    display_permission: str = "summary_only",
    user_id: int,
) -> tuple[JobPosition, bool]:
    """用户导入岗位：必须提供可验证的来源链接，或选择手动录入（无链接）。

    返回（岗位, 是否新建）；同一内容重复导入时返回已有记录（is_duplicate=True）。
    """
    _validate_catalog_refs(industry_id, occupation_id)
    if hiring_status not in HIRING_STATUSES:
        raise HTTPException(status_code=422, detail="招聘状态取值不合法")
    if display_permission not in {"summary_only", "full_text"}:
        raise HTTPException(status_code=422, detail="展示权限取值不合法")

    url = (source_url or "").strip() or None
    if url:
        _assert_public_http_url(url)
    else:
        display_permission = "summary_only"

    if not any((responsibilities_summary, required_skills_summary, jd_full_text)):
        raise HTTPException(
            status_code=422,
            detail="请至少填写职责摘要、技能摘要之一，或提供 JD 原文，不得导入空岗位",
        )

    fingerprint = content_fingerprint(
        company, title, location, responsibilities_summary, required_skills_summary
    )
    duplicate = db.scalar(select(JobPosition).where(JobPosition.content_hash == fingerprint))
    if duplicate is not None:
        return duplicate, False

    position = JobPosition(
        company=company.strip()[:80],
        title=title.strip()[:120],
        location=location.strip()[:200],
        level=level.strip()[:40],
        industry_id=industry_id,
        occupation_id=occupation_id,
        published_at=None,
        published_note="来源未提供发布时间",
        source_url=url,
        source_type="user_import" if url else "manual",
        display_permission=display_permission,
        responsibilities_summary=responsibilities_summary.strip(),
        required_skills_summary=required_skills_summary.strip(),
        preferred_skills_summary=preferred_skills_summary.strip(),
        experience_summary=experience_summary.strip()[:300],
        jd_full_text=(jd_full_text or "").strip()[:MAX_IMPORT_CHARS] or None,
        content_hash=fingerprint,
        hiring_status=hiring_status,
        link_status="unverified" if url else "no_link",
        last_verified_at=None,
        verified_note=None,
        imported_by=user_id,
    )
    db.add(position)
    db.flush()
    db.add(JobPositionChange(
        position_id=position.id,
        change_type="created",
        content_hash=fingerprint,
        note="用户导入" if url else "用户手动录入（无来源链接）",
        actor_id=user_id,
    ))
    db.commit()
    db.refresh(position)
    return position, True


# ---------- 来源核验（单次、适度、防 SSRF） ----------


def _assert_public_http_url(url: str) -> None:
    """只允许公网 http(s) 链接：拒绝非 http 协议与内网/环回/链路本地地址。

    导入阶段仅校验格式与主机字面量（不发起 DNS 查询）；真实访问前的 DNS
    解析校验在 verify_source 内执行。
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=422, detail="来源链接必须是有效的 http(s) 地址")
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise HTTPException(status_code=422, detail="来源链接不允许指向本机或内网地址")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return  # 普通域名：导入阶段不做 DNS 解析
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    ):
        raise HTTPException(status_code=422, detail="来源链接不允许指向本机或内网地址")


def _assert_resolvable_public_host(url: str) -> None:
    """真实访问前校验：域名必须可解析且不指向内网/环回地址（防 SSRF）。"""
    parsed = urlparse(url)
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except OSError as exc:
        raise HTTPException(status_code=422, detail=f"来源域名无法解析：{parsed.hostname}") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
        ):
            raise HTTPException(status_code=422, detail="来源链接指向内网地址，已拒绝")


def verify_source(db: Session, position: JobPosition, actor_id: int | None = None) -> JobPosition:
    """单次访问来源链接核验有效性：可访问→ok；页面缺失→dead；网络失败→stale。

    只判断「链接是否仍可打开」，不据此断定岗位是否仍在招聘（hiring_status 不因此改变）。
    """
    if not position.source_url:
        raise HTTPException(status_code=422, detail="该岗位没有来源链接，无法核验")
    _assert_public_http_url(position.source_url)
    _assert_resolvable_public_host(position.source_url)

    status, note = "stale", None
    try:
        response = httpx.get(
            position.source_url,
            timeout=VERIFY_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": "AUREL-LinkCheck/1.0 (source verification)"},
        )
        if response.status_code < 400:
            status, note = "ok", f"来源链接可访问（HTTP {response.status_code}）"
        elif response.status_code in (404, 410):
            status, note = "dead", f"来源页面已失效（HTTP {response.status_code}），已标记待核验"
        else:
            note = f"来源返回 HTTP {response.status_code}，已标记待核验"
    except httpx.HTTPError as exc:
        note = f"来源访问失败（{exc.__class__.__name__}），已标记待核验"

    previous = position.link_status
    position.link_status = status
    position.last_verified_at = utcnow()
    position.verified_note = note[:200]
    db.add(JobPositionChange(
        position_id=position.id,
        change_type="verified" if status == "ok" else "stale",
        content_hash=position.content_hash,
        note=f"链接核验：{previous} → {status}；{note}",
        actor_id=actor_id,
    ))
    db.commit()
    db.refresh(position)
    return position


def record_change(db: Session, position: JobPosition, *, change_type: str, note: str, actor_id: int | None = None) -> None:
    db.add(JobPositionChange(
        position_id=position.id,
        change_type=change_type,
        content_hash=position.content_hash,
        note=note[:300],
        actor_id=actor_id,
    ))


def list_changes(db: Session, position_id: int, limit: int = 20) -> list[JobPositionChange]:
    statement = (
        select(JobPositionChange)
        .where(JobPositionChange.position_id == position_id)
        .order_by(JobPositionChange.created_at.desc(), JobPositionChange.id.desc())
        .limit(min(max(limit, 1), 100))
    )
    return list(db.scalars(statement))
