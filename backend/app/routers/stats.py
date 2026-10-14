"""成长轨迹统计路由：年度热力图、连续打卡与澜记周报。"""

import json
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import utcnow
from app.routers.interviews import get_ark_client
from app.schemas.insight import WeeklyNoteAi, WeeklyReportResponse
from app.services.ark_client import ArkClient, ArkError
from app.services.growth_stats import growth_heatmap, weekly_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

_WEEKLY_SYSTEM = """你是求职成长平台「观澜 AUREL」的周记撰写者。基于用户最近 7 天的真实练习数据，写一段 60-120 字的中文短评：
1. 如实概括本周的练习构成与节奏（不要编造数据之外的成绩）；
2. 给出下周一个具体、可执行的小建议；
3. 语气温和自然，可化用「水」「澜」「舟」意象，但不堆砌辞藻。
只输出 JSON：{"note": "..."}"""

_WEEKLY_KIND_LABELS = {
    "interview": "问澜训练",
    "challenge": "度衡挑战",
    "expression": "听澜分析",
    "mistake": "回澜复习",
}


@router.get("/heatmap")
def heatmap(
    year: int | None = Query(default=None, ge=2020, le=2100),
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> dict:
    """指定年份（默认当年）的逐日活动热力图与 streak 统计。"""
    target_year = year or utcnow().year
    return growth_heatmap(db, user_id, target_year)


@router.get("/weekly", response_model=WeeklyReportResponse)
def weekly(
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> WeeklyReportResponse:
    """澜记周报：近 7 日真实活动聚合 + AI 短评（AI 不可用时如实降级为无短评）。"""
    report = weekly_report(db, user_id)
    try:
        summary = {
            "period": f"{report['week_start']} 至 {report['week_end']}",
            "totals": {
                _WEEKLY_KIND_LABELS.get(kind, kind): count
                for kind, count in report["totals"].items()
            },
            "interviews_completed": report["interviews_completed"],
            "average_score": report["average_score"],
            "active_days": report["active_days"],
            "streak_current": report["streak_current"],
        }
        note = client.chat_json(
            _WEEKLY_SYSTEM,
            json.dumps(summary, ensure_ascii=False),
            temperature=0.5,
            service="weekly_note",
        )
        report["ai_note"] = WeeklyNoteAi.model_validate(note).note
    except (ArkError, ValidationError) as exc:
        # AI 短评是锦上添花：模型未配置 / 调用失败 / 结构不合格时如实返回无短评
        logger.info("weekly ai_note unavailable: %s", exc)
        report["ai_note"] = None
    return WeeklyReportResponse(**report)
