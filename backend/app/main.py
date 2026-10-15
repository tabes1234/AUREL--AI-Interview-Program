from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import SERVICE_NAME, VERSION, cors_origins
from app.logging_setup import setup_logging
from app.middleware import AccessControlMiddleware, RateLimitMiddleware
from app.routers import (
    announcements,
    auth,
    career,
    career_intelligence,
    catalog,
    challenges,
    expression,
    health,
    interviews,
    jobs,
    job_library,
    knowledge,
    matching,
    mistakes,
    observability,
    privacy,
    resume_gallery,
    resumes,
    skills,
    stats,
)

setup_logging()

# 启动时确保表结构存在（幂等：新表自动创建，已有表与数据不受影响）
from app import models as _models  # noqa: E402,F401 — 确保模型注册到 metadata
from app.database import engine  # noqa: E402
from app.models import ensure_sqlite_columns  # noqa: E402
from app.models_base import Base  # noqa: E402

Base.metadata.create_all(engine)
ensure_sqlite_columns()

# 知潮种子岗位：官方页面人工核对过的真实数据，幂等导入（已存在则跳过）
from app.database import SessionLocal  # noqa: E402
from app.services.job_library import seed_job_positions  # noqa: E402

try:
    with SessionLocal() as _seed_db:
        seed_job_positions(_seed_db)
except Exception:  # noqa: BLE001 — 种子导入失败不阻塞服务启动，真实错误记录日志
    import logging

    logging.getLogger(__name__).exception("知潮种子岗位导入失败")

# 启动即后台预热与模型服务之间的 TCP/TLS 连接，消除重启后首次 AI 调用的建连延迟
from app.services.ark_client import warmup_connection  # noqa: E402

warmup_connection()

app = FastAPI(
    title="AUREL 观澜 API",
    description="AI 驱动的能力探索与成长平台 — 后端服务",
    version=VERSION,
)

# 中间件自下而上生效：CORS（最外层）→ 限流 → 访问控制
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AccessControlMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(announcements.router)
app.include_router(catalog.router)
app.include_router(interviews.router)
app.include_router(knowledge.router)
app.include_router(skills.router)
app.include_router(matching.router)
app.include_router(expression.router)
app.include_router(jobs.router)
app.include_router(job_library.router)
app.include_router(resume_gallery.router)
app.include_router(resumes.router)
app.include_router(mistakes.router)
app.include_router(challenges.router)
app.include_router(stats.router)
app.include_router(career.router)
app.include_router(career_intelligence.router)
app.include_router(observability.router)
app.include_router(privacy.router)

# ---------- 单容器部署：托管前端构建产物（frontend/dist 存在时生效） ----------
# 本地开发仍由 Vite dev server 服务前端；dist 不存在时以下路由不注册，API 行为不变
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    from fastapi.responses import FileResponse

    @app.api_route(
        "/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False
    )
    async def spa_fallback(full_path: str) -> FileResponse:
        """静态文件直出；其余路径一律回退 index.html（SPA 前端路由）。"""
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="接口不存在")
        candidate = (_FRONTEND_DIST / full_path).resolve()
        # 防目录穿越：解析后必须仍在 dist 目录内
        if (
            full_path
            and str(candidate).startswith(str(_FRONTEND_DIST))
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
