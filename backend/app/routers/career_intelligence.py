"""知途高级能力路由（第十五阶段）：能力图谱、多路径比较、RAG 检索、记忆管理、
规划复盘与版本、成长反馈、评测记录。

复用现有认证（current_user_id）、模型客户端（get_ark_client）与规划数据模型；
所有端点按 user_id 严格隔离，越权一律 404；失败不伪装成功。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import (
    CareerEvalRun,
    CareerPlan,
    CareerPlanRevision,
    JobAnalysis,
)
from app.routers.interviews import get_ark_client
from app.schemas.career_intelligence import (
    EvalRunOut,
    GraphEdgeCreate,
    GraphNodeStatusUpdate,
    GraphOut,
    GraphSyncRequest,
    PathCompareRequest,
    PathComparisonOut,
    RetrievalSearchRequest,
    ReviewApplyRequest,
)
from app.services import (
    career_paths,
    career_planning_service,
    career_retrieval,
    career_skill_graph,
)
from app.services.ark_client import ArkClient
from app.services.career_eval_rules import DATASET_VERSION
from app.services.interview_service import map_ark_error

logger = logging.getLogger("aurel.career")

router = APIRouter(prefix="/api/v1/career-guide", tags=["career-intelligence"])


def _get_owned_plan(db: Session, plan_id: int, user_id: int) -> CareerPlan:
    plan = db.get(CareerPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="计划不存在")
    return plan


# ---------- 能力图谱 ----------


@router.get("/graph", response_model=GraphOut)
def get_graph(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> GraphOut:
    """查看能力图谱：节点四态（已证实/用户自述/AI推断/尚待验证）+ 来源可追溯的边。"""
    return GraphOut.model_validate(career_skill_graph.get_graph(db, user_id))


@router.post("/graph/sync", response_model=GraphOut)
def sync_graph(
    payload: GraphSyncRequest | None = None,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> GraphOut:
    """从本人真实数据（档案事实/简历/知岗解析）幂等同步图谱节点。"""
    request = payload or GraphSyncRequest()
    career_skill_graph.sync_profile_skill_facts(db, user_id)
    if request.include_knowledge:
        career_retrieval.sync_user_index(db, user_id)
    for analysis in db.scalars(
        select(JobAnalysis).where(JobAnalysis.user_id == user_id, JobAnalysis.status == "ready")
    ).all():
        career_skill_graph.update_after_job_analysis(db, user_id, analysis)
    return GraphOut.model_validate(career_skill_graph.get_graph(db, user_id))


@router.post("/graph/suggest", response_model=GraphOut)
def suggest_graph_nodes(
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> GraphOut:
    """AI 依据档案与简历提议能力节点：一律 ai_inferred 状态，依据定位不到的丢弃。"""
    try:
        career_skill_graph.suggest_from_profile(db, client, user_id)
    except Exception as exc:  # noqa: BLE001 — 由统一错误映射处理
        raise map_ark_error(exc) from exc
    return GraphOut.model_validate(career_skill_graph.get_graph(db, user_id))


@router.patch("/graph/nodes/{node_id}")
def update_graph_node(
    node_id: int,
    payload: GraphNodeStatusUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> dict:
    """用户修正节点状态。verified 只能来自真实练习，不能手工标记。"""
    try:
        node = career_skill_graph.update_node_status(db, user_id, node_id, payload.status, payload.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "id": node.id,
        "name": node.name,
        "status": node.status,
        "note": node.note,
        "message": "已更新；该修正会同步影响图谱展示",
    }


@router.delete("/graph/nodes/{node_id}", status_code=204)
def delete_graph_node(
    node_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    try:
        career_skill_graph.delete_node(db, user_id, node_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/graph/edges", response_model=GraphOut)
def create_graph_edge(
    payload: GraphEdgeCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> GraphOut:
    try:
        career_skill_graph.add_user_edge(db, user_id, payload.from_node_id, payload.to_node_id, payload.relation)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return GraphOut.model_validate(career_skill_graph.get_graph(db, user_id))


# ---------- 多职业路径比较 ----------


@router.post("/paths/compare", response_model=PathComparisonOut, status_code=201)
def compare_paths(
    payload: PathCompareRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> PathComparisonOut:
    """比较 2-4 个职业方向：真实调用模型 + 知潮岗位来源 + 知藏检索证据；结果保存。"""
    try:
        record = career_paths.compare_paths(
            db, client, user_id, directions=payload.directions, note=payload.note or ""
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — ArkError 等统一映射
        raise map_ark_error(exc) from exc
    return PathComparisonOut.model_validate(record)


@router.get("/paths", response_model=list[PathComparisonOut])
def list_paths(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> list[PathComparisonOut]:
    records = career_paths.list_comparisons(db, user_id)
    return [PathComparisonOut.model_validate(record) for record in records]


@router.get("/paths/{comparison_id}", response_model=PathComparisonOut)
def get_path(
    comparison_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> PathComparisonOut:
    record = career_paths.get_comparison(db, user_id, comparison_id)
    if record is None:
        raise HTTPException(status_code=404, detail="比较记录不存在")
    return PathComparisonOut.model_validate(record)


@router.delete("/paths/{comparison_id}", status_code=204)
def delete_path(
    comparison_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    record = career_paths.get_comparison(db, user_id, comparison_id)
    if record is None:
        raise HTTPException(status_code=404, detail="比较记录不存在")
    db.delete(record)
    db.commit()


# ---------- RAG 职业知识检索 ----------


@router.post("/retrieval/search")
def search_knowledge(
    payload: RetrievalSearchRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> dict:
    """混合检索（BM25 + 词面向量 + RRF + 重排序），来源可见、过期降权、无据如实说明。"""
    outcome = career_retrieval.search_knowledge(
        db,
        user_id=user_id,
        query=payload.query,
        top_k=payload.top_k,
        industry_id=payload.industry_id,
        occupation_id=payload.occupation_id,
        experience_level=payload.experience_level,
        source_kinds=payload.source_kinds,
    )
    outcome["disclaimer"] = (
        "检索结果仅含事实性摘要与来源引用；无法检索到可靠依据时，知途不会据此编造建议。"
    )
    return outcome


@router.post("/retrieval/sync")
def sync_retrieval_index(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> dict:
    """重建检索索引：全局（知潮岗位/指导资料）+ 本人（知岗解析/知藏文档/档案）。"""
    global_index = career_retrieval.sync_global_index(db)
    user_index = career_retrieval.sync_user_index(db, user_id)
    return {
        "global_added": global_index["added"],
        "user_added": user_index["added"],
        "stats": career_retrieval.index_stats(db, user_id),
    }


@router.get("/retrieval/stats")
def retrieval_stats(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> dict:
    return career_retrieval.index_stats(db, user_id)


# ---------- 记忆透明化与清除 ----------


@router.get("/memory/usage")
def memory_usage(
    conversation_id: int | None = Query(default=None),
    query: str | None = Query(default=None, max_length=300),
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> dict:
    """查看一次回答将使用哪些记忆（档案/召回/摘要分层预览）。"""
    try:
        return career_planning_service.memory_usage(db, user_id, conversation_id, query)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/memory")
def clear_memory(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> dict:
    """清除记忆并重新开始：删除本人全部会话与档案事实（立即退出检索与上下文）。"""
    return career_planning_service.clear_memory(db, user_id)


# ---------- 规划复盘与版本 ----------


@router.get("/plans/{plan_id}/revisions")
def list_plan_revisions(
    plan_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> list[dict]:
    """规划版本列表（历史不可变，可回看）。"""
    plan = _get_owned_plan(db, plan_id, user_id)
    revisions = list(
        db.scalars(
            select(CareerPlanRevision)
            .where(CareerPlanRevision.plan_id == plan.id)
            .order_by(CareerPlanRevision.version_no.desc())
        )
    )
    return [
        {
            "version_no": revision.version_no,
            "change_note": revision.change_note,
            "has_review": "review" in (revision.snapshot or {}),
            "created_at": revision.created_at.isoformat(),
        }
        for revision in revisions
    ]


@router.get("/plans/{plan_id}/revisions/{version_no}")
def get_plan_revision(
    plan_id: int,
    version_no: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> dict:
    """打开某一版规划的完整快照（含当时数据依据与复盘记录）。"""
    plan = _get_owned_plan(db, plan_id, user_id)
    revision = db.scalar(
        select(CareerPlanRevision).where(
            CareerPlanRevision.plan_id == plan.id,
            CareerPlanRevision.version_no == version_no,
        )
    )
    if revision is None:
        raise HTTPException(status_code=404, detail="规划版本不存在")
    return {
        "version_no": revision.version_no,
        "change_note": revision.change_note,
        "snapshot": revision.snapshot,
        "created_at": revision.created_at.isoformat(),
    }


@router.post("/plans/{plan_id}/review")
def review_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> dict:
    """复盘：基于真实完成情况与练习记录产出复盘与新版本；历史不覆盖。"""
    try:
        outcome = career_planning_service.review_plan(db, client, user_id, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — ArkError 统一映射
        raise map_ark_error(exc) from exc
    plan, review = outcome["plan"], outcome["review"]
    from app.schemas.career import PlanOut

    return {
        "plan": PlanOut.model_validate(plan).model_dump(mode="json"),
        "review": review,
        "disclaimer": "复盘仅基于平台内真实记录；调整建议需你确认后才会写入计划。",
    }


@router.post("/plans/{plan_id}/review/apply")
def apply_review(
    plan_id: int,
    payload: ReviewApplyRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> dict:
    """用户确认后采纳复盘调整建议（写入计划并生成新版本）。"""
    try:
        plan = career_planning_service.apply_review_adjustments(
            db, user_id, plan_id, payload.adjustments
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from app.schemas.career import PlanOut

    return {
        "plan": PlanOut.model_validate(plan).model_dump(mode="json"),
        "message": "已按你的确认写入计划并生成新版本",
    }


# ---------- 成长反馈 ----------


@router.get("/growth")
def growth_feedback(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
) -> dict:
    """成长趋势：只来自真实练习与行动记录；无记录时返回空状态。"""
    return career_planning_service.growth_feedback(db, user_id)


# ---------- 评测 ----------


@router.get("/eval-runs", response_model=list[EvalRunOut])
def list_eval_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> list[EvalRunOut]:
    """评测记录（含模型/提示词/数据集版本与指标）。"""
    runs = list(
        db.scalars(
            select(CareerEvalRun)
            .order_by(CareerEvalRun.id.desc())
            .limit(limit)
        )
    )
    return [EvalRunOut.model_validate(run) for run in runs]


@router.post("/eval/offline", status_code=201)
def run_offline_eval(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> dict:
    """运行离线评测：人工数据集校验规则判定器（judge_accuracy 必须为 1.0），结果入库。"""
    from eval.run_career_eval import load_dataset, persist_run, run_offline

    dataset = load_dataset()
    report = run_offline(dataset)
    persist_run(
        report["metrics"],
        report["results"],
        model="rule-judge",
        prompt_version="n/a",
        session=db,
    )
    return {
        "metrics": report["metrics"],
        "dataset_version": DATASET_VERSION,
        "note": "离线评测只校验判定器与人工标注的一致性，不代表模型质量。",
    }
