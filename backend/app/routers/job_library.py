"""知潮路由：真实岗位目录、检索、导入、收藏、来源核验与模块联动（按登录用户隔离）。

联动全部复用现有服务：
- 知岗解析：jd_analysis（结构化校验 + 证据核验，绝不编造）
- 问澜出题：interview_service.create_task（现有题集生成流程）
- 合契匹配：jd_matching.match_analysis_with_resume（可解释匹配）
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import JobAnalysis, JobFavorite, JobPosition
from app.routers.interviews import get_ark_client
from app.schemas.interview import InterviewCreateRequest
from app.schemas.job_library import (
    JobAnalyzeFromPositionRequest,
    JobMatchFromPositionRequest,
    JobPositionDetail,
    JobPositionImportRequest,
    JobPositionImportResponse,
    JobPositionListResponse,
    JobPositionOut,
)
from app.schemas.jobs import JobResumeMatchRequest, JobResumeMatchResponse
from app.schemas.resume import ResumeContent
from app.services import (
    career_analyst,
    interview_service,
    jd_analysis,
    jd_matching,
    job_library,
    resume_service,
)
from app.services.ark_client import ArkClient, ArkError

router = APIRouter(prefix="/api/v1/job-library", tags=["job-library"])


def _favorite_ids(db: Session, user_id: int) -> set[int]:
    return set(
        db.scalars(select(JobFavorite.position_id).where(JobFavorite.user_id == user_id))
    )


def _out(position: JobPosition, favorites: set[int]) -> JobPositionOut:
    return JobPositionOut(
        id=position.id,
        company=position.company,
        company_url=position.company_url,
        title=position.title,
        industry_id=position.industry_id,
        industry_name=job_library.industry_name(position.industry_id),
        occupation_id=position.occupation_id,
        occupation_name=job_library.occupation_name(position.occupation_id),
        location=position.location,
        level=position.level,
        published_at=position.published_at,
        published_note=position.published_note,
        source_updated_at=position.source_updated_at,
        source_url=position.source_url,
        source_type=position.source_type,
        display_permission=position.display_permission,
        responsibilities_summary=position.responsibilities_summary,
        required_skills_summary=position.required_skills_summary,
        preferred_skills_summary=position.preferred_skills_summary,
        experience_summary=position.experience_summary,
        hiring_status=position.hiring_status,
        link_status=position.link_status,
        last_verified_at=position.last_verified_at,
        verified_note=position.verified_note,
        stale_hint=job_library.stale_hint(position),
        is_favorited=position.id in favorites,
        imported_by=position.imported_by,
        created_at=position.created_at,
    )


# ---------- 目录与检索 ----------


@router.get("", response_model=JobPositionListResponse)
def list_positions(
    q: str | None = None,
    industry_id: str | None = None,
    occupation_id: str | None = None,
    location: str | None = None,
    level: str | None = None,
    company: str | None = None,
    stage: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> JobPositionListResponse:
    """岗位目录检索：行业/职业/关键词/地点/级别/企业/经验阶段过滤。

    目录为全站共享的岗位资料库（只读），任何分类无数据时返回空列表，
    前端显示空状态——绝不用固定职位或虚假薪资填充。
    """
    rows, total = job_library.search_positions(
        db,
        q=q, industry_id=industry_id, occupation_id=occupation_id,
        location=location, level=level, company=company, stage=stage,
        limit=limit, offset=offset,
    )
    favorites = _favorite_ids(db, user_id)
    return JobPositionListResponse(
        items=[_out(p, favorites) for p in rows],
        total=total, limit=min(max(limit, 1), 100), offset=max(offset, 0),
    )


@router.get("/favorites", response_model=JobPositionListResponse)
def list_favorites(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> JobPositionListResponse:
    rows, total = job_library.search_positions(db, favorite_user_id=user_id, limit=100)
    favorites = _favorite_ids(db, user_id)
    return JobPositionListResponse(
        items=[_out(p, favorites) for p in rows], total=total, limit=100, offset=0
    )


@router.get("/{position_id}", response_model=JobPositionDetail)
def get_position(
    position_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> JobPositionDetail:
    position = job_library.get_position(db, position_id)
    detail = JobPositionDetail(
        **_out(position, _favorite_ids(db, user_id)).model_dump(),
        changes=[
            {
                "id": c.id,
                "change_type": c.change_type,
                "note": c.note,
                "created_at": c.created_at,
            }
            for c in job_library.list_changes(db, position.id)
        ],
    )
    return detail


# ---------- 导入 ----------


@router.post("", response_model=JobPositionImportResponse, status_code=201)
def import_position(
    request: JobPositionImportRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> JobPositionImportResponse:
    """导入真实岗位：须提供可验证的来源链接或选择手动录入；重复内容幂等返回。"""
    position, is_new = job_library.import_position(db, **request.model_dump(), user_id=user_id)
    favorites = _favorite_ids(db, user_id)
    return JobPositionImportResponse(
        position=_out(position, favorites), is_duplicate=not is_new
    )


# ---------- 收藏 ----------


@router.post("/{position_id}/favorite", status_code=204)
def add_favorite(
    position_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    position = job_library.get_position(db, position_id)
    exists = db.scalar(
        select(JobFavorite).where(
            JobFavorite.user_id == user_id, JobFavorite.position_id == position.id
        )
    )
    if exists is None:
        db.add(JobFavorite(user_id=user_id, position_id=position.id))
        db.commit()


@router.delete("/{position_id}/favorite", status_code=204)
def remove_favorite(
    position_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    favorite = db.scalar(
        select(JobFavorite).where(
            JobFavorite.user_id == user_id, JobFavorite.position_id == position_id
        )
    )
    if favorite is not None:
        db.delete(favorite)
        db.commit()


# ---------- 来源核验 ----------


@router.post("/{position_id}/verify", response_model=JobPositionOut)
def verify_source(
    position_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> JobPositionOut:
    """单次访问来源链接核验有效性；只判断链接，不据此断定招聘状态。"""
    position = job_library.get_position(db, position_id)
    position = job_library.verify_source(db, position, actor_id=user_id)
    return _out(position, _favorite_ids(db, user_id))


# ---------- 知岗 / 问澜 / 合契联动 ----------


def _compose_analysis_text(position: JobPosition) -> str:
    """库内岗位的分析输入：优先 JD 原文，否则用事实性摘要拼装。"""
    if position.jd_full_text and position.jd_full_text.strip():
        return position.jd_full_text.strip()[: jd_analysis.MAX_JD_CHARS]
    parts = [
        f"岗位名称：{position.title}",
        f"来源企业：{position.company}",
    ]
    if position.location:
        parts.append(f"工作地点：{position.location}")
    if position.level:
        parts.append(f"岗位级别/招聘类型：{position.level}")
    industry = job_library.industry_name(position.industry_id)
    if industry:
        parts.append(f"所属行业：{industry}")
    if position.responsibilities_summary:
        parts.append(f"工作职责摘要：{position.responsibilities_summary}")
    if position.required_skills_summary:
        parts.append(f"必需技能摘要：{position.required_skills_summary}")
    if position.preferred_skills_summary:
        parts.append(f"加分技能摘要：{position.preferred_skills_summary}")
    if position.experience_summary:
        parts.append(f"经验要求摘要：{position.experience_summary}")
    parts.append("（以上为岗位资料库保存的事实性摘要，完整职位描述以来源页面为准）")
    return "\n".join(parts)


def _ensure_analysis(
    db: Session, client: ArkClient, position: JobPosition, user_id: int, *, force_new: bool
) -> tuple[JobAnalysis, bool]:
    """取得该用户对该岗位的可用解析：复用已有（reused=True），否则真实调用知岗解析并落库。"""
    if not force_new:
        latest = db.scalar(
            select(JobAnalysis)
            .where(
                JobAnalysis.user_id == user_id,
                JobAnalysis.source_job_id == position.id,
                JobAnalysis.status == "ready",
            )
            .order_by(JobAnalysis.created_at.desc(), JobAnalysis.id.desc())
            .limit(1)
        )
        if latest is not None:
            return latest, True

    jd_text = _compose_analysis_text(position)
    if len(jd_text) < jd_analysis.MIN_JD_CHARS:
        raise HTTPException(
            status_code=422,
            detail="该岗位资料内容过少，无法解析；请查看企业原始岗位后粘贴完整 JD",
        )
    try:
        result, model_name = jd_analysis.analyze_jd(client, jd_text)
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc

    fingerprint = jd_analysis.jd_fingerprint(jd_text)
    previous_no = db.scalar(
        select(JobAnalysis.version_no)
        .where(
            JobAnalysis.user_id == user_id,
            JobAnalysis.source_job_id == position.id,
        )
        .order_by(JobAnalysis.version_no.desc())
        .limit(1)
    )
    analysis = JobAnalysis(
        user_id=user_id,
        title=position.title[:120],
        jd_text=jd_text,
        jd_hash=fingerprint,
        version_no=(previous_no or 0) + 1,
        status="ready",
        result=result.model_dump(),
        model_name=model_name,
        source_job_id=position.id,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis, False


@router.post("/{position_id}/analyze", status_code=201)
def analyze_from_position(
    position_id: int,
    request: JobAnalyzeFromPositionRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
):
    """把库内真实岗位送入知岗解析（复用 jd_analysis，证据核验规则不变）。"""
    position = job_library.get_position(db, position_id)
    analysis, reused = _ensure_analysis(db, client, position, user_id, force_new=request.force_new)
    return {
        "job_analysis_id": analysis.id,
        "reused": reused,
        "position_name": (analysis.result or {}).get("position_name", analysis.title),
    }


@router.post("/{position_id}/interview-task", status_code=201)
def interview_from_position(
    position_id: int,
    request: JobAnalyzeFromPositionRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
):
    """把库内岗位作为问澜出题条件：先确保知岗解析，再复用现有题集生成流程。"""
    position = job_library.get_position(db, position_id)
    analysis, _ = _ensure_analysis(db, client, position, user_id, force_new=request.force_new)
    description = jd_analysis.compose_interview_description(analysis.result, analysis.jd_text)
    interview_request = InterviewCreateRequest(
        position=position.title[:120],
        description=description,
        difficulty="intermediate",
        language="zh",
        question_count=3,
    )
    try:
        task = interview_service.create_task(db, interview_request, client, user_id=user_id)
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc
    from app.routers.interviews import _task_detail

    return _task_detail(task)


@router.post("/{position_id}/match", response_model=JobResumeMatchResponse, status_code=201)
def match_from_position(
    position_id: int,
    request: JobMatchFromPositionRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
):
    """把库内岗位加入合契匹配：真实岗位 + 知岗解析 + 用户简历的可解释匹配。"""
    position = job_library.get_position(db, position_id)
    analysis, _ = _ensure_analysis(db, client, position, user_id, force_new=False)
    if analysis.status != "ready" or analysis.result is None:
        raise HTTPException(status_code=409, detail="该岗位解析尚未成功完成，无法进行匹配")
    resume = resume_service.get_owned_resume(db, request.resume_id, user_id)
    content = ResumeContent(**resume.content)

    match = jd_matching.match_analysis_with_resume(
        client,
        jd_text=analysis.jd_text,
        analysis_result=analysis.result,
        resume_content=content,
    )
    return JobResumeMatchResponse(
        job_analysis_id=analysis.id,
        resume_id=resume.id,
        resume_title=resume.title,
        **match,
    )


# ---------- 知途联动 ----------


@router.post("/{position_id}/career-plan", status_code=201)
def career_plan_from_position(
    position_id: int,
    request: JobAnalyzeFromPositionRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
):
    """把库内岗位加入知途规划：先确保知岗解析，再复用现有 7/30/90 天规划生成。

    规划真实落库并携带岗位解析依据（job_analysis_id），失败如实报错；
    每次生成独立新计划，历史版本不覆盖（与知途规划行为一致）。
    """
    position = job_library.get_position(db, position_id)
    analysis, reused = _ensure_analysis(db, client, position, user_id, force_new=request.force_new)
    try:
        plan = career_analyst.generate_plan(
            db, client, user_id,
            job_analysis_id=analysis.id,
            goal=position.title,
        )
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "plan_id": plan.id,
        "plan_title": plan.title,
        "focus_role": plan.focus_role,
        "job_analysis_id": analysis.id,
        "reused_analysis": reused,
    }
