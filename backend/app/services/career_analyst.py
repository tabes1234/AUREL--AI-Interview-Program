"""知途分析引擎：情况总结、职业方向探索、能力差距与 7/30/90 天行动计划。

所有结论只基于真实数据（档案、会话摘要、知岗解析、简历、观己评分、
成长轨迹、度衡挑战）；信息不足时如实说明，绝不武断下结论，
绝不承诺求职成功、录用概率或薪资结果。
"""

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChallengeRun, CareerConversation, JobAnalysis, Resume, utcnow
from app.models import (
    CareerPlan,
    CareerPlanAction,
    CareerPlanRevision,
)
from app.services.ark_client import ArkClient
from app.services.career_memory import FACT_CATEGORIES, confirmed_facts, get_or_create_profile
from app.services.growth_stats import growth_heatmap
from app.services.skill_service import build_skill_profile

logger = logging.getLogger("aurel.career")

ANALYST_SYSTEM = """你是职业分析师「小鸥」的分析内核。基于提供的真实材料做结构化分析。
只输出 JSON。规则：
- 只依据材料下结论；材料中没有的信息标记为不确定，绝不编造用户的经历或能力；
- 用户未提及的能力既不当作具备、也不当作缺失，只能放入「待确认」；
- 不给录用承诺，不预测录取概率或薪资数字；
- 每个判断尽量引用材料中的依据片段。"""

PLANNER_SYSTEM = """你是职业规划师「小鸥」的规划内核。基于已知信息制定未来 7 天、30 天、90 天的阶段性成长计划。
只输出 JSON：{"title": "计划标题", "focus_role": "目标职业或 null", "situation": "背景与不确定点（2-4 句）", "actions": [{"phase": "7d", "goal": "具体目标", "steps": "执行步骤（用分号分隔，2-4 步）", "due_in_days": 3, "related_goal": "对应技能或职业目标，可为空"}]}
规则：
- 7d 安排 2-3 条、30d 安排 3-5 条、90d 安排 3-5 条，actions 总数不超过 12；
- 任务必须具体、可执行、可在期限内完成；优先基于用户已有的证据与目标安排；
- 材料不足的信息在 situation 中如实说明，不编造用户背景；
- 绝不承诺求职成功、录用概率或薪资结果；due_in_days 为距今天数（1-90）。"""

VALID_PHASES = {"7d", "30d", "90d"}
PHASE_LABELS = {"7d": "未来 7 天", "30d": "未来 30 天", "90d": "未来 90 天"}


def _profile_block(db: Session, user_id: int) -> str:
    facts = confirmed_facts(db, user_id)
    if not facts:
        return "（档案为空：用户尚未确认任何长期事实）"
    lines = [
        f"- [{FACT_CATEGORIES.get(fact.category, '其他')}] {fact.content}" for fact in facts
    ]
    return "【已确认的职业档案】\n" + "\n".join(lines)


def _conversation_context(db: Session, user_id: int) -> str:
    """会话摘要 + 近期用户消息样本（轻量，不塞全量）。"""
    parts: list[str] = []
    summaries = list(
        db.scalars(
            select(CareerConversation)
            .where(
                CareerConversation.user_id == user_id,
                CareerConversation.summary.is_not(None),
            )
            .order_by(CareerConversation.updated_at.desc())
            .limit(5)
        )
    )
    for conversation in summaries:
        parts.append(f"-（会话「{conversation.title}」）{conversation.summary}")
    if parts:
        parts_text = "\n".join(parts)
        parts_text = f"【近期对话摘要】\n{parts_text}"
    else:
        parts_text = ""
    return parts_text


def _skill_profile_block(db: Session, user_id: int) -> str:
    """观己：真实问澜评分画像；度衡：真实挑战记录；成长轨迹：真实打卡。"""
    lines: list[str] = []
    try:
        profile = build_skill_profile(db, user_id=user_id)
        if profile.has_data:
            dims = "、".join(
                f"{name} {value:.1f} 分" for name, value in sorted(
                    profile.dimension_averages.items(), key=lambda kv: kv[1], reverse=True
                )
            )
            average = f"{profile.average_score:.1f}" if profile.average_score is not None else "—"
            lines.append(
                f"【观己 · 问澜真实评分】已完成 {profile.completed_interviews} 场，平均 {average} 分；"
                f"维度：{dims or '无'}；练习过的岗位：{'、'.join(profile.positions_practiced) or '无'}"
            )
        else:
            lines.append("【观己 · 问澜真实评分】暂无完成的面试练习")
    except Exception:  # noqa: BLE001 — 证据收集失败不阻塞分析，如实降级
        logger.warning("skill profile gather failed", exc_info=True)
        lines.append("【观己 · 问澜真实评分】暂时取不到")

    try:
        runs = list(
            db.scalars(
                select(ChallengeRun)
                .where(ChallengeRun.user_id == user_id)
                .order_by(ChallengeRun.id.desc())
                .limit(20)
            )
        )
        lines.append(f"【度衡 · 限时挑战】最近共 {len(runs)} 次记录")
    except Exception:  # noqa: BLE001
        lines.append("【度衡 · 限时挑战】暂时取不到")

    try:
        from datetime import date

        heatmap = growth_heatmap(db, user_id, date.today().year)
        streak = heatmap.get("current_streak")
        total = heatmap.get("total_active_days")
        lines.append(f"【成长轨迹】今年活跃 {total} 天，连续打卡 {streak} 天")
    except Exception:  # noqa: BLE001
        lines.append("【成长轨迹】暂时取不到")
    return "\n".join(lines)


def _resume_block(db: Session, user_id: int) -> str:
    """履历成章：最近一份简历的结构化内容（真实数据，可缺省）。"""
    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.updated_at.desc(), Resume.id.desc())
    )
    if resume is None:
        return "【履历成章 · 简历】暂无简历"
    try:
        content = json.dumps(resume.content, ensure_ascii=False)
    except (TypeError, ValueError):
        content = str(resume.content)
    return f"【履历成章 · 简历《{resume.title}》】\n{content[:2500]}"


def _job_block(db: Session, user_id: int, job_analysis_id: int | None) -> str:
    """知岗：指定或最新一份真实 JD 解析（可缺省）。"""
    statement = select(JobAnalysis).where(
        JobAnalysis.user_id == user_id, JobAnalysis.status == "ready"
    )
    if job_analysis_id is not None:
        statement = statement.where(JobAnalysis.id == job_analysis_id)
    job = db.scalar(statement.order_by(JobAnalysis.created_at.desc(), JobAnalysis.id.desc()))
    if job is None:
        return "【知岗 · 岗位解析】暂无解析记录"
    try:
        result = json.dumps(job.result or {}, ensure_ascii=False)
    except (TypeError, ValueError):
        result = str(job.result)
    return f"【知岗 · 岗位解析《{job.title}》】\nJD 原文节选：{job.jd_text[:800]}\n结构化结论：{result[:1500]}"


def _job_for_user(db: Session, user_id: int, job_analysis_id: int | None) -> JobAnalysis | None:
    statement = select(JobAnalysis).where(JobAnalysis.user_id == user_id)
    if job_analysis_id is not None:
        statement = statement.where(JobAnalysis.id == job_analysis_id)
    else:
        statement = statement.where(JobAnalysis.status == "ready")
    return db.scalar(statement.order_by(JobAnalysis.created_at.desc(), JobAnalysis.id.desc()))


def analyze_situation(db: Session, client: ArkClient, user_id: int) -> dict:
    """当前情况总结：背景、已有证据与不确定点。"""
    user_payload = "\n\n".join(
        block
        for block in (
            _profile_block(db, user_id),
            _conversation_context(db, user_id),
            _skill_profile_block(db, user_id),
            _resume_block(db, user_id),
        )
        if block
    )
    data = client.chat_json(
        ANALYST_SYSTEM,
        user_payload
        + "\n\n请输出 JSON：{\"summary\": \"当前情况总结（3-5 句）\", \"known\": [\"已确认的关键信息\"], "
          "\"uncertain\": [\"尚不确定、需要用户补充的信息\"], \"suggested_focus\": [\"建议下一步聚焦的方向\"]}",
        temperature=0.3,
        service="career_analyst",
    )
    return {
        "summary": str(data.get("summary") or "").strip(),
        "known": _string_list(data.get("known"), 8),
        "uncertain": _string_list(data.get("uncertain"), 8),
        "suggested_focus": _string_list(data.get("suggested_focus"), 5),
    }


def explore_directions(db: Session, client: ArkClient, user_id: int) -> dict:
    """职业方向探索：多个可能方向 + 证据 + 不确定性，不武断定性。"""
    user_payload = "\n\n".join(
        block
        for block in (
            _profile_block(db, user_id),
            _conversation_context(db, user_id),
            _skill_profile_block(db, user_id),
            _resume_block(db, user_id),
        )
        if block
    )
    data = client.chat_json(
        ANALYST_SYSTEM,
        user_payload
        + "\n\n请提出 2-4 个值得探索的职业方向，输出 JSON："
          "{\"directions\": [{\"name\": \"方向名\", \"fit\": \"值得探索|需要验证|证据不足\", "
          "\"relation\": \"与用户现有经历的关系\", \"requirements\": [\"该方向常见岗位要求\"], "
          "\"evidence\": [\"用户已有的能力证据\"], \"unknowns\": [\"未明确的情况\"], "
          "\"conditions\": [\"需要进一步验证的条件\"], \"next_steps\": [\"建议的下一步探索\"]}], "
          "\"note\": \"提醒：这是基于现有信息的探索建议，不是结论\"}",
        temperature=0.4,
        service="career_analyst",
    )
    directions = []
    for item in data.get("directions", [])[:4] if isinstance(data.get("directions"), list) else []:
        if not isinstance(item, dict):
            continue
        fit = str(item.get("fit") or "需要验证")
        if fit not in {"值得探索", "需要验证", "证据不足"}:
            fit = "需要验证"
        directions.append(
            {
                "name": str(item.get("name") or "").strip()[:60],
                "fit": fit,
                "relation": str(item.get("relation") or "").strip(),
                "requirements": _string_list(item.get("requirements"), 5),
                "evidence": _string_list(item.get("evidence"), 5),
                "unknowns": _string_list(item.get("unknowns"), 5),
                "conditions": _string_list(item.get("conditions"), 5),
                "next_steps": _string_list(item.get("next_steps"), 5),
            }
        )
    directions = [item for item in directions if item["name"]]
    return {
        "directions": directions,
        "note": str(data.get("note") or "").strip()
        or "这是基于现有信息的探索建议，不是结论；结果不构成对求职成功的承诺。",
    }


def gap_analysis(db: Session, client: ArkClient, user_id: int, job_analysis_id: int | None = None) -> dict:
    """能力差距分析：结合真实 JD、简历、问澜评分，找证据缺口。"""
    job = _job_for_user(db, user_id, job_analysis_id)
    user_payload = "\n\n".join(
        block
        for block in (
            _profile_block(db, user_id),
            _job_block(db, user_id, job.id if job else None),
            _resume_block(db, user_id),
            _skill_profile_block(db, user_id),
        )
        if block
    )
    data = client.chat_json(
        ANALYST_SYSTEM,
        user_payload
        + "\n\n请做能力差距分析，输出 JSON："
          "{\"target_role\": \"分析的目标岗位（无 JD 时根据档案推断并说明）\", "
          "\"have\": [\"用户已有的技能/经历\"], \"required\": [\"目标岗位的要求\"], "
          "\"proven\": [\"已有真实证据证明的能力（来自简历/问澜/挑战）\"], "
          "\"missing\": [\"缺少证据的能力（是缺证据，不是断言用户不会）\"], "
          "\"buildable\": [\"可以补足的能力及方式\"], "
          "\"practice_tasks\": [\"适合安排的实践任务\"], \"notes\": \"其他说明与不确定点\"}",
        temperature=0.3,
        service="career_analyst",
    )
    return {
        "target_role": str(data.get("target_role") or "").strip() or "未明确说明",
        "have": _string_list(data.get("have"), 8),
        "required": _string_list(data.get("required"), 8),
        "proven": _string_list(data.get("proven"), 8),
        "missing": _string_list(data.get("missing"), 8),
        "buildable": _string_list(data.get("buildable"), 8),
        "practice_tasks": _string_list(data.get("practice_tasks"), 6),
        "notes": str(data.get("notes") or "").strip(),
        "job_analysis_id": job.id if job else None,
    }


def generate_plan(
    db: Session,
    client: ArkClient,
    user_id: int,
    *,
    conversation_id: int | None = None,
    job_analysis_id: int | None = None,
    goal: str | None = None,
) -> CareerPlan:
    """生成 7/30/90 天行动计划并落库（含首个版本快照）。"""
    job = _job_for_user(db, user_id, job_analysis_id)
    user_payload = "\n\n".join(
        block
        for block in (
            _profile_block(db, user_id),
            _conversation_context(db, user_id),
            _job_block(db, user_id, job.id if job else None),
            _resume_block(db, user_id),
            _skill_profile_block(db, user_id),
            f"【用户指定的目标】{goal}" if goal else "",
        )
        if block
    )
    data = client.chat_json(
        PLANNER_SYSTEM, user_payload, temperature=0.4, service="career_planner"
    )
    raw_actions = data.get("actions") if isinstance(data.get("actions"), list) else []
    plan = CareerPlan(
        user_id=user_id,
        conversation_id=conversation_id,
        title=str(data.get("title") or "我的成长计划").strip()[:120] or "我的成长计划",
        situation=str(data.get("situation") or "").strip(),
        focus_role=(str(data.get("focus_role")).strip()[:120] or None)
        if data.get("focus_role")
        else None,
        version_no=1,
    )
    db.add(plan)
    db.flush()  # 拿到 plan.id 再挂行动

    position = 0
    for item in raw_actions[:12]:
        if not isinstance(item, dict):
            continue
        phase = str(item.get("phase") or "30d").strip()
        if phase not in VALID_PHASES:
            phase = "30d"
        goal_text = str(item.get("goal") or "").strip()
        if not goal_text:
            continue
        plan.actions.append(
            CareerPlanAction(
                plan_id=plan.id,
                user_id=user_id,
                phase=phase,
                goal=goal_text[:200],
                steps=str(item.get("steps") or "").strip()[:1000],
                related_goal=(str(item.get("related_goal") or "").strip()[:200] or None),
                position=position,
            )
        )
        position += 1
    if not plan.actions:
        raise ValueError("AI 模型未能生成有效的计划任务，请稍后重试或补充更多信息")

    # 规划所依据的数据版本：记录生成时真实数据源与岗位解析依据（复盘时会更新）
    from app.services.career_planning_service import collect_data_basis

    plan.data_basis = collect_data_basis(db, user_id)
    if job is not None:
        plan.data_basis["job_analysis_id"] = job.id
        plan.data_basis["job_title"] = job.title

    from datetime import timedelta

    now = utcnow()
    for action in plan.actions:
        days = {"7d": 7, "30d": 30, "90d": 90}[action.phase]
        action.due_at = now + timedelta(days=days)
    db.add_all(plan.actions)
    db.commit()
    db.refresh(plan)

    revision = CareerPlanRevision(
        plan_id=plan.id,
        user_id=user_id,
        version_no=1,
        change_note="初始生成",
        snapshot=plan_snapshot(plan),
    )
    db.add(revision)
    db.commit()
    return plan


def plan_snapshot(plan: CareerPlan) -> dict:
    return {
        "title": plan.title,
        "situation": plan.situation,
        "focus_role": plan.focus_role,
        "status": plan.status,
        "actions": [
            {
                "phase": action.phase,
                "goal": action.goal,
                "steps": action.steps,
                "status": action.status,
                "due_at": action.due_at.isoformat() if action.due_at else None,
                "related_goal": action.related_goal,
            }
            for action in sorted(plan.actions, key=lambda item: item.position)
        ],
    }


def _string_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value[:limit]:
        text = str(item).strip()
        if text:
            items.append(text[:200])
    return items
