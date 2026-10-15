"""T3 技能图谱与自适应训练路由（全部由真实历史报告驱动，按登录用户聚合）。"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import JobAnalysis
from app.routers.interviews import get_ark_client
from app.schemas.features import (
    SkillGraphResponse,
    SkillProfileResponse,
    TrainingRecommendationResponse,
)
from app.schemas.insight import (
    GapAnalysisAiPlan,
    GapAnalysisRequest,
    GapAnalysisResponse,
)
from app.services.ark_client import ArkClient, ArkError
from app.services.interview_service import map_ark_error
from app.services.skill_service import (
    build_skill_graph,
    build_skill_profile,
    build_training_recommendation,
)
from app.services.usage_tracking import record_event

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])

_GAP_SYSTEM = """你是求职成长平台「观澜 AUREL」的星图对照分析师。输入包含：
1. profile：用户观己能力快照（dimension_averages 为各维度均分 0-10，可能为空）；
2. job：目标岗位（来自知岗解析的 capability_dimensions 与 keywords）。

请从输入提供的「候选维度清单」（profile 与 job 的维度名并集）中挑选 3-8 个最关键的维度，输出：
- name：逐字复用候选清单中的维度名，不得自创；
- target：该岗位对此维度的要求水平（0-10 数字，1 位小数）；
- gap_note：不超过 60 字的中文差距点评（现状→目标的具体练法；无数据时给入门建议）；
- overall_note：一段 80-150 字的中文总评（如实现状与岗位的总体距离与接下来两周的重点）。
只输出 JSON。"""


@router.get("/profile", response_model=SkillProfileResponse)
def get_profile(db: Session = Depends(get_db), user_id: int = Depends(current_user_id)):
    profile = build_skill_profile(db, user_id=user_id)
    return SkillProfileResponse(
        has_data=profile.has_data,
        completed_interviews=profile.completed_interviews,
        average_score=profile.average_score,
        latest_score=profile.latest_score,
        dimension_averages=profile.dimension_averages,
        positions_practiced=profile.positions_practiced,
    )


@router.get("/graph", response_model=SkillGraphResponse)
def get_graph(db: Session = Depends(get_db), user_id: int = Depends(current_user_id)):
    profile = build_skill_profile(db, user_id=user_id)
    return SkillGraphResponse(**build_skill_graph(profile))


@router.get("/recommendation", response_model=TrainingRecommendationResponse)
def get_recommendation(db: Session = Depends(get_db), user_id: int = Depends(current_user_id)):
    profile = build_skill_profile(db, user_id=user_id)
    return TrainingRecommendationResponse(**build_training_recommendation(profile))


@router.post("/gap-analysis", response_model=GapAnalysisResponse)
def gap_analysis(
    request: GapAnalysisRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> GapAnalysisResponse:
    """星图对照：观己能力快照 × 知岗岗位要求，AI 生成差距分析与目标画像。

    current 一律由服务端从真实能力快照回填（无数据为 0），不采信模型给的现值。
    """
    analysis = db.get(JobAnalysis, request.job_analysis_id)
    if (
        analysis is None
        or analysis.user_id != user_id
        or analysis.status != "ready"
        or not analysis.result
    ):
        raise HTTPException(status_code=404, detail="岗位解析不存在或不可用")

    profile = build_skill_profile(db, user_id=user_id)
    result = analysis.result or {}
    job_dims = [d for d in result.get("capability_dimensions", []) if isinstance(d, str)]
    keywords = [k for k in result.get("keywords", []) if isinstance(k, str)][:12]
    candidates = list(dict.fromkeys([*profile.dimension_averages.keys(), *job_dims]))[:12]
    if not candidates:
        raise HTTPException(
            status_code=422, detail="该岗位解析缺少能力维度信息，无法进行星图对照"
        )

    user_payload = json.dumps(
        {
            "profile": {
                "has_data": profile.has_data,
                "completed_interviews": profile.completed_interviews,
                "average_score": profile.average_score,
                "dimension_averages": profile.dimension_averages,
                "positions_practiced": profile.positions_practiced,
            },
            "job": {
                "position": analysis.title,
                "capability_dimensions": job_dims,
                "keywords": keywords,
            },
            "candidate_dimensions": candidates,
        },
        ensure_ascii=False,
    )

    try:
        raw = client.chat_json(
            _GAP_SYSTEM, user_payload, temperature=0.3, service="gap_analysis"
        )
    except ArkError as exc:
        raise map_ark_error(exc) from exc

    try:
        plan = GapAnalysisAiPlan.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI 输出结构不合格，无法生成星图对照：{exc.errors()[0].get('msg', '')}",
        ) from exc

    dimensions = []
    for dim in plan.dimensions:
        current = profile.dimension_averages.get(dim.name)
        dimensions.append(
            {
                "name": dim.name,
                # 现值由服务端回填：无真实数据时如实记 0（前端以 has_data 提示）
                "current": round(float(current), 2) if current is not None else 0.0,
                "target": dim.target,
                "gap_note": dim.gap_note,
            }
        )

    record_event(db, user_id=user_id, module="guanji", name="gap_analysis")
    db.commit()
    return GapAnalysisResponse(
        position=analysis.title,
        has_data=profile.has_data,
        completed_interviews=profile.completed_interviews,
        average_score=profile.average_score,
        dimensions=dimensions,
        overall_note=plan.overall_note,
        model_name=getattr(client, "model", None),
    )
