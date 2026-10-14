"""面试流程业务编排：创建任务、回答流转、追问决策、报告生成。"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InterviewAnswer, InterviewQuestion, InterviewReport, InterviewTask, KnowledgeDocument
from app.schemas.interview import (
    AnswerCreateRequest,
    InterviewCreateRequest,
    QuestionSetGenerateRequest,
)
from app.services import catalog as catalog_service
from app.services import follow_up as follow_up_service
from app.services import knowledge_service, question_generator, scoring
from app.services.ark_client import ArkClient, ArkError, ArkNotConfiguredError


class TaskFlowError(Exception):
    """流程状态错误（请求与任务状态不匹配）。"""


def get_task(db: Session, task_id: int) -> InterviewTask:
    task = db.get(InterviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="面试任务不存在")
    return task


def get_question(db: Session, task: InterviewTask, question_id: int) -> InterviewQuestion:
    question = db.get(InterviewQuestion, question_id)
    if question is None or question.task_id != task.id:
        raise HTTPException(status_code=404, detail="问题不存在或不属于该任务")
    return question


def create_task(
    db: Session, request: InterviewCreateRequest, client: ArkClient, *, user_id: int
) -> InterviewTask:
    """创建任务并同步生成问题。失败时任务落库为 failed 并抛出真实错误。

    T2 RAG：指定 knowledge_document_id 时，从该文档检索 top 证据注入出题依据。
    """
    evidence_texts: list[str] = []
    if request.knowledge_document_id is not None:
        document = db.get(KnowledgeDocument, request.knowledge_document_id)
        if document is None or document.user_id != user_id:
            raise HTTPException(status_code=404, detail="指定的知识库文档不存在")
        # 在所选文档的分块内做 BM25 检索，取最相关证据注入出题依据
        evidence_texts = knowledge_service.retrieve_from_document(
            document,
            query=f"{request.position}\n{request.description}".strip() or request.position,
            top_k=3,
        )

    task = InterviewTask(
        position=request.position.strip(),
        description=request.description.strip(),
        difficulty=request.difficulty,
        language=request.language,
        question_count=request.question_count,
        status="generating_questions",
        user_id=user_id,
    )
    db.add(task)
    db.commit()

    try:
        questions = question_generator.generate_questions(
            client,
            position=task.position,
            description=task.description,
            difficulty=task.difficulty,
            language=task.language,
            question_count=task.question_count,
            evidence_texts=evidence_texts,
        )
    except ArkError as exc:
        task.status = "failed"
        task.error_message = f"问题生成失败：{exc}"
        db.commit()
        raise

    for index, content in enumerate(questions, start=1):
        db.add(
            InterviewQuestion(
                task_id=task.id,
                order_index=index,
                type="main",
                content=content,
            )
        )
    task.status = "ready"
    task.error_message = None
    db.commit()
    db.refresh(task)
    return task


def create_task_from_catalog(
    db: Session, request: QuestionSetGenerateRequest, client: ArkClient, *, user_id: int
) -> InterviewTask:
    """问澜：按行业/职业目录创建任务并生成结构化题集。

    服务端强制校验行业-职业组合；模型校验失败有限重试；失败任务真实落库，不伪造成功。
    """
    try:
        occupation_name, industry_name, occupation_profile = catalog_service.resolve_occupation(
            request.industry_id, request.occupation_id, request.custom_occupation
        )
    except catalog_service.CatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    evidence_texts: list[str] = []
    if request.knowledge_document_id is not None:
        document = db.get(KnowledgeDocument, request.knowledge_document_id)
        if document is None or document.user_id != user_id:
            raise HTTPException(status_code=404, detail="指定的知识库文档不存在")
        evidence_texts = knowledge_service.retrieve_from_document(
            document,
            query=f"{occupation_name}\n{request.job_description}".strip() or occupation_name,
            top_k=3,
        )

    task = InterviewTask(
        position=occupation_name,
        description=request.job_description.strip(),
        difficulty=request.difficulty,
        language=request.language,
        question_count=request.question_count,
        status="generating_questions",
        industry_id=request.industry_id,
        occupation_id=request.occupation_id,
        experience_level=request.experience_level,
        interview_type=request.interview_type,
        focus_areas=request.focus_areas,
        user_id=user_id,
    )
    db.add(task)
    db.commit()

    try:
        questions = question_generator.generate_question_set(
            client,
            industry_name=industry_name,
            occupation_name=occupation_name,
            occupation_profile=occupation_profile,
            experience_level=request.experience_level,
            interview_type=request.interview_type,
            focus_areas=request.focus_areas,
            difficulty=request.difficulty,
            language=request.language,
            question_count=request.question_count,
            job_description=request.job_description,
            evidence_texts=evidence_texts,
        )
    except ArkError as exc:
        task.status = "failed"
        task.error_message = f"题集生成失败：{exc}"
        db.commit()
        raise

    for index, item in enumerate(questions, start=1):
        db.add(
            InterviewQuestion(
                task_id=task.id,
                order_index=index,
                type="main",
                content=item.content,
                category=item.category,
                dimension=item.dimension,
                goal=item.goal,
                rubric=item.rubric,
                suggested_follow_up=item.follow_up,
            )
        )
    task.status = "ready"
    task.error_message = None
    db.commit()
    db.refresh(task)
    return task


def occupation_context_for_task(task: InterviewTask) -> str:
    """把任务上的目录上下文组装为文本，供评分等下游模块使用。"""
    if not task.industry_id:
        return task.position
    focus_areas = task.focus_areas or []
    try:
        industry_name = catalog_service.get_industry(task.industry_id)
        profile = catalog_service.get_occupation(task.occupation_id) if task.occupation_id else None
    except Exception:  # 目录加载异常不阻塞评分流程
        return task.position
    industry = industry_name["name"] if industry_name else ""
    if profile is None:
        return f"行业：{industry}；职业：{task.position}（自定义）"
    # occupation_context 已包含行业、职业、核心技能、能力维度与题目侧重
    return catalog_service.occupation_context(profile, task.position, focus_areas)


def _ordered_questions(task: InterviewTask) -> list[InterviewQuestion]:
    """主问题按 order_index 排列，追问紧跟其主问题之后。"""
    return sorted(
        task.questions,
        key=lambda q: (q.order_index, 0 if q.type == "main" else 1, q.id),
    )


def current_question(task: InterviewTask) -> InterviewQuestion | None:
    """纯查询：第一个未回答的问题（不调用 AI）。"""
    for question in _ordered_questions(task):
        if question.answer is None:
            return question
    return None


def _unresolved_answered_main(task: InterviewTask) -> InterviewQuestion | None:
    for question in _ordered_questions(task):
        if question.type == "main" and question.answer is not None \
                and not question.follow_up_resolved:
            return question
    return None


def resolve_next(db: Session, task: InterviewTask, client: ArkClient):
    """决定下一个要回答的问题；可能触发一次 AI 追问决策。幂等可重试。

    返回 (next_question | None, all_answered)。
    """
    # 先处理"已回答但追问决策未完成"的主问题（失败重试也会走到这里）
    pending_main = _unresolved_answered_main(task)
    if pending_main is not None:
        decision = follow_up_service.decide_follow_up(
            client,
            position=task.position,
            question=pending_main.content,
            answer=pending_main.answer.content,
            language=task.language,
        )
        if decision.need_follow_up and decision.follow_up:
            follow_up_question = InterviewQuestion(
                task_id=task.id,
                order_index=pending_main.order_index,
                type="follow_up",
                parent_question_id=pending_main.id,
                content=decision.follow_up,
            )
            db.add(follow_up_question)
        pending_main.follow_up_resolved = True
        db.commit()
        db.refresh(task)

    nxt = current_question(task)
    return nxt, nxt is None


def submit_answer(
    db: Session, task: InterviewTask, request: AnswerCreateRequest, client: ArkClient
):
    """保存回答并决定下一步。返回 (next_question | None, all_answered)。"""
    question = get_question(db, task, request.question_id)

    if task.status in ("generating_questions", "generating_report", "completed"):
        raise TaskFlowError(f"任务当前状态（{task.status}）不允许提交回答")
    if question.answer is not None:
        raise TaskFlowError("该问题已回答，请回答当前问题")

    db.add(InterviewAnswer(question_id=question.id, content=request.content.strip()))
    if task.status == "ready":
        task.status = "in_progress"
    task.error_message = None
    db.commit()
    db.refresh(task)

    return resolve_next(db, task, client)


def build_qa_pairs(task: InterviewTask) -> list[dict]:
    pair_by_main_id: dict[int, dict] = {}
    pairs: list[dict] = []
    for question in _ordered_questions(task):
        if question.type == "main":
            pair = {
                "question": question.content,
                "answer": question.answer.content if question.answer else "",
                "follow_up": None,
                "follow_up_answer": None,
            }
            pair_by_main_id[question.id] = pair
            pairs.append(pair)
        else:
            pair = pair_by_main_id.get(question.parent_question_id or -1)
            if pair is not None:
                pair["follow_up"] = question.content
                pair["follow_up_answer"] = (
                    question.answer.content if question.answer else ""
                )
    return pairs


def finish_task(db: Session, task: InterviewTask, client: ArkClient) -> InterviewReport:
    """全部回答完成后生成 T1 评分报告。"""
    if task.status == "completed" and task.report is not None:
        return task.report
    if task.status in ("generating_questions", "ready", "generating_report"):
        raise TaskFlowError("还有未完成的步骤，暂时无法生成报告")
    if current_question(task) is not None:
        raise TaskFlowError("仍有问题未回答，无法生成报告")

    task.status = "generating_report"
    db.commit()

    try:
        qa_pairs = build_qa_pairs(task)
        result = scoring.score_interview(
            client,
            position=task.position,
            difficulty=task.difficulty,
            language=task.language,
            qa_pairs=qa_pairs,
            occupation_context=occupation_context_for_task(task),
        )
    except ArkError as exc:
        task.status = "failed"
        task.error_message = f"报告生成失败：{exc}"
        db.commit()
        raise

    report = InterviewReport(
        task_id=task.id,
        overall_score=result.overall_score,
        summary=result.summary,
        dimensions=[d.model_dump() for d in result.dimensions],
        strengths=result.strengths,
        improvements=[i.model_dump() for i in result.improvements],
        model_name=client.model,
    )
    db.add(report)
    task.status = "completed"
    task.error_message = None
    db.commit()
    db.refresh(task)
    _sync_skill_graph(db, task, report)
    return report


def _sync_skill_graph(db, task: InterviewTask, report: InterviewReport) -> None:
    """完成真实面试后同步能力图谱（第十五阶段）。失败只记日志，不影响评分报告。"""
    try:
        from app.services import career_skill_graph

        career_skill_graph.update_after_interview(db, task.user_id, report)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("aurel.career").warning(
            "面试后能力图谱同步失败", exc_info=True
        )


def map_ark_error(exc: ArkError) -> HTTPException:
    if isinstance(exc, ArkNotConfiguredError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


def list_tasks(db: Session, limit: int = 50, *, user_id: int) -> list[InterviewTask]:
    statement = (
        select(InterviewTask)
        .where(InterviewTask.user_id == user_id)
        .order_by(InterviewTask.created_at.desc(), InterviewTask.id.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))
