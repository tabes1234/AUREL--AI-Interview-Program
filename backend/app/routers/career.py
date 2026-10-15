"""知途：AI 职业顾问「小鸥」的对话、长期档案与行动规划路由。

- 流式回复走统一服务层 ArkClient.chat_stream（SSE），前端绝不直连模型 API；
- 分层记忆由 career_memory 提供：当前会话近段 + 会话摘要 + 已确认档案 + 相关历史召回；
- 事实与推断严格分离：user_stated 自动确认，AI 归纳/推断必须用户确认后才进入长期上下文；
- 所有数据关联真实用户并在后端校验归属，删除的数据立即退出检索通道。
"""

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import (
    CareerConversation,
    CareerMessage,
    CareerPlan,
    CareerPlanAction,
    CareerPlanRevision,
    CareerProfile,
    CareerProfileFact,
    CareerWorkflowRun,
    utcnow,
)
from app.routers.interviews import get_ark_client
from app.schemas.career import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationUpdate,
    MessageCreate,
    MessageOut,
    MessagePairOut,
    PlanActionCreate,
    PlanActionOut,
    PlanActionUpdate,
    PlanGenerateRequest,
    PlanOut,
    PlanSummaryOut,
    PlanUpdate,
    ProfileFactCreate,
    ProfileFactOut,
    ProfileOrganizeRequest,
    ProfileOut,
    ProfileFactUpdate,
    WorkflowCreate,
    WorkflowOut,
)
from app.services import career_analyst, career_workflow
from app.services.ark_client import ArkClient, ArkError
from app.services import career_memory
from app.services.interview_service import map_ark_error
from app.services.usage_tracking import record_event

logger = logging.getLogger("aurel.career")

router = APIRouter(prefix="/api/v1/career-guide", tags=["career-guide"])

DEFAULT_TITLE = "新的旅程"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_owned_conversation(
    db: Session, conversation_id: int, user_id: int
) -> CareerConversation:
    conversation = db.get(CareerConversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conversation


def _get_owned_plan(db: Session, plan_id: int, user_id: int) -> CareerPlan:
    plan = db.get(CareerPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="计划不存在")
    return plan


def _get_owned_action(db: Session, plan: CareerPlan, action_id: int) -> CareerPlanAction:
    action = db.get(CareerPlanAction, action_id)
    if action is None or action.plan_id != plan.id or action.user_id != plan.user_id:
        raise HTTPException(status_code=404, detail="计划任务不存在")
    return action


def _snapshot_plan(db: Session, plan: CareerPlan, note: str) -> None:
    """任何计划变更都留版本快照（历史不可变）。"""
    plan.version_no = (plan.version_no or 1) + 1
    db.add(
        CareerPlanRevision(
            plan_id=plan.id,
            user_id=plan.user_id,
            version_no=plan.version_no,
            change_note=note[:200],
            snapshot=career_analyst.plan_snapshot(plan),
        )
    )


# ---------- 会话管理 ----------


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    search: str | None = Query(default=None, max_length=60),
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> list[ConversationOut]:
    """当前用户的对话列表（按最近更新排序；search 支持标题与消息内容检索）。"""
    statement = (
        select(CareerConversation, func.count(CareerMessage.id))
        .outerjoin(CareerMessage, CareerMessage.conversation_id == CareerConversation.id)
        .where(CareerConversation.user_id == user_id)
    )
    if search and search.strip():
        keyword = f"%{search.strip()}%"
        matched_ids = select(CareerMessage.conversation_id).where(
            CareerMessage.content.ilike(keyword)
        )
        statement = statement.where(
            or_(
                CareerConversation.title.ilike(keyword),
                CareerConversation.id.in_(matched_ids),
            )
        )
    rows = db.execute(
        statement.group_by(CareerConversation.id)
        .order_by(CareerConversation.updated_at.desc(), CareerConversation.id.desc())
        .limit(100)
    ).all()
    return [
        ConversationOut(
            id=conversation.id,
            title=conversation.title,
            message_count=count,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        for conversation, count in rows
    ]


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(
    payload: ConversationCreate | None = None,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ConversationOut:
    conversation = CareerConversation(
        user_id=user_id, title=(payload.title if payload and payload.title else DEFAULT_TITLE)
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        message_count=0,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ConversationDetail:
    conversation = _get_owned_conversation(db, conversation_id, user_id)
    messages = list(
        db.scalars(
            select(CareerMessage)
            .where(CareerMessage.conversation_id == conversation.id)
            .order_by(CareerMessage.id.asc())
        )
    )
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        message_count=len(messages),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[MessageOut.model_validate(message) for message in messages],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def rename_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ConversationOut:
    """编辑会话标题（自动生成的标题也允许用户改名）。"""
    conversation = _get_owned_conversation(db, conversation_id, user_id)
    conversation.title = payload.title
    conversation.updated_at = utcnow()
    db.commit()
    db.refresh(conversation)
    count = db.scalar(
        select(func.count(CareerMessage.id))
        .where(CareerMessage.conversation_id == conversation.id)
    )
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        message_count=int(count or 0),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    conversation = _get_owned_conversation(db, conversation_id, user_id)
    db.delete(conversation)
    db.commit()


# ---------- 对话（同步整段回复，供兼容与测试） ----------


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessagePairOut,
)
def send_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> MessagePairOut:
    """发送一条消息，小鸥结合分层记忆回复；AI 失败时不落任何消息。"""
    conversation = _get_owned_conversation(db, conversation_id, user_id)
    content = payload.content

    system, user_payload = career_memory.build_chat_context(db, user_id, conversation, content)
    try:
        reply = client.chat(
            system, user_payload, temperature=0.6, service="career_guide"
        ).strip()
    except ArkError as exc:
        raise map_ark_error(exc) from exc
    if not reply:
        raise HTTPException(status_code=502, detail="AI 模型返回了空内容")

    user_message = CareerMessage(conversation_id=conversation.id, role="user", content=content)
    assistant_message = CareerMessage(
        conversation_id=conversation.id, role="assistant", content=reply
    )
    db.add_all([user_message, assistant_message])
    # 首条消息自动把默认标题换成用户的真实问题（保留用户自拟标题）
    if conversation.title == DEFAULT_TITLE:
        conversation.title = content[:16]
    conversation.updated_at = utcnow()
    record_event(db, user_id=user_id, module="zhitu", name="message_send")
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    # 记忆整理尽力而为：失败不阻塞对话，也不冒充成功
    try:
        career_memory.maybe_summarize(db, client, conversation)
        career_memory.extract_facts_from_exchange(db, client, user_id, user_message, reply)
    except ArkError as exc:
        logger.info("career memory housekeeping skipped: %s", exc)
    except Exception:  # noqa: BLE001
        logger.warning("career memory housekeeping failed", exc_info=True)

    return MessagePairOut(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
        model_name=getattr(client, "model", None),
    )


# ---------- 对话（SSE 流式回复） ----------


def _stream_reply(
    db: Session,
    client: ArkClient,
    user_id: int,
    conversation: CareerConversation,
    content: str | None,
    *,
    regenerate: bool,
) -> Iterator[str]:
    """SSE 生成器：meta → delta* → done → end；失败发 error 事件，绝不伪造输出。

    - 新消息：content 落库后流式生成；
    - 重试：若最后一条是同内容的用户消息（上次生成失败），复用它不重复入库；
    - 重新生成：移除最后一条 AI 回复后基于最后一条用户消息重新生成；
    - 客户端中途停止：已生成的部分内容落库保留。
    """
    user_message: CareerMessage | None = None
    removed_any = False

    last = db.scalar(
        select(CareerMessage)
        .where(CareerMessage.conversation_id == conversation.id)
        .order_by(CareerMessage.id.desc())
    )
    if regenerate:
        if last is not None and last.role == "assistant":
            db.delete(last)
            db.commit()
            removed_any = True
            last = db.scalar(
                select(CareerMessage)
                .where(CareerMessage.conversation_id == conversation.id)
                .order_by(CareerMessage.id.desc())
            )
        if last is None or last.role != "user":
            yield _sse("error", {"message": "没有可以重新生成回复的用户消息", "status": 400})
            return
        user_message = last
    else:
        if last is not None and last.role == "user" and content is not None and last.content == content:
            user_message = last  # 失败重试：复用原消息，不重复入库
        else:
            user_message = CareerMessage(
                conversation_id=conversation.id, role="user", content=content or ""
            )
            db.add(user_message)
            db.commit()
            db.refresh(user_message)
            if conversation.title == DEFAULT_TITLE:
                conversation.title = (content or "")[:16]
                db.commit()

    yield _sse(
        "meta",
        {
            "user_message": json.loads(MessageOut.model_validate(user_message).model_dump_json()),
            "regenerated": regenerate,
            "removed_previous": removed_any,
        },
    )

    accumulated: list[str] = []
    stream_error: str | None = None
    error_status = 502
    try:
        system, user_payload = career_memory.build_chat_context(
            db, user_id, conversation, user_message.content
        )
        for delta in client.chat_stream(
            system, user_payload, temperature=0.6, service="career_guide"
        ):
            accumulated.append(delta)
            yield _sse("delta", {"text": delta})
    except ArkError as exc:
        stream_error = str(exc)
        error_status = 503 if "尚未配置" in stream_error else 502
    except GeneratorExit:
        # 用户停止生成：已生成的部分保留为 AI 回复（如实截断），然后收束流
        partial = "".join(accumulated).strip()
        if partial:
            assistant = CareerMessage(
                conversation_id=conversation.id, role="assistant", content=partial
            )
            conversation.updated_at = utcnow()
            db.add(assistant)
            db.commit()
        raise
    except Exception:  # noqa: BLE001 — 流式管道意外中断，如实报错
        logger.warning("career stream unexpected error", exc_info=True)
        stream_error = "流式响应出现意外中断，请重试"

    partial = "".join(accumulated).strip()
    if stream_error is not None:
        # 已生成的部分内容保留；未生成任何内容时用户消息保留（可重试）
        if partial:
            assistant = CareerMessage(
                conversation_id=conversation.id, role="assistant", content=partial
            )
            conversation.updated_at = utcnow()
            db.add(assistant)
            db.commit()
            db.refresh(assistant)
        yield _sse(
            "error",
            {
                "message": stream_error,
                "status": error_status,
                "partial_saved": bool(partial),
            },
        )
        return
    if not partial:
        yield _sse("error", {"message": "AI 模型返回了空内容", "status": 502, "partial_saved": False})
        return

    assistant_message = CareerMessage(
        conversation_id=conversation.id, role="assistant", content=partial
    )
    conversation.updated_at = utcnow()
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    yield _sse(
        "done",
        {
            "assistant_message": json.loads(
                MessageOut.model_validate(assistant_message).model_dump_json()
            ),
            "title": conversation.title,
            "model_name": getattr(client, "model", None),
        },
    )

    # 回复完成后整理记忆（摘要 + 事实抽取），尽力而为
    facts_added = 0
    summary_updated = False
    try:
        summary_updated = career_memory.maybe_summarize(db, client, conversation)
        facts = career_memory.extract_facts_from_exchange(
            db, client, user_id, user_message, partial
        )
        facts_added = len(facts)
    except ArkError as exc:
        logger.info("career memory housekeeping skipped: %s", exc)
    except Exception:  # noqa: BLE001
        logger.warning("career memory housekeeping failed", exc_info=True)

    yield _sse("end", {"facts_added": facts_added, "summary_updated": summary_updated})


@router.post("/conversations/{conversation_id}/stream")
def stream_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> StreamingResponse:
    """发送消息并流式接收小鸥回复（SSE）。"""
    conversation = _get_owned_conversation(db, conversation_id, user_id)
    record_event(db, user_id=user_id, module="zhitu", name="message_send")
    return StreamingResponse(
        _stream_reply(db, client, user_id, conversation, payload.content, regenerate=False),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/conversations/{conversation_id}/regenerate")
def regenerate_message(
    conversation_id: int,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> StreamingResponse:
    """重新生成最后一条 AI 回复（替换旧回复，真实再次调用模型）。"""
    conversation = _get_owned_conversation(db, conversation_id, user_id)
    record_event(db, user_id=user_id, module="zhitu", name="message_send")
    return StreamingResponse(
        _stream_reply(db, client, user_id, conversation, None, regenerate=True),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- 结构化分析引擎 ----------


@router.post("/analysis/situation")
def analyze_situation_endpoint(
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> dict:
    """当前情况总结：背景、已有证据与不确定点（不武断下结论）。"""
    try:
        return career_analyst.analyze_situation(db, client, user_id)
    except ArkError as exc:
        raise map_ark_error(exc) from exc


@router.post("/analysis/directions")
def explore_directions_endpoint(
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> dict:
    """职业方向探索：多个可能方向 + 证据 + 不确定性，不预测成功概率。"""
    try:
        return career_analyst.explore_directions(db, client, user_id)
    except ArkError as exc:
        raise map_ark_error(exc) from exc


# ---------- 长期职业档案 ----------


@router.get("/profile", response_model=ProfileOut)
def get_profile(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> ProfileOut:
    profile = career_memory.get_or_create_profile(db, user_id)
    facts = list(
        db.scalars(
            select(CareerProfileFact)
            .where(CareerProfileFact.user_id == user_id)
            .order_by(CareerProfileFact.updated_at.desc(), CareerProfileFact.id.desc())
        )
    )
    counts = career_memory.profile_counts(db, user_id)
    return ProfileOut(
        summary=profile.summary,
        facts=[ProfileFactOut.model_validate(fact) for fact in facts],
        **counts,
    )


@router.post("/profile/facts", response_model=ProfileFactOut, status_code=201)
def add_fact(
    payload: ProfileFactCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ProfileFactOut:
    """用户主动补充档案事实：来源为本人，视为已确认。"""
    profile = career_memory.get_or_create_profile(db, user_id)
    fact = CareerProfileFact(
        user_id=user_id,
        profile_id=profile.id,
        category=payload.category,
        content=payload.content,
        source_type="user_stated",
        confirmed=True,
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return ProfileFactOut.model_validate(fact)


@router.patch("/profile/facts/{fact_id}", response_model=ProfileFactOut)
def update_fact(
    fact_id: int,
    payload: ProfileFactUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ProfileFactOut:
    """编辑/确认某条记忆。确认后 AI 归纳才算用户认可的信息。"""
    fact = db.get(CareerProfileFact, fact_id)
    if fact is None or fact.user_id != user_id:
        raise HTTPException(status_code=404, detail="档案条目不存在")
    if payload.content is not None:
        fact.content = payload.content
    if payload.category is not None:
        fact.category = payload.category
    if payload.confirmed is not None:
        fact.confirmed = payload.confirmed
    if payload.content is not None and not fact.confirmed and payload.confirmed is None:
        # 用户亲手改写的内容视为本人认可
        fact.confirmed = True
    fact.updated_at = utcnow()
    db.commit()
    db.refresh(fact)
    return ProfileFactOut.model_validate(fact)


@router.delete("/profile/facts/{fact_id}", status_code=204)
def delete_fact(
    fact_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    """删除单条记忆：删除后立即退出上下文与召回。"""
    fact = db.get(CareerProfileFact, fact_id)
    if fact is None or fact.user_id != user_id:
        raise HTTPException(status_code=404, detail="档案条目不存在")
    db.delete(fact)
    db.commit()


@router.delete("/profile/facts", status_code=204)
def clear_facts(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> None:
    """清空长期记忆：删除全部档案事实与 AI 总结。"""
    profile = career_memory.get_or_create_profile(db, user_id)
    for fact in db.scalars(
        select(CareerProfileFact).where(CareerProfileFact.user_id == user_id)
    ):
        db.delete(fact)
    profile.summary = None
    db.commit()


@router.post("/profile/organize", response_model=ProfileOut)
def organize_profile(
    payload: ProfileOrganizeRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> ProfileOut:
    """让小鸥整理历史对话，产出待确认的档案候选（全部不自动确认）。"""
    conversation = None
    if payload.conversation_id is not None:
        conversation = _get_owned_conversation(db, payload.conversation_id, user_id)
    try:
        career_memory.organize_profile_from_history(
            db, client, user_id, conversation=conversation
        )
    except ArkError as exc:
        raise map_ark_error(exc) from exc
    return get_profile(db=db, user_id=user_id)


# ---------- 行动规划 ----------


@router.get("/plans", response_model=list[PlanSummaryOut])
def list_plans(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> list[PlanSummaryOut]:
    plans = list(
        db.scalars(
            select(CareerPlan)
            .where(CareerPlan.user_id == user_id)
            .order_by(CareerPlan.updated_at.desc(), CareerPlan.id.desc())
            .limit(50)
        )
    )
    summaries = []
    for plan in plans:
        actions = list(plan.actions)
        summaries.append(
            PlanSummaryOut(
                id=plan.id,
                title=plan.title,
                focus_role=plan.focus_role,
                status=plan.status,
                version_no=plan.version_no,
                created_at=plan.created_at,
                updated_at=plan.updated_at,
                pending_count=sum(1 for item in actions if item.status == "pending"),
                done_count=sum(1 for item in actions if item.status == "done"),
                skipped_count=sum(1 for item in actions if item.status == "skipped"),
            )
        )
    return summaries


@router.post("/plans/generate", response_model=PlanOut, status_code=201)
def generate_plan(
    payload: PlanGenerateRequest | None = None,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> PlanOut:
    """生成 7/30/90 天行动计划（真实调用规划模型；信息不足在 situation 中说明）。"""
    request = payload or PlanGenerateRequest()
    try:
        plan = career_analyst.generate_plan(
            db,
            client,
            user_id,
            conversation_id=request.conversation_id,
            job_analysis_id=request.job_analysis_id,
            goal=request.goal,
        )
    except ArkError as exc:
        raise map_ark_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.refresh(plan)
    return PlanOut.model_validate(plan)


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> PlanOut:
    plan = _get_owned_plan(db, plan_id, user_id)
    return PlanOut.model_validate(plan)


@router.patch("/plans/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: int,
    payload: PlanUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> PlanOut:
    plan = _get_owned_plan(db, plan_id, user_id)
    notes = []
    if payload.title is not None:
        plan.title = payload.title
        notes.append("更新标题")
    if payload.status is not None:
        plan.status = payload.status
        notes.append("归档" if payload.status == "archived" else "恢复")
    if notes:
        _snapshot_plan(db, plan, "、".join(notes))
    db.commit()
    db.refresh(plan)
    return PlanOut.model_validate(plan)


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    plan = _get_owned_plan(db, plan_id, user_id)
    db.delete(plan)
    db.commit()


@router.post("/plans/{plan_id}/actions", response_model=PlanOut)
def add_plan_action(
    plan_id: int,
    payload: PlanActionCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> PlanOut:
    plan = _get_owned_plan(db, plan_id, user_id)
    position = max((item.position for item in plan.actions), default=-1) + 1
    from datetime import timedelta

    days = {"7d": 7, "30d": 30, "90d": 90}[payload.phase]
    plan.actions.append(
        CareerPlanAction(
            plan_id=plan.id,
            user_id=user_id,
            phase=payload.phase,
            goal=payload.goal,
            steps=payload.steps or "",
            related_goal=payload.related_goal,
            position=position,
            due_at=utcnow() + timedelta(days=days),
        )
    )
    _snapshot_plan(db, plan, "手动添加任务")
    db.commit()
    db.refresh(plan)
    return PlanOut.model_validate(plan)


@router.patch("/plans/{plan_id}/actions/{action_id}", response_model=PlanOut)
def update_plan_action(
    plan_id: int,
    action_id: int,
    payload: PlanActionUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> PlanOut:
    plan = _get_owned_plan(db, plan_id, user_id)
    action = _get_owned_action(db, plan, action_id)
    notes = []
    if payload.status is not None and payload.status != action.status:
        action.status = payload.status
        if payload.status == "done":
            action.completed_at = utcnow()
            notes.append(f"完成任务「{action.goal[:20]}」")
        elif payload.status == "skipped":
            action.completed_at = None
            notes.append(f"跳过任务「{action.goal[:20]}」")
        else:
            action.completed_at = None
            notes.append("任务恢复待办")
    if payload.review is not None:
        action.review = payload.review or None
        notes.append("更新复盘")
    if payload.goal is not None:
        action.goal = payload.goal
        notes.append("调整目标")
    if payload.steps is not None:
        action.steps = payload.steps
    if payload.related_goal is not None:
        action.related_goal = payload.related_goal or None
    if payload.due_at is not None:
        action.due_at = payload.due_at
        notes.append("调整期限")
    action.updated_at = utcnow()
    if notes:
        _snapshot_plan(db, plan, "、".join(notes))
    db.commit()
    db.refresh(plan)
    return PlanOut.model_validate(plan)


@router.delete("/plans/{plan_id}/actions/{action_id}", response_model=PlanOut)
def delete_plan_action(
    plan_id: int,
    action_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> PlanOut:
    plan = _get_owned_plan(db, plan_id, user_id)
    action = _get_owned_action(db, plan, action_id)
    db.delete(action)
    _snapshot_plan(db, plan, "删除任务")
    db.commit()
    db.refresh(plan)
    return PlanOut.model_validate(plan)


# ---------- 联动工作流 ----------


@router.post("/workflows", response_model=WorkflowOut, status_code=201)
def create_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> WorkflowOut:
    """执行多步骤联动工作流（逐步真实调用各模块服务，失败如实记录）。"""
    try:
        run = career_workflow.run_workflow(db, client, user_id, payload.kind, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return WorkflowOut.model_validate(run)


@router.get("/workflows/{run_id}", response_model=WorkflowOut)
def get_workflow(
    run_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> WorkflowOut:
    run = db.get(CareerWorkflowRun, run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="工作流记录不存在")
    return WorkflowOut.model_validate(run)


@router.get("/workflows", response_model=list[WorkflowOut])
def list_workflows(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> list[WorkflowOut]:
    runs = list(
        db.scalars(
            select(CareerWorkflowRun)
            .where(CareerWorkflowRun.user_id == user_id)
            .order_by(CareerWorkflowRun.id.desc())
            .limit(20)
        )
    )
    return [WorkflowOut.model_validate(run) for run in runs]


# ---------- 个人数据导出 ----------


@router.get("/export")
def export_career_data(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> JSONResponse:
    """导出本人全部知途数据（会话、档案、规划、工作流），JSON 下载。"""
    conversations = list(
        db.scalars(
            select(CareerConversation)
            .where(CareerConversation.user_id == user_id)
            .order_by(CareerConversation.id.asc())
        )
    )
    conversation_payload = []
    for conversation in conversations:
        messages = list(
            db.scalars(
                select(CareerMessage)
                .where(CareerMessage.conversation_id == conversation.id)
                .order_by(CareerMessage.id.asc())
            )
        )
        conversation_payload.append(
            {
                "id": conversation.id,
                "title": conversation.title,
                "summary": conversation.summary,
                "created_at": conversation.created_at.isoformat(),
                "messages": [
                    {
                        "id": message.id,
                        "role": message.role,
                        "content": message.content,
                        "created_at": message.created_at.isoformat(),
                    }
                    for message in messages
                ],
            }
        )

    profile_row = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user_id))
    facts = list(
        db.scalars(
            select(CareerProfileFact)
            .where(CareerProfileFact.user_id == user_id)
            .order_by(CareerProfileFact.id.asc())
        )
    )

    plans = list(
        db.scalars(
            select(CareerPlan)
            .where(CareerPlan.user_id == user_id)
            .order_by(CareerPlan.id.asc())
        )
    )
    plan_payload = []
    for plan in plans:
        revisions = list(
            db.scalars(
                select(CareerPlanRevision)
                .where(CareerPlanRevision.plan_id == plan.id)
                .order_by(CareerPlanRevision.version_no.asc())
            )
        )
        plan_payload.append(
            {
                "id": plan.id,
                "title": plan.title,
                "situation": plan.situation,
                "focus_role": plan.focus_role,
                "status": plan.status,
                "version_no": plan.version_no,
                "created_at": plan.created_at.isoformat(),
                "actions": [
                    {
                        "id": action.id,
                        "phase": action.phase,
                        "goal": action.goal,
                        "steps": action.steps,
                        "status": action.status,
                        "review": action.review,
                        "due_at": action.due_at.isoformat() if action.due_at else None,
                    }
                    for action in sorted(plan.actions, key=lambda item: item.position)
                ],
                "revisions": [
                    {
                        "version_no": revision.version_no,
                        "change_note": revision.change_note,
                        "snapshot": revision.snapshot,
                        "created_at": revision.created_at.isoformat(),
                    }
                    for revision in revisions
                ],
            }
        )

    runs = list(
        db.scalars(
            select(CareerWorkflowRun)
            .where(CareerWorkflowRun.user_id == user_id)
            .order_by(CareerWorkflowRun.id.asc())
        )
    )

    body = {
        "exported_at": utcnow().isoformat(),
        "conversations": conversation_payload,
        "profile": {
            "summary": profile_row.summary if profile_row else None,
            "facts": [
                {
                    "id": fact.id,
                    "category": fact.category,
                    "content": fact.content,
                    "source_type": fact.source_type,
                    "confirmed": fact.confirmed,
                    "confidence": fact.confidence,
                    "quote": fact.quote,
                    "created_at": fact.created_at.isoformat(),
                }
                for fact in facts
            ],
        },
        "plans": plan_payload,
        "workflow_runs": [
            {
                "id": run.id,
                "kind": run.kind,
                "status": run.status,
                "steps": run.steps,
                "error_message": run.error_message,
                "created_at": run.created_at.isoformat(),
            }
            for run in runs
        ],
    }
    return JSONResponse(
        content=body,
        headers={
            "Content-Disposition": "attachment; filename=aurel-career-export.json"
        },
    )
