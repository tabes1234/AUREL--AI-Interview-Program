"""pytest 共享 fixtures：内存数据库 + 可编程的假方舟客户端 + 会话认证注入。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import SessionLocal, get_db
from app.main import app
from app.models import User
from app.models_base import Base
from app.routers.interviews import get_ark_client
from app.services import auth_service
from app.services.password_service import hash_password

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)

DEFAULT_USER_USERNAME = "tester"
DEFAULT_USER_NICKNAME = "测试用户"
DEFAULT_USER_PASSWORD = "harbor-light8"


class FakeArkClient:
    """按预设队列返回 JSON 的假客户端，不发起真实网络请求。"""

    def __init__(self, responses: list[dict] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[tuple[str, str]] = []
        self.model = "fake-model-test"

    def ensure_configured(self) -> None:
        return

    def chat_json(self, system: str, user: str, *, temperature: float = 0.3,
                  service: str = "unattributed") -> dict:
        self.ensure_configured()
        self.calls.append((system, user))
        if not self.responses:
            raise AssertionError("FakeArkClient 没有更多预设响应")
        return self.responses.pop(0)


class NotConfiguredArkClient(FakeArkClient):
    """模拟未配置 API Key 的客户端。"""

    def __init__(self) -> None:
        super().__init__()
        self.model = ""

    def ensure_configured(self) -> None:
        from app.services.ark_client import ArkNotConfiguredError

        raise ArkNotConfiguredError(
            "AI 模型尚未配置：缺少环境变量 ARK_API_KEY。请在 backend/.env 中配置后重启后端服务。"
        )


@pytest.fixture(autouse=True)
def _fresh_rate_limit_window():
    """每个用例开始/结束时清空限流窗口，避免用例间请求计数互相污染。"""
    from app.middleware import reset_rate_limits

    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    """将会话查询指向测试内存库；结束后还原为真实库工厂。"""
    auth_service.set_session_factory(TestingSessionLocal)
    yield
    auth_service.set_session_factory(SessionLocal)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(TEST_ENGINE)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(TEST_ENGINE)


def make_user(
    db_session,
    username: str = DEFAULT_USER_USERNAME,
    nickname: str = DEFAULT_USER_NICKNAME,
    password: str = DEFAULT_USER_PASSWORD,
) -> User:
    """创建（或按用户名复用）测试用户，密码以 PBKDF2 摘要落库。"""
    existing = db_session.scalar(select(User).where(User.username == username))
    if existing is not None:
        return existing
    user = User(username=username, nickname=nickname, password_hash=hash_password(password))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login_user(db_session, user: User) -> str:
    """为用户创建服务端会话，返回明文令牌（仅测试使用）。"""
    token, _ = auth_service.create_session(db_session, user.id)
    return token


@pytest.fixture()
def api_client(db_session):
    """默认登录用户（tester@qq.com）的客户端：自带 HttpOnly 会话 Cookie。"""
    def override_get_db():
        yield db_session

    user = make_user(db_session)
    token = login_user(db_session, user)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        # 注意：httpx 0.28 下 set 需不带 domain，Cookie 才会随请求发送
        client.cookies.set(auth_service.SESSION_COOKIE_NAME, token)
        yield client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_ark_client, None)


@pytest.fixture()
def anon_client(db_session):
    """未登录客户端：用于认证接口与"未登录访问受保护端点"的用例。"""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_ark_client, None)


def use_fake_client(responses: list[dict]) -> FakeArkClient:
    fake = FakeArkClient(responses)
    app.dependency_overrides[get_ark_client] = lambda: fake
    return fake


VALID_TASK = {
    "position": "前端工程师",
    "description": "负责 Web 前端开发",
    "difficulty": "intermediate",
    "language": "zh",
    "question_count": 3,
}


def question_generation_response(count: int = 3) -> dict:
    return {"questions": [f"问题{i}：请谈谈你的理解" for i in range(1, count + 1)]}


NO_FOLLOW_UP = {"need_follow_up": False, "follow_up": None, "reason": "回答充分"}


def follow_up_response() -> dict:
    return {
        "need_follow_up": True,
        "follow_up": "追问：能举一个具体项目中的例子吗？",
        "reason": "回答过浅",
    }


VALID_SCORING = {
    "summary": "整体回答结构清晰，但专业深度有待加强。",
    "dimensions": [
        {"name": "内容深度", "score": 6.0, "evidence": "我用了 React", "rationale": "仅提及使用，未展开原理"},
        {"name": "表达清晰", "score": 8.0, "evidence": "首先…其次…最后", "rationale": "有明确的结构化表达"},
        {"name": "逻辑结构", "score": 7.0, "evidence": "先说了背景再给结论", "rationale": "推理链条基本完整"},
        {"name": "岗位匹配", "score": 6.0, "evidence": "做过管理后台", "rationale": "经验与目标岗位部分重合"},
    ],
    "strengths": ["表达有条理", "态度认真"],
    "improvements": [
        {"title": "深挖技术原理", "detail": "对使用过的技术补充原理层面的理解"},
    ],
}
