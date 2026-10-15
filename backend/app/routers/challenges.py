"""度衡路由：限时挑战的创建 / 开始 / 提交 / 历史与详情。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.routers.interviews import get_ark_client
from app.schemas.challenge import (
    ChallengeCreate,
    ChallengeOut,
    ChallengeSubmit,
)
from app.services import challenge_service
from app.services.ark_client import ArkClient, ArkError
from app.services.interview_service import map_ark_error
from app.services.usage_tracking import record_event

router = APIRouter(prefix="/api/v1/challenges", tags=["challenges"])


@router.post("", response_model=ChallengeOut, status_code=201)
def create(
    request: ChallengeCreate,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> ChallengeOut:
    try:
        run = challenge_service.create_challenge(db, user_id, request, client)
    except ArkError as exc:
        raise map_ark_error(exc) from exc
    record_event(db, user_id=user_id, module="duheng", name="challenge_create")
    db.commit()
    return ChallengeOut.model_validate(run, from_attributes=True)


@router.get("", response_model=list[ChallengeOut])
def list_challenges(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> list[ChallengeOut]:
    return [
        ChallengeOut.model_validate(run, from_attributes=True)
        for run in challenge_service.list_challenges(db, user_id)
    ]


@router.get("/{run_id}", response_model=ChallengeOut)
def get_challenge(
    run_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ChallengeOut:
    run = challenge_service.get_run(db, user_id, run_id)
    return ChallengeOut.model_validate(run, from_attributes=True)


@router.post("/{run_id}/start", response_model=ChallengeOut)
def start(
    run_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ChallengeOut:
    """开始作答：服务端设定截止时间（deadline 以服务端时钟为准）。"""
    run = challenge_service.start_run(db, user_id, run_id)
    return ChallengeOut.model_validate(run, from_attributes=True)


@router.post("/{run_id}/submit", response_model=ChallengeOut)
def submit(
    run_id: int,
    request: ChallengeSubmit,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> ChallengeOut:
    """提交答卷：服务端判定超时并评分（失败如实标记 failed，不伪造结果）。"""
    try:
        run = challenge_service.submit_run(db, user_id, run_id, request, client)
    except ArkError as exc:
        raise map_ark_error(exc) from exc
    record_event(db, user_id=user_id, module="duheng", name="challenge_submit")
    db.commit()
    return ChallengeOut.model_validate(run, from_attributes=True)
