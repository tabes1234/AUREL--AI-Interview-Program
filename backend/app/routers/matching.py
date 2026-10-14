"""T9 简历/岗位语义匹配路由：匹配、列表、详情、删除（按登录用户隔离）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import ResumeMatchRecord
from app.routers.interviews import get_ark_client
from app.schemas.features import (
    ResumeMatchDetail,
    ResumeMatchRecordOut,
    ResumeMatchRequest,
    ResumeMatchResponse,
)
from app.services.ark_client import ArkClient
from app.services.matching_service import match_resume

router = APIRouter(prefix="/api/v1/matching", tags=["matching"])


@router.post("/resume", response_model=ResumeMatchResponse, status_code=201)
def match_resume_api(
    request: ResumeMatchRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> ResumeMatchResponse:
    """简历与岗位匹配：统计依据真实可解释；LLM 建议失败时降级并如实标注。"""
    result = match_resume(
        None,
        client,
        position=request.position,
        job_description=request.job_description,
        resume_text=request.resume_text,
    )
    record = ResumeMatchRecord(
        position=request.position.strip(),
        job_description=request.job_description,
        resume_text=request.resume_text,
        result={
            "match_score": result.match_score,
            "matched_skills": result.matched_skills,
            "missing_skills": result.missing_skills,
            "suggestions": result.suggestions,
            "llm_error": result.llm_error,
        },
        model_name=result.model_name,
        user_id=user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return ResumeMatchResponse(
        id=record.id,
        match_score=result.match_score,
        matched_skills=result.matched_skills,
        missing_skills=result.missing_skills,
        suggestions=result.suggestions,
        llm_error=result.llm_error,
        model_name=result.model_name,
    )


@router.get("/records", response_model=list[ResumeMatchRecordOut])
def list_records(
    limit: int = 50,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    statement = (
        select(ResumeMatchRecord)
        .where(ResumeMatchRecord.user_id == user_id)
        .order_by(ResumeMatchRecord.created_at.desc(), ResumeMatchRecord.id.desc())
        .limit(limit)
    )
    records = list(db.scalars(statement))
    return [
        ResumeMatchRecordOut(
            id=r.id,
            position=r.position,
            match_score=r.result.get("match_score", 0.0),
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/records/{record_id}", response_model=ResumeMatchDetail)
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    record = db.get(ResumeMatchRecord, record_id)
    if record is None or record.user_id != user_id:
        raise HTTPException(status_code=404, detail="匹配记录不存在")
    return ResumeMatchDetail(
        id=record.id,
        position=record.position,
        match_score=record.result.get("match_score", 0.0),
        created_at=record.created_at,
        job_description=record.job_description,
        resume_text=record.resume_text,
        result=record.result,
        model_name=record.model_name,
    )


@router.delete("/records/{record_id}", status_code=204)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    record = db.get(ResumeMatchRecord, record_id)
    if record is None or record.user_id != user_id:
        raise HTTPException(status_code=404, detail="匹配记录不存在")
    db.delete(record)
    db.commit()
