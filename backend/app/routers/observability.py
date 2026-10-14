"""T10 调用观测 API：近期调用明细、按服务/模型聚合统计、提示词版本。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LlmCallRecord
from app.schemas.observability import LlmCallOut, LlmStatsOut, ServiceStats
from app.services.prompt_registry import CHANGELOG, PROMPT_VERSIONS

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])

STATS_SCAN_LIMIT = 2000  # 统计扫描的最近记录上限，防止全表增长后变慢


@router.get("/llm-calls", response_model=list[LlmCallOut])
def list_llm_calls(limit: int = 50, db: Session = Depends(get_db)) -> list[LlmCallOut]:
    limit = max(1, min(limit, 200))
    statement = (
        select(LlmCallRecord)
        .order_by(LlmCallRecord.created_at.desc(), LlmCallRecord.id.desc())
        .limit(limit)
    )
    return [LlmCallOut.model_validate(row) for row in db.scalars(statement)]


def _group_stats(rows: list[LlmCallRecord], key) -> dict[str, ServiceStats]:
    groups: dict[str, list[LlmCallRecord]] = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    stats: dict[str, ServiceStats] = {}
    for name, members in groups.items():
        errors = sum(1 for m in members if m.status == "error")
        stats[name] = ServiceStats(
            calls=len(members),
            errors=errors,
            success_rate=round(1 - errors / len(members), 4) if members else 0.0,
            avg_latency_ms=round(sum(m.latency_ms for m in members) / len(members), 1)
            if members
            else 0.0,
        )
    return stats


@router.get("/llm-stats", response_model=LlmStatsOut)
def llm_stats(db: Session = Depends(get_db)) -> LlmStatsOut:
    statement = (
        select(LlmCallRecord)
        .order_by(LlmCallRecord.created_at.desc(), LlmCallRecord.id.desc())
        .limit(STATS_SCAN_LIMIT)
    )
    rows = list(db.scalars(statement))
    errors = sum(1 for row in rows if row.status == "error")
    return LlmStatsOut(
        total=len(rows),
        errors=errors,
        success_rate=round(1 - errors / len(rows), 4) if rows else 0.0,
        avg_latency_ms=round(sum(row.latency_ms for row in rows) / len(rows), 1) if rows else 0.0,
        by_service=_group_stats(rows, lambda row: row.service),
        by_model=_group_stats(rows, lambda row: row.model),
        experiment_calls=sum(1 for row in rows if row.experiment),
    )


@router.get("/prompt-versions")
def prompt_versions() -> dict:
    return {"versions": PROMPT_VERSIONS, "changelog": CHANGELOG}
