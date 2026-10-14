"""回澜错题本路由：收集 / 复习 / 列表 / 删除（全部按登录用户隔离）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.schemas.mistake import MistakeCardOut, MistakeCollect, MistakeListResponse, MistakeReview
from app.services import mistake_service

router = APIRouter(prefix="/api/v1/mistakes", tags=["mistakes"])


@router.post("", response_model=MistakeCardOut, status_code=201)
def collect(
    request: MistakeCollect,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> MistakeCardOut:
    card = mistake_service.collect_question(db, user_id, request.question_id, request.my_answer)
    return MistakeCardOut.model_validate(card, from_attributes=True)


@router.get("", response_model=MistakeListResponse)
def list_cards(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> MistakeListResponse:
    data = mistake_service.list_cards(db, user_id)
    return MistakeListResponse(
        total=data["total"],
        due_count=data["due_count"],
        cards=[
            MistakeCardOut.model_validate(card, from_attributes=True) for card in data["cards"]
        ],
    )


@router.post("/{card_id}/review", response_model=MistakeCardOut)
def review(
    card_id: int,
    request: MistakeReview,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> MistakeCardOut:
    """按回忆质量（0-5）提交一次复习，服务端执行 SM-2 调度。"""
    card = mistake_service.review_card(db, user_id, card_id, request.grade)
    return MistakeCardOut.model_validate(card, from_attributes=True)


@router.delete("/{card_id}", status_code=204)
def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    mistake_service.delete_card(db, user_id, card_id)
