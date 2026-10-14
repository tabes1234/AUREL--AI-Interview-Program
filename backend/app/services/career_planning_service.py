"""知途规划协调服务（第十五阶段）：规划复盘、成长反馈、记忆使用透明化。

职责边界（不塞大文件）：
- 复盘（review_plan）：真实读取计划完成状态、问澜/度衡/成长轨迹记录与知识检索证据，
  调用模型产出复盘与更新建议，落为「新的规划版本」——历史版本一律不覆盖；
- 成长趋势（growth_feedback）：只聚合真实记录（问澜报告分数序列、行动完成时间线、
  度衡挑战、活跃打卡），没有记录时返回空状态，绝不生成假曲线；
- 记忆透明化（memory_usage）：展示一次回答实际会用到的档案事实、召回与摘要；
- 清除记忆（clear_memory）：删除本人全部会话与档案事实，删除的数据立即退出所有
  检索与上下文通道。
"""

import json
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChallengeRun,
    CareerConversation,
    CareerMessage,
    CareerPlan,
    CareerPlanAction,
    CareerPlanRevision,
    CareerProfileFact,
    InterviewReport,
    InterviewTask,
    utcnow,
)
from app.services.ark_client import ArkError
from app.services import career_analyst, career_memory, career_retrieval, career_skill_graph

logger = logging.getLogger("aurel.career")

REVIEW_SYSTEM = """你是职业规划复盘师「小鸥」的复盘内核。对用户当前行动计划做真实复盘。
只输出 JSON：{"review_summary": "复盘总结（3-5 句，引用真实完成情况）",
"achievements": ["已完成/有进展的事项及证据"],
"blocked": ["受阻或逾期事项及原因（材料中没有原因时如实说未知）"],
"adjustments": [{"phase": "7d|30d|90d", "goal": "调整后的目标", "steps": "执行步骤", "due_in_days": 7, "reason": "调整理由"}],
"next_focus": ["下一阶段建议聚焦的方向"]}
规则：
- 只依据提供的真实记录复盘，绝不虚构完成情况或成长数据；
- adjustments 只针对当前计划明显需要调整的任务，最多 4 条；没有需要调整的返回空数组；
- 绝不承诺求职成功、录用概率或薪资结果。"""


def collect_data_basis(db: Session, user_id: int) -> dict:
    """规划所依据的数据版本：真实数据源清单 + 采集时间。"""
    from app.models import JobAnalysis, Resume

    facts = career_memory.confirmed_facts(db, user_id)
    latest_report_id = db.scalar(
        select(InterviewReport.id)
        .join(InterviewTask, InterviewReport.task_id == InterviewTask.id)
        .where(InterviewTask.user_id == user_id)
        .order_by(InterviewReport.id.desc())
        .limit(1)
    )
    job_analysis_count = len(
        list(db.scalars(select(JobAnalysis.id).where(JobAnalysis.user_id == user_id).limit(50)))
    )
    resume_count = len(
        list(db.scalars(select(Resume.id).where(Resume.user_id == user_id).limit(50)))
    )
    return {
        "collected_at": utcnow().isoformat(),
        "confirmed_facts": len(facts),
        "latest_interview_report_id": latest_report_id,
        "job_analysis_count": job_analysis_count,
        "resume_count": resume_count,
    }


def review_plan(db: Session, client, user_id: int, plan_id: int) -> dict:
    """复盘计划：不覆盖历史，产出新的版本快照 + 复盘记录。失败如实抛出。"""
    plan = db.get(CareerPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise LookupError("计划不存在")

    actions = list(plan.actions)
    done = [item for item in actions if item.status == "done"]
    skipped = [item for item in actions if item.status == "skipped"]
    pending = [item for item in actions if item.status == "pending"]
    now = utcnow()
    overdue = [
        item for item in pending if item.due_at is not None and item.due_at < now
    ]

    # 真实证据：问澜近期表现 + 知识检索证据 + 图谱已证实技能
    skill_profile = career_analyst._skill_profile_block(db, user_id)
    retrieval_block, retrieval_sources = career_retrieval.evidence_block(
        db, user_id, plan.focus_role or plan.title, top_k=3
    )
    graph = career_skill_graph.get_graph(db, user_id)
    verified_skills = [
        node["name"] for node in graph["nodes"] if node["status"] == "verified"
    ][:10]

    plan_block = "\n".join(
        f"- [{item.phase}] {item.goal}｜状态 {item.status}｜"
        f"期限 {item.due_at.date().isoformat() if item.due_at else '未设置'}"
        + (f"｜复盘备注 {item.review[:80]}" if item.review else "")
        for item in sorted(actions, key=lambda item: item.position)
    )
    user_payload = "\n\n".join(
        block
        for block in (
            f"【计划《{plan.title}》】目标职业：{plan.focus_role or '未明确'}\n任务清单：\n{plan_block}",
            f"【完成情况】完成 {len(done)}、跳过 {len(skipped)}、待办 {len(pending)}、逾期 {len(overdue)}",
            skill_profile,
            f"【图谱中已证实的技能】{'、'.join(verified_skills) if verified_skills else '暂无已证实技能'}",
            retrieval_block,
        )
        if block
    )
    data = client.chat_json(REVIEW_SYSTEM, user_payload, temperature=0.3, service="career_review")

    adjustments = []
    for item in data.get("adjustments", [])[:4] if isinstance(data.get("adjustments"), list) else []:
        if not isinstance(item, dict):
            continue
        goal = str(item.get("goal") or "").strip()
        if not goal:
            continue
        phase = str(item.get("phase") or "30d").strip()
        if phase not in {"7d", "30d", "90d"}:
            phase = "30d"
        adjustments.append(
            {
                "phase": phase,
                "goal": goal[:200],
                "steps": str(item.get("steps") or "").strip()[:1000],
                "due_in_days": min(max(int(item.get("due_in_days") or 30), 1), 90),
                "reason": str(item.get("reason") or "").strip()[:300],
            }
        )

    review = {
        "review_summary": str(data.get("review_summary") or "").strip()[:1000],
        "achievements": career_analyst._string_list(data.get("achievements"), 6),
        "blocked": career_analyst._string_list(data.get("blocked"), 6),
        "adjustments": adjustments,
        "next_focus": career_analyst._string_list(data.get("next_focus"), 5),
        "reviewed_at": now.isoformat(),
        "real_stats": {
            "done": len(done),
            "skipped": len(skipped),
            "pending": len(pending),
            "overdue": len(overdue),
        },
        "retrieval_sources": retrieval_sources,
    }

    # 版本留痕：历史不可变；复盘本身也生成新版本（即使没有调整，也记录复盘时点状态）
    plan.version_no = (plan.version_no or 1) + 1
    plan.data_basis = collect_data_basis(db, user_id)
    db.add(
        CareerPlanRevision(
            plan_id=plan.id,
            user_id=user_id,
            version_no=plan.version_no,
            change_note=f"复盘：完成 {len(done)}/待办 {len(pending)}/逾期 {len(overdue)}",
            snapshot={
                **career_analyst.plan_snapshot(plan),
                "review": review,
                "data_basis": plan.data_basis,
            },
        )
    )
    db.commit()
    db.refresh(plan)
    return {"plan": plan, "review": review}


def apply_review_adjustments(db: Session, user_id: int, plan_id: int, adjustments: list[dict]) -> CareerPlan:
    """用户确认后，把复盘建议落为新任务（追加），并生成新版本。"""
    plan = db.get(CareerPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise LookupError("计划不存在")
    from datetime import timedelta

    position = max((item.position for item in plan.actions), default=-1) + 1
    added = 0
    for item in adjustments[:4]:
        goal = str(item.get("goal") or "").strip()
        if not goal:
            continue
        phase = item.get("phase") if item.get("phase") in {"7d", "30d", "90d"} else "30d"
        plan.actions.append(
            CareerPlanAction(
                plan_id=plan.id,
                user_id=user_id,
                phase=phase,
                goal=goal[:200],
                steps=str(item.get("steps") or "")[:1000],
                related_goal=(item.get("reason") or "")[:200] or None,
                position=position,
                due_at=utcnow() + timedelta(days={"7d": 7, "30d": 30, "90d": 90}[phase]),
            )
        )
        position += 1
        added += 1
    if added:
        plan.version_no = (plan.version_no or 1) + 1
        db.add(
            CareerPlanRevision(
                plan_id=plan.id,
                user_id=user_id,
                version_no=plan.version_no,
                change_note=f"采纳复盘建议，新增 {added} 项任务",
                snapshot=career_analyst.plan_snapshot(plan),
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def growth_feedback(db: Session, user_id: int) -> dict:
    """成长反馈：只来自真实记录；没有记录的维度返回空状态，不造曲线。"""
    reports = list(
        db.execute(
            select(InterviewReport, InterviewTask)
            .join(InterviewTask, InterviewReport.task_id == InterviewTask.id)
            .where(InterviewTask.user_id == user_id)
            .order_by(InterviewReport.created_at.asc(), InterviewReport.id.asc())
            .limit(100)
        ).all()
    )
    score_series = [
        {
            "date": report.created_at.date().isoformat(),
            "position": task.position,
            "score": report.overall_score,
        }
        for report, task in reports
    ]
    challenge_count = len(
        list(db.scalars(select(ChallengeRun.id).where(ChallengeRun.user_id == user_id).limit(100)))
    )

    actions = list(
        db.scalars(
            select(CareerPlanAction)
            .where(CareerPlanAction.user_id == user_id, CareerPlanAction.status == "done")
            .order_by(CareerPlanAction.completed_at.asc())
            .limit(200)
        )
    )
    action_series = [
        {
            "date": action.completed_at.date().isoformat() if action.completed_at else None,
            "goal": action.goal[:80],
        }
        for action in actions
        if action.completed_at is not None
    ]

    from app.services.growth_stats import growth_heatmap

    heatmap = growth_heatmap(db, user_id, date.today().year)

    has_any = bool(score_series or challenge_count or action_series)
    return {
        "available": has_any,
        "message": None if has_any else "暂无真实练习与行动记录；完成问澜面试、度衡挑战或计划任务后，这里才会出现真实的成长趋势",
        "interview_scores": score_series,
        "challenge_count": challenge_count,
        "completed_actions": action_series,
        "heatmap": {
            "total_active_days": heatmap.get("total_active_days"),
            "current_streak": heatmap.get("current_streak"),
        },
        "disclaimer": "成长趋势仅基于平台内的真实练习与行动记录，不代表任何就业结果。",
    }


def memory_usage(db: Session, user_id: int, conversation_id: int | None, preview_query: str | None) -> dict:
    """记忆透明化：展示一次回答会用到的上下文分层（不真实调用模型）。"""
    if conversation_id is not None:
        conversation = db.get(CareerConversation, conversation_id)
        if conversation is None or conversation.user_id != user_id:
            raise LookupError("对话不存在")
    else:
        conversation = db.scalar(
            select(CareerConversation)
            .where(CareerConversation.user_id == user_id)
            .order_by(CareerConversation.updated_at.desc(), CareerConversation.id.desc())
        )
        if conversation is None:
            conversation = CareerConversation(user_id=user_id, title="记忆预览")
            db.add(conversation)
            db.flush()

    query = (preview_query or "").strip()[:300] or "职业发展方向"
    _, context = career_memory.build_chat_context(db, user_id, conversation, query)
    recalls = career_memory.recall_related_history(db, user_id, query, conversation.id)
    facts = career_memory.confirmed_facts(db, user_id)
    return {
        "conversation_id": conversation.id,
        "layers": {
            "confirmed_facts": [
                {"id": fact.id, "category": fact.category, "content": fact.content[:120]}
                for fact in facts[:20]
            ],
            "related_history": [
                {
                    "conversation_title": item["conversation_title"],
                    "content": item["content"][:120],
                    "score": item["score"],
                }
                for item in recalls
            ],
            "session_summary": conversation.summary,
            "recent_window": career_memory.RECENT_MESSAGE_WINDOW,
        },
        "assembled_context_preview": context[:2000],
        "note": "以上为下一次回答将使用的记忆分层预览；未确认的 AI 归纳/推断不会进入模型上下文。",
    }


def clear_memory(db: Session, user_id: int) -> dict:
    """清除记忆并重新开始：删除本人全部知途会话与档案事实。
    删除的数据立即退出召回、摘要与上下文组装（查询按 user_id 即时过滤）。"""
    conversations = list(
        db.scalars(select(CareerConversation).where(CareerConversation.user_id == user_id))
    )
    message_count = 0
    for conversation in conversations:
        messages = list(
            db.scalars(
                select(CareerMessage).where(CareerMessage.conversation_id == conversation.id)
            )
        )
        message_count += len(messages)
        for message in messages:
            db.delete(message)
        db.delete(conversation)
    facts = list(
        db.scalars(select(CareerProfileFact).where(CareerProfileFact.user_id == user_id))
    )
    for fact in facts:
        db.delete(fact)
    db.commit()
    return {
        "deleted_conversations": len(conversations),
        "deleted_messages": message_count,
        "deleted_facts": len(facts),
        "note": "记忆已清除；已删除的数据不再参与任何后续上下文与召回。",
    }


def serialize_data_basis(data_basis: dict | None) -> str:
    return json.dumps(data_basis or {}, ensure_ascii=False)


def rebuild_derived_indexes(db: Session, user_id: int) -> dict:
    """重建本人可检索索引 + 同步档案/解析到图谱（供联动按钮调用）。"""
    user_index = career_retrieval.sync_user_index(db, user_id)
    graph_from_profile = career_skill_graph.sync_profile_skill_facts(db, user_id)
    analyses = list(
        db.scalars(select(_job_analysis_model()).where(_job_analysis_model().user_id == user_id))
    )
    graph_from_jobs = 0
    for analysis in analyses:
        graph_from_jobs += career_skill_graph.update_after_job_analysis(db, user_id, analysis)[
            "created_nodes"
        ]
    return {
        "knowledge_chunks_added": user_index["added"],
        "graph_nodes_added": graph_from_profile["created_nodes"] + graph_from_jobs,
    }


def _job_analysis_model():
    from app.models import JobAnalysis

    return JobAnalysis


def ark_error_note(exc: ArkError) -> str:
    return f"模型调用失败：{exc}"
