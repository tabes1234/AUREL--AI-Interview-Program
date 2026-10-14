"""认证接口 Schema：用户名 + 密码注册/登录；密码不出现在任何响应中。"""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]{3,24}$")
PASSWORD_LETTER = re.compile(r"[A-Za-z]")
PASSWORD_DIGIT = re.compile(r"\d")


def normalize_username(value: str) -> str:
    return value.strip()


class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        username = normalize_username(value)
        if not USERNAME_PATTERN.fullmatch(username):
            raise ValueError("用户名需为 3-24 位中英文、数字或下划线")
        return username

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        if not 8 <= len(value) <= 64:
            raise ValueError("密码长度需在 8-64 位之间")
        if not PASSWORD_LETTER.search(value) or not PASSWORD_DIGIT.search(value):
            raise ValueError("密码需同时包含字母和数字")
        return value

    @field_validator("nickname")
    @classmethod
    def _check_nickname(cls, value: str) -> str:
        nickname = value.strip()
        if not 2 <= len(nickname) <= 20:
            raise ValueError("昵称需在 2-20 个字符之间")
        return nickname


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _normalize(cls, value: str) -> str:
        username = normalize_username(value)
        if not username:
            raise ValueError("请填写用户名")
        return username

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        if not value:
            raise ValueError("请填写密码")
        return value


class AuthUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    status: str
    created_at: datetime
    last_login_at: datetime | None


class AuthMeResponse(BaseModel):
    authenticated: bool
    user: AuthUser | None = None


class LogoutResponse(BaseModel):
    ok: bool
