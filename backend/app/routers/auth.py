"""认证路由：用户名 + 密码注册/登录、会话管理。

- 密码只存 PBKDF2 摘要；登录失败统一返回"用户名或密码不匹配"，不泄露账户是否存在
- 会话令牌经 HttpOnly Cookie 下发，库内只存 SHA-256 摘要
- /me、/logout 自行解析 Cookie（未登录时返回明确状态而非 500）
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import User, utcnow
from app.schemas.auth import (
    AuthMeResponse,
    AuthUser,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
)
from app.services import auth_service
from app.services.password_service import hash_password, verify_password
from app.services.usage_tracking import record_event

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=auth_service.SESSION_COOKIE_NAME,
        value=token,
        max_age=config.session_ttl_hours() * 3600,
        httponly=True,
        secure=config.cookie_secure(),
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=auth_service.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=config.cookie_secure(),
        samesite="lax",
    )


def _token_from_request(request: Request) -> str:
    return request.cookies.get(auth_service.SESSION_COOKIE_NAME) or ""


def _auth_user_payload(user: User) -> AuthUser:
    return AuthUser(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        status=user.status,
        role=getattr(user, "role", None) or "user",
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _find_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.username) == username.lower()))


@router.post("/register", response_model=AuthMeResponse, status_code=201)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if _find_by_username(db, body.username) is not None:
        raise HTTPException(status_code=400, detail="该用户名已被使用，换一个试试")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        nickname=body.nickname,
    )
    db.add(user)
    db.flush()
    record_event(db, user_id=user.id, module="auth", name="register")
    db.commit()
    db.refresh(user)
    token, _ = auth_service.create_session(db, user.id)
    _set_session_cookie(response, token)
    return AuthMeResponse(authenticated=True, user=_auth_user_payload(user))


@router.post("/login", response_model=AuthMeResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = _find_by_username(db, body.username)
    # 用户不存在与密码错误返回同一提示，避免用户名枚举
    if user is None:
        verify_password(body.password, hash_password("timing-equalizer"))
        raise HTTPException(status_code=401, detail="用户名或密码不匹配，请核对后再试")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码不匹配，请核对后再试")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账户当前不可用，请联系维护者")

    user.last_login_at = utcnow()
    record_event(db, user_id=user.id, module="auth", name="login")
    db.commit()
    token, _ = auth_service.create_session(db, user.id)
    _set_session_cookie(response, token)
    return AuthMeResponse(authenticated=True, user=_auth_user_payload(user))


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = _token_from_request(request)
    if token:
        auth_service.revoke_session(db, token)
    _clear_session_cookie(response)
    return LogoutResponse(ok=True)


@router.get("/me", response_model=AuthMeResponse)
def me(request: Request, db: Session = Depends(get_db)):
    token = _token_from_request(request)
    if not token:
        return AuthMeResponse(authenticated=False)
    user = auth_service.resolve_session(db, token)
    if user is None:
        return AuthMeResponse(authenticated=False)
    return AuthMeResponse(authenticated=True, user=_auth_user_payload(user))
