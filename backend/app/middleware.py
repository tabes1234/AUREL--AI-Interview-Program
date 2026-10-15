"""T7/T8 + 认证：访问控制、会话认证与限流中间件。

- 访问控制三层：
  1) 用户会话（HttpOnly Cookie，库内摘要校验）——主要认证方式；
  2) AUREL_ACCESS_TOKEN Bearer（部署级运维令牌，设置后仅作为机器访问通道，
     不绑定用户数据，业务接口仍会要求用户登录）；
  3) 免认证端点（健康检查、公开状态、公告、公开目录、认证接口本身）。
- CSRF：写方法携带 Origin 时必须属于受信任来源（配合 SameSite=Lax Cookie）。
- 限流：按客户端 IP 的滑动窗口限流（AUREL_RATE_LIMIT_PER_MINUTE，0 关闭）。
"""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import config
from app.config import access_token, cors_origins, rate_limit_per_minute
from app.services import auth_service

# 免登录路径：健康检查、不含敏感信息的只读状态端点、公开公告与公开目录、公开模板指南、认证接口
AUTH_EXEMPT_PREFIXES = (
    "/api/v1/health",
    "/api/v1/ai/status",
    "/api/v1/expression/status",
    "/api/v1/announcements",
    "/api/v1/catalog",
    "/api/v1/resume-gallery",
    "/api/v1/auth",
)

RATE_LIMIT_EXEMPT_PREFIXES = ("/api/v1/health",)

# 需要 Origin 来源校验的写方法（CSRF 防御，配合 SameSite=Lax）
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def is_auth_exempt(path: str) -> bool:
    # 非 /api 路径（前端页面与静态资源）不涉用户数据，单容器部署时由后端托管 SPA，直接放行
    if not path.startswith("/api"):
        return True
    return any(path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES)


def is_rate_limit_exempt(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in RATE_LIMIT_EXEMPT_PREFIXES)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _origin_rejected(request: Request) -> bool:
    """跨站写请求防御：携带 Origin 时必须属于受信任来源。"""
    if request.method not in WRITE_METHODS:
        return False
    origin = request.headers.get("origin", "")
    if not origin:
        return False
    return origin not in cors_origins()


class AccessControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        if _origin_rejected(request):
            return JSONResponse({"detail": "请求来源不受信任，已拒绝该操作"}, status_code=403)
        if is_auth_exempt(request.url.path):
            return await call_next(request)

        token = access_token()
        header = request.headers.get("authorization", "")
        if token:
            if header == f"Bearer {token}":
                # 运维令牌通道：不绑定用户数据
                request.state.user_id = None
                return await call_next(request)
            if header:
                return JSONResponse(
                    {"detail": "访问令牌无效：请携带正确的 Authorization: Bearer <AUREL_ACCESS_TOKEN>"},
                    status_code=401,
                )

        cookie_token = request.cookies.get(auth_service.SESSION_COOKIE_NAME, "")
        if cookie_token:
            db = auth_service.open_session_db()
            try:
                user = auth_service.resolve_session(db, cookie_token)
            finally:
                db.close()
            if user is not None:
                request.state.user_id = user.id
                return await call_next(request)

        return JSONResponse(
            {"detail": "请先登录后访问：未持有有效会话"},
            status_code=401,
        )


# 实例注册表：便于测试与运维重置窗口状态
_RATE_LIMIT_INSTANCES: list["RateLimitMiddleware"] = []


def reset_rate_limits() -> None:
    for instance in _RATE_LIMIT_INSTANCES:
        instance._hits.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """固定 60 秒滑动窗口的内存限流（单进程部署足够；多副本需换集中式存储）。"""

    WINDOW_SECONDS = 60

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        _RATE_LIMIT_INSTANCES.append(self)

    async def dispatch(self, request: Request, call_next):
        limit = rate_limit_per_minute()
        if (
            limit <= 0
            or request.method == "OPTIONS"
            or is_rate_limit_exempt(request.url.path)
        ):
            return await call_next(request)

        key = client_ip(request)
        now = time.monotonic()
        window = self._hits[key]
        while window and now - window[0] > self.WINDOW_SECONDS:
            window.popleft()
        if len(window) >= limit:
            retry_after = max(1, int(self.WINDOW_SECONDS - (now - window[0])) + 1)
            return JSONResponse(
                {"detail": f"请求过于频繁，请 {retry_after} 秒后再试"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        window.append(now)

        # 防御：过期 IP 过多时做一次清理，避免长期运行内存膨胀
        if len(self._hits) > 10000:
            for stale in [k for k, v in self._hits.items() if not v]:
                self._hits.pop(stale, None)
        return await call_next(request)
