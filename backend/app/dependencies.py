"""通用依赖：从中间件注入的会话身份获取当前用户。"""

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models import User


def current_user_id(request: Request) -> int:
    """中间件已通过会话认证时挂载 user_id；Bearer 运维令牌通道不绑定用户。"""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="该接口需要用户登录（运维令牌不绑定个人数据）",
        )
    return user_id


def get_current_user(request: Request, db: Session) -> User:
    user_id = current_user_id(request)
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="账户不存在或不可用，请重新登录")
    return user
