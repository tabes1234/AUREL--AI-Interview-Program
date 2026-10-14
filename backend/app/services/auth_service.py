"""用户会话：不透明高熵令牌 + HttpOnly Cookie + 库内摘要存储。

- 令牌：secrets.token_urlsafe(32)（约 256 bit 熵），浏览器只持有明文令牌
- 数据库只存 SHA-256 摘要，泄露数据库无法直接伪造会话
- 有效期 AUREL_SESSION_TTL_HOURS（默认 7 天）；登出真实撤销（revoked_at）
- 会话工厂可替换（测试注入内存库）
"""

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.database import SessionLocal
from app.models import User, UserSession, utcnow

SESSION_COOKIE_NAME = "aurel_session"

_session_factory = SessionLocal


def set_session_factory(factory) -> None:
    """测试注入：替换会话查询使用的 session 工厂。"""
    global _session_factory
    _session_factory = factory


def open_session_db() -> Session:
    return _session_factory()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user_id: int) -> tuple[str, object]:
    token = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(hours=config.session_ttl_hours())
    record = UserSession(user_id=user_id, token_hash=hash_token(token), expires_at=expires_at)
    db.add(record)
    db.commit()
    return token, expires_at


def resolve_session(db: Session, token: str) -> User | None:
    """校验令牌：存在、未撤销、未过期、用户 active。"""
    record = db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(token)).limit(1)
    )
    if record is None or record.revoked_at is not None:
        return None
    if utcnow() > record.expires_at:
        return None
    user = db.get(User, record.user_id)
    if user is None or user.status != "active":
        return None
    return user


def revoke_session(db: Session, token: str) -> bool:
    record = db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(token)).limit(1)
    )
    if record is None or record.revoked_at is not None:
        return False
    record.revoked_at = utcnow()
    db.commit()
    return True
