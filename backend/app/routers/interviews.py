"""面试任务 API：创建、列表、详情、回答、追问流转、完成与报告。

所有面试数据按登录用户隔离；访问他人任务一律返回 404（不暴露存在性）。
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import InterviewQuestion, InterviewReport, InterviewTask
from app.schemas.interview import (
    AiStatusResponse,
    AnswerCreateRequest,
    AnswerResponse,
    FinishResponse,
    InterviewCreateRequest,
    QuestionOut,
    QuestionSetGenerateRequest,
    ReportOut,
    TaskDetail,
    TaskSummary,
)
from app.services import interview_service
from app.services.ark_client import ArkClient, ArkError
from app.services.usage_tracking import record_event

router = APIRouter(prefix="/api/v1", tags=["interviews"])


def get_ark_client() -> ArkClient:
    return ArkClient()


def _owned_task(db: Session, task_id: int, user_id: int) -> InterviewTask:
    task = interview_service.get_task(db, task_id)
    if task.user_id != user_id:
        raise HTTPException(status_code=404, detail="面试任务不存在")
    return task


def _question_out(question: InterviewQuestion) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        order_index=question.order_index,
        type=question.type,  # type: ignore[arg-type]
        parent_question_id=question.parent_question_id,
        content=question.content,
        answer=question.answer.content if question.answer else None,
        category=question.category,
        dimension=question.dimension,
        goal=question.goal,
        rubric=question.rubric,
        suggested_follow_up=question.suggested_follow_up,
    )


def _task_summary(task: InterviewTask) -> TaskSummary:
    return TaskSummary(
        id=task.id,
        position=task.position,
        difficulty=task.difficulty,  # type: ignore[arg-type]
        language=task.language,  # type: ignore[arg-type]
        question_count=task.question_count,
        status=task.status,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        overall_score=task.report.overall_score if task.report else None,
        industry_id=task.industry_id,
        occupation_id=task.occupation_id,
        experience_level=task.experience_level,
        interview_type=task.interview_type,
    )


def _task_detail(task: InterviewTask) -> TaskDetail:
    current = interview_service.current_question(task)
    return TaskDetail(
        **_task_summary(task).model_dump(),
        description=task.description,
        questions=[_question_out(q) for q in sorted(task.questions, key=lambda q: q.id)],
        current_question_id=current.id if current else None,
    )


@router.post("/interviews", response_model=TaskDetail, status_code=201)
def create_interview(
    request: InterviewCreateRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> TaskDetail:
    try:
        task = interview_service.create_task(db, request, client, user_id=user_id)
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc
    record_event(db, user_id=user_id, module="wenlan", name="task_create")
    db.commit()
    return _task_detail(task)


@router.post("/interviews/generate-questions", response_model=TaskDetail, status_code=201)
def generate_question_set(
    request: QuestionSetGenerateRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> TaskDetail:
    """问澜：按行业/职业目录生成结构化题集（服务端双重校验，失败不伪造成功）。

    注意：必须注册在 /interviews/{task_id} 之前，避免路径参数吞掉该固定路径。
    """
    try:
        task = interview_service.create_task_from_catalog(db, request, client, user_id=user_id)
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc
    record_event(db, user_id=user_id, module="wenlan", name="task_create")
    db.commit()
    return _task_detail(task)


@router.get("/interviews", response_model=list[TaskSummary])
def list_interviews(
    limit: int = 50,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> list[TaskSummary]:
    tasks = interview_service.list_tasks(db, limit=min(max(limit, 1), 100), user_id=user_id)
    return [_task_summary(task) for task in tasks]


@router.get("/interviews/{task_id}", response_model=TaskDetail)
def get_interview(
    task_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> TaskDetail:
    task = _owned_task(db, task_id, user_id)
    return _task_detail(task)


@router.post("/interviews/{task_id}/answers", response_model=AnswerResponse)
def submit_answer(
    task_id: int,
    request: AnswerCreateRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> AnswerResponse:
    task = _owned_task(db, task_id, user_id)
    try:
        next_question, all_answered = interview_service.submit_answer(db, task, request, client)
    except interview_service.TaskFlowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc

    return AnswerResponse(
        task_status=task.status,
        answered_question_id=request.question_id,
        next_question=_question_out(next_question) if next_question else None,
        all_answered=all_answered,
    )


@router.post("/interviews/{task_id}/next", response_model=AnswerResponse)
def resolve_next(
    task_id: int,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> AnswerResponse:
    """幂等重试：重新决定下一个问题（追问生成失败后的恢复入口）。"""
    task = _owned_task(db, task_id, user_id)
    try:
        next_question, all_answered = interview_service.resolve_next(db, task, client)
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc

    last_answered = next(
        (q for q in reversed(sorted(task.questions, key=lambda q: q.id)) if q.answer is not None),
        None,
    )
    return AnswerResponse(
        task_status=task.status,
        answered_question_id=last_answered.id if last_answered else 0,
        next_question=_question_out(next_question) if next_question else None,
        all_answered=all_answered,
    )


@router.post("/interviews/{task_id}/finish", response_model=FinishResponse)
def finish_interview(
    task_id: int,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> FinishResponse:
    task = _owned_task(db, task_id, user_id)
    try:
        report = interview_service.finish_task(db, task, client)
    except interview_service.TaskFlowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc
    record_event(db, user_id=user_id, module="wenlan", name="report_generate")
    db.commit()
    return FinishResponse(task_id=task.id, status=task.status, report_id=report.id)


@router.get("/interviews/{task_id}/report", response_model=ReportOut)
def get_report(
    task_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ReportOut:
    task = _owned_task(db, task_id, user_id)
    report: InterviewReport | None = task.report
    if report is None:
        raise HTTPException(status_code=404, detail="报告尚未生成")
    return ReportOut(
        id=report.id,
        task_id=report.task_id,
        overall_score=report.overall_score,
        summary=report.summary,
        dimensions=report.dimensions,
        strengths=report.strengths,
        improvements=report.improvements,
        model_name=report.model_name,
        created_at=report.created_at,
        position=task.position,
        difficulty=task.difficulty,  # type: ignore[arg-type]
        language=task.language,  # type: ignore[arg-type]
    )


@router.get("/ai/status", response_model=AiStatusResponse)
def ai_status(client: ArkClient = Depends(get_ark_client)) -> AiStatusResponse:
    from app.config import ark_base_url

    try:
        client.ensure_configured()
    except ArkError as exc:
        return AiStatusResponse(
            configured=False,
            model=client.model or None,
            base_url=ark_base_url(),
            message=str(exc),
        )
    return AiStatusResponse(
        configured=True,
        model=client.model,
        base_url=ark_base_url(),
        message=f"已配置：{client.model}",
    )
