"""知途联动工作流：多步骤真实调用各模块服务，逐步留痕、失败如实记录。

不能只在聊天回复里说「已经帮你分析」，这里每一步都真实执行：
- gap_analysis：档案 → 知岗 JD → 履历成章简历 → 知藏检索 → 观己/度衡/成长轨迹证据 → AI 差距分析；
- interview_prep：目标 → 知藏证据 → 真实创建问澜面试练习（复用 interview_service）。
"""

import logging

from sqlalchemy.orm import Session

from app.models import CareerWorkflowRun, JobAnalysis, utcnow
from app.schemas.interview import InterviewCreateRequest
from app.services import career_analyst, interview_service
from app.services.ark_client import ArkClient
from app.services.knowledge_service import retrieve_evidence

logger = logging.getLogger("aurel.career")

WORKFLOW_KINDS = {"gap_analysis", "interview_prep"}


def run_workflow(
    db: Session, client: ArkClient, user_id: int, kind: str, params: dict | None
) -> CareerWorkflowRun:
    """执行工作流并返回持久化的运行记录；失败记录真实原因，绝不伪造成功。"""
    if kind not in WORKFLOW_KINDS:
        raise ValueError(f"未知的工作流类型：{kind}")
    run = CareerWorkflowRun(
        user_id=user_id, kind=kind, params=params or {}, steps=[], status="running"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    steps = _StepRecorder(db, run)
    try:
        if kind == "gap_analysis":
            result = _run_gap_analysis(db, client, user_id, steps, params or {})
        else:
            result = _run_interview_prep(db, client, user_id, steps, params or {})
        run.status = "succeeded"
        run.result = result
        steps.close("succeeded")
    except Exception as exc:  # noqa: BLE001 — 工作流失败必须如实记录
        logger.warning("career workflow %s failed: %s", kind, exc)
        run.error_message = str(exc)[:500]
        run.status = "failed"
        steps.close("failed")
    run.updated_at = utcnow()
    db.commit()
    db.refresh(run)
    return run


class _StepRecorder:
    """把每一步状态即时写库（请求会话内 commit），便于中断时也留下真实进度。"""

    def __init__(self, db: Session, run: CareerWorkflowRun) -> None:
        self.db = db
        self.run = run
        self._steps: list[dict] = []

    def begin(self, key: str, title: str) -> None:
        self._steps.append({"key": key, "title": title, "status": "running"})
        self._flush()

    def succeed(self, detail: str) -> None:
        self._steps[-1]["status"] = "succeeded"
        self._steps[-1]["detail"] = detail[:300]
        self._flush()

    def skip(self, detail: str) -> None:
        self._steps[-1]["status"] = "skipped"
        self._steps[-1]["detail"] = detail[:300]
        self._flush()

    def close(self, status: str) -> None:
        if self._steps and self._steps[-1]["status"] == "running":
            self._steps[-1]["status"] = status
            self._steps[-1]["detail"] = (self.run.error_message or "")[:300]
        self._flush()

    def _flush(self) -> None:
        self.run.steps = list(self._steps)
        self.db.commit()


def _run_gap_analysis(
    db: Session, client: ArkClient, user_id: int, steps: _StepRecorder, params: dict
) -> dict:
    job_analysis_id = params.get("job_analysis_id")

    steps.begin("profile", "读取已确认的职业档案")
    from app.services.career_memory import confirmed_facts

    facts = confirmed_facts(db, user_id)
    steps.succeed(f"载入 {len(facts)} 条已确认档案事实")

    steps.begin("job", "读取知岗岗位解析")
    from sqlalchemy import select

    job_statement = select(JobAnalysis).where(JobAnalysis.user_id == user_id)
    if job_analysis_id is not None:
        job_statement = job_statement.where(JobAnalysis.id == int(job_analysis_id))
    else:
        job_statement = job_statement.where(JobAnalysis.status == "ready")
    job = db.scalar(job_statement.order_by(JobAnalysis.created_at.desc(), JobAnalysis.id.desc()))
    if job is None:
        steps.skip("暂无知岗解析，将仅基于档案、简历与问澜数据")
    else:
        steps.succeed(f"使用解析《{job.title}》")

    steps.begin("resume", "读取履历成章简历")
    from app.models import Resume

    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.updated_at.desc(), Resume.id.desc())
    )
    if resume is None:
        steps.skip("暂无简历，可先到履历成章上传或创建")
    else:
        steps.succeed(f"使用简历《{resume.title}》")

    steps.begin("knowledge", "知藏检索相关知识")
    target = (job.title if job else None) or str(params.get("target") or "") or "职业发展"
    try:
        hits = retrieve_evidence(db, target, top_k=3, user_id=user_id)
        steps.succeed(f"知藏召回 {len(hits)} 条知识片段")
    except Exception as exc:  # noqa: BLE001 — 知藏失败不阻塞，但如实记录
        steps.skip(f"知藏检索暂不可用：{exc}")

    steps.begin("evidence", "汇总观己评分、度衡挑战与成长轨迹")
    evidence = career_analyst._skill_profile_block(db, user_id)
    steps.succeed("已汇总真实练习与打卡证据")

    steps.begin("ai_gap", "AI 能力差距分析")
    result = career_analyst.gap_analysis(
        db, client, user_id, job.id if job else None
    )
    result["evidence_digest"] = evidence
    steps.succeed(f"差距分析完成：目标 {result.get('target_role') or '未明确'}")
    return result


def _run_interview_prep(
    db: Session, client: ArkClient, user_id: int, steps: _StepRecorder, params: dict
) -> dict:
    from sqlalchemy import select

    steps.begin("target", "确定面试练习目标")
    position = str(params.get("position") or "").strip()
    if not position:
        job = db.scalar(
            select(JobAnalysis)
            .where(JobAnalysis.user_id == user_id, JobAnalysis.status == "ready")
            .order_by(JobAnalysis.created_at.desc(), JobAnalysis.id.desc())
        )
        if job is None:
            raise ValueError("没有可用的目标岗位：请先在知岗解析一份 JD，或在参数中给出 position")
        position = job.title
        params_job = job
    else:
        params_job = None
    steps.succeed(f"目标岗位：{position}")

    steps.begin("knowledge", "知藏检索相关证据")
    description = str(params.get("description") or "").strip() or (
        params_job.jd_text[:300] if params_job else ""
    )
    evidence_texts: list[str] = []
    try:
        for evidence in retrieve_evidence(
            db, f"{position}\n{description}".strip(), top_k=3, user_id=user_id
        ):
            evidence_texts.append(evidence.content)
        steps.succeed(f"召回 {len(evidence_texts)} 条知识证据")
    except Exception as exc:  # noqa: BLE001
        steps.skip(f"知藏检索暂不可用：{exc}")

    steps.begin("create_interview", "创建问澜面试练习（真实出题）")
    request = InterviewCreateRequest(
        position=position,
        description=description,
        difficulty=str(params.get("difficulty") or "intermediate"),
        language=str(params.get("language") or "zh"),
        question_count=int(params.get("question_count") or 5),
        knowledge_document_id=None,
    )
    task = interview_service.create_task(db, request, client, user_id=user_id)
    steps.succeed(f"问澜任务 #{task.id} 已创建，含 {task.question_count} 道题")
    return {
        "task_id": task.id,
        "position": task.position,
        "question_count": task.question_count,
        "message": "已在问澜创建真实面试练习，可前往「问澜」开始作答",
    }
