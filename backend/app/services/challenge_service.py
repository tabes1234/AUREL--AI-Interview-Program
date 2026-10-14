"""度衡：限时模拟挑战服务。

- 出题：一次生成全套题目（复用 ArkClient，service 记 question_set）
- 计时：started_at / deadline_at 均为服务端时间（naive UTC），客户端倒计时仅供展示
- 提交：服务端判定是否超时（overtime 如实标记，不阻断提交）；评分复用 scoring.score_interview
"""

from datetime import timedelta

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChallengeRun, utcnow
from app.schemas.challenge import ChallengeAiQuestionSet, ChallengeCreate, ChallengeSubmit
from app.services.ark_client import ArkClient, ArkError
from app.services.scoring import score_interview

MAX_RUNS = 50  # 每用户保留的历史挑战上限

_CREATE_SYSTEM = (
    "你是观澜平台的限时挑战出题官。根据目标岗位与难度出一张限时模拟卷。"
    "要求：题目贴合真实工作场景、总能在限定时间内作答、覆盖不同能力维度。"
    "输出 JSON：{\"questions\": [{\"order_index\": 从1递增, \"content\": 题面, "
    "\"category\": 题型(如 项目/八股/场景/系统设计), \"dimension\": 考察能力维度, "
    "\"rubric\": [评分要点]}]}。"
)


def create_challenge(
    db: Session, user_id: int, request: ChallengeCreate, client: ArkClient
) -> ChallengeRun:
    user_prompt = (
        f"目标岗位：{request.position}\n"
        f"难度：{request.difficulty}\n"
        f"题目数量：{request.question_count}（order_index 1..{request.question_count}）"
    )
    try:
        data = client.chat_json(_CREATE_SYSTEM, user_prompt, temperature=0.5, service="question_set")
    except ArkError as exc:
        raise exc  # 路由层统一映射

    try:
        ai_set = ChallengeAiQuestionSet.model_validate(data)
    except ValidationError as exc:
        raise ArkError(f"AI 生成的挑战题目结构不合格，已放弃创建：{exc}") from exc

    seen = {question.order_index for question in ai_set.questions}
    if seen != set(range(1, request.question_count + 1)):
        raise ArkError("AI 生成的挑战题目序号不完整，已放弃创建")

    ids = db.scalars(
        select(ChallengeRun.id)
        .where(ChallengeRun.user_id == user_id)
        .order_by(ChallengeRun.created_at.desc(), ChallengeRun.id.desc())
        .offset(MAX_RUNS - 1)
    ).all()
    if ids:
        db.query(ChallengeRun).where(ChallengeRun.id.in_(ids)).delete(synchronize_session=False)

    run = ChallengeRun(
        user_id=user_id,
        position=request.position,
        difficulty=request.difficulty,
        question_count=request.question_count,
        duration_minutes=request.duration_minutes,
        questions=[question.model_dump() for question in ai_set.questions],
        model_name=client.model,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def list_challenges(db: Session, user_id: int) -> list[ChallengeRun]:
    return list(
        db.scalars(
            select(ChallengeRun)
            .where(ChallengeRun.user_id == user_id)
            .order_by(ChallengeRun.created_at.desc(), ChallengeRun.id.desc())
        )
    )


def get_run(db: Session, user_id: int, run_id: int) -> ChallengeRun:
    run = db.get(ChallengeRun, run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="挑战不存在")
    return run


def start_run(db: Session, user_id: int, run_id: int) -> ChallengeRun:
    run = get_run(db, user_id, run_id)
    if run.status != "created":
        raise HTTPException(status_code=409, detail="该挑战已开始或已结束")
    run.status = "in_progress"
    run.started_at = utcnow()
    run.deadline_at = run.started_at + timedelta(minutes=run.duration_minutes)
    db.commit()
    db.refresh(run)
    return run


def submit_run(
    db: Session, user_id: int, run_id: int, request: ChallengeSubmit, client: ArkClient
) -> ChallengeRun:
    run = get_run(db, user_id, run_id)
    if run.status != "in_progress":
        raise HTTPException(status_code=409, detail="挑战不在进行中，无法提交")

    now = utcnow()
    run.overtime = run.deadline_at is not None and now > run.deadline_at
    run.submitted_at = now
    run.answers = request.answers

    answer_map = {item.get("order_index"): str(item.get("answer", "")).strip() for item in request.answers}
    qa_pairs = [
        {"question": question["content"], "answer": answer_map.get(question["order_index"], "")}
        for question in run.questions
    ]
    if all(not pair["answer"] for pair in qa_pairs):
        raise HTTPException(status_code=422, detail="所有题目均未作答，无法评分")

    run.status = "evaluating"
    db.commit()
    try:
        scoring = score_interview(
            client,
            position=run.position,
            difficulty=run.difficulty,
            language=run.language,
            qa_pairs=qa_pairs,
        )
    except ArkError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        db.commit()
        raise exc  # 路由层统一映射

    run.status = "completed"
    run.overall_score = scoring.overall_score
    run.result = scoring.model_dump()
    db.commit()
    db.refresh(run)
    return run
