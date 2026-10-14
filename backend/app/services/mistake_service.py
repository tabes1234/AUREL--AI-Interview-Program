"""回澜错题本：收集问澜题目 + SM-2 间隔重复调度。

SM-2（SuperMemo-2）经典实现：
- 每次复习按回忆质量打分 q∈[0,5]
- q≥3：连续成功次数 +1；间隔依次 1 天 → 6 天 → 上一间隔 × EF
- q<3：重置为 1 天后复习，连续成功清零
- EF' = EF + (0.1 − (5−q) × (0.08 + (5−q) × 0.02))，下限 1.3
- 到期时间 = 本次复习时间 + 新间隔
"""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import InterviewAnswer, InterviewQuestion, InterviewTask, MistakeCard, utcnow


def collect_question(
    db: Session, user_id: int, question_id: int, my_answer: str
) -> MistakeCard:
    """从问澜题目创建错题卡（题目必须属于当前用户已完成的任务）。"""
    question = db.get(InterviewQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    task = db.get(InterviewTask, question.task_id)
    if task is None or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="题目不存在")

    existing = db.scalar(
        select(MistakeCard).where(
            MistakeCard.user_id == user_id, MistakeCard.question_id == question_id
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="该题目已在错题本中")

    answer = db.scalar(
        select(InterviewAnswer).where(InterviewAnswer.question_id == question_id)
    )
    card = MistakeCard(
        user_id=user_id,
        question_id=question_id,
        position=task.position,
        question_content=question.content,
        category=question.category,
        dimension=question.dimension,
        goal=question.goal,
        rubric=question.rubric,
        my_answer=(my_answer.strip() or (answer.content if answer else "")),
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def apply_sm2(db: Session, card: MistakeCard, grade: int) -> MistakeCard:
    """对单卡应用一次 SM-2 复习调度。"""
    if grade >= 3:
        card.repetitions += 1
        if card.repetitions == 1:
            card.interval_days = 1
        elif card.repetitions == 2:
            card.interval_days = 6
        else:
            card.interval_days = max(1, round(card.interval_days * card.ease_factor))
    else:
        card.repetitions = 0
        card.interval_days = 1

    q = grade
    card.ease_factor = max(
        1.3, card.ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    )
    card.due_at = utcnow() + timedelta(days=card.interval_days)
    card.last_grade = grade
    card.last_reviewed_at = utcnow()
    card.review_count += 1
    db.commit()
    db.refresh(card)
    return card


def review_card(db: Session, user_id: int, card_id: int, grade: int) -> MistakeCard:
    card = db.get(MistakeCard, card_id)
    if card is None or card.user_id != user_id:
        raise HTTPException(status_code=404, detail="错题卡不存在")
    return apply_sm2(db, card, grade)


def list_cards(db: Session, user_id: int) -> dict:
    cards = list(
        db.scalars(
            select(MistakeCard)
            .where(MistakeCard.user_id == user_id)
            .order_by(MistakeCard.due_at.asc(), MistakeCard.id.asc())
        )
    )
    now = utcnow()
    due_count = sum(1 for card in cards if card.due_at <= now)
    return {"total": len(cards), "due_count": due_count, "cards": cards}


def delete_card(db: Session, user_id: int, card_id: int) -> None:
    card = db.get(MistakeCard, card_id)
    if card is None or card.user_id != user_id:
        raise HTTPException(status_code=404, detail="错题卡不存在")
    db.delete(card)
    db.commit()


def mastered_count(db: Session, user_id: int) -> int:
    """已掌握（连续成功 ≥3 次）的卡片数，供进度展示。"""
    return int(
        db.scalar(
            select(func.count())
            .select_from(MistakeCard)
            .where(MistakeCard.user_id == user_id, MistakeCard.repetitions >= 3)
        )
        or 0
    )
