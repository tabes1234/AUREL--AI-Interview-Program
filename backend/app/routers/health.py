from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import SERVICE_NAME, VERSION
from app.database import get_db
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, version=VERSION)


@router.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)) -> dict:
    """T8 就绪检查：数据库可用才返回 ready，否则 503（供部署探针使用）。"""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库不可用：{exc.__class__.__name__}") from exc
    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "version": VERSION,
        "checks": {"database": "ok"},
    }
