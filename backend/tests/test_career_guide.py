"""知途（AI 职业顾问「小鸥」）对话功能的回归测试。

外部 AI 一律使用假客户端，绝不发起真实网络请求。
"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import CareerMessage
from app.routers.interviews import get_ark_client
from app.services.auth_service import SESSION_COOKIE_NAME
from tests.conftest import login_user, make_user


class FakeChatClient:
    """按预设队列返回纯文本回复的假客户端（知途走 chat 而非 chat_json）。"""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []
        self.model = "fake-model-test"

    def chat(self, system: str, user: str, *, temperature: float = 0.7,
             service: str = "unattributed") -> str:
        self.calls.append((system, user))
        if not self.replies:
            raise AssertionError("FakeChatClient 没有更多预设回复")
        return self.replies.pop(0)


class NotConfiguredChatClient(FakeChatClient):
    def __init__(self) -> None:
        super().__init__([])
        self.model = ""

    def chat(self, system: str, user: str, *, temperature: float = 0.7,
             service: str = "unattributed") -> str:
        from app.services.ark_client import ArkNotConfiguredError

        raise ArkNotConfiguredError(
            "AI 模型尚未配置：缺少环境变量 ARK_API_KEY。请在 backend/.env 中配置后重启后端服务。"
        )


def use_chat_client(replies: list[str]) -> FakeChatClient:
    fake = FakeChatClient(replies)
    app.dependency_overrides[get_ark_client] = lambda: fake
    return fake


def test_create_and_list_conversations(api_client):
    resp = api_client.post("/api/v1/career-guide/conversations", json=None)
    assert resp.status_code == 201
    first = resp.json()
    assert first["title"] == "新的旅程"
    assert first["message_count"] == 0

    resp = api_client.post(
        "/api/v1/career-guide/conversations", json={"title": "  转向产品岗  "}
    )
    assert resp.status_code == 201
    second = resp.json()
    assert second["title"] == "转向产品岗"  # 标题被规范化（去首尾空白）

    resp = api_client.get("/api/v1/career-guide/conversations")
    assert resp.status_code == 200
    items = resp.json()
    assert [item["id"] for item in items] == [second["id"], first["id"]]


def test_send_message_persists_pair_and_autotitle(api_client, db_session):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    fake = use_chat_client(["先把目标岗位拆成三项核心能力，再逐项对齐。"])

    resp = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/messages",
        json={"content": "  我想从测试转产品经理，该怎么开始？  "},
    )
    assert resp.status_code == 200
    pair = resp.json()
    assert pair["user_message"]["role"] == "user"
    assert pair["user_message"]["content"] == "我想从测试转产品经理，该怎么开始？"
    assert pair["assistant_message"]["role"] == "assistant"
    assert pair["assistant_message"]["content"].startswith("先把目标岗位")
    assert pair["model_name"] == "fake-model-test"

    # 内容已真实落库
    stored = list(
        db_session.scalars(
            select(CareerMessage).where(
                CareerMessage.conversation_id == created["id"]
            )
        )
    )
    assert len(stored) == 2

    # 详情返回完整消息流，默认标题被首条消息替换
    detail = api_client.get(
        f"/api/v1/career-guide/conversations/{created['id']}"
    ).json()
    assert detail["message_count"] == 2
    assert detail["title"].startswith("我想从测试转产品经理")
    assert [m["id"] for m in detail["messages"]] == sorted(
        m["id"] for m in detail["messages"]
    )

    # 提示词走小鸥人设，上下文包含用户新消息
    system, user = fake.calls[0]
    assert "小鸥" in system
    assert "我想从测试转产品经理" in user


def test_blank_message_rejected(api_client):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    use_chat_client(["不该被调用"])
    resp = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/messages",
        json={"content": "   "},
    )
    assert resp.status_code == 422


def test_conversation_isolated_between_users(api_client, db_session):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()

    other = make_user(db_session, username="guide-other", nickname="其他用户")
    other_token = login_user(db_session, other)
    other_client = TestClient(app)
    other_client.cookies.set(SESSION_COOKIE_NAME, other_token)

    # 他人列表看不到、详情 404
    listed = other_client.get("/api/v1/career-guide/conversations")
    assert listed.status_code == 200
    assert listed.json() == []
    resp = other_client.get(f"/api/v1/career-guide/conversations/{created['id']}")
    assert resp.status_code == 404


def test_delete_conversation(api_client):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    resp = api_client.delete(f"/api/v1/career-guide/conversations/{created['id']}")
    assert resp.status_code == 204
    resp = api_client.get(f"/api/v1/career-guide/conversations/{created['id']}")
    assert resp.status_code == 404


def test_send_message_without_ai_configured_persists_nothing(api_client, db_session):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    app.dependency_overrides[get_ark_client] = lambda: NotConfiguredChatClient()

    resp = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/messages",
        json={"content": "帮帮我"},
    )
    assert resp.status_code == 503

    detail = api_client.get(
        f"/api/v1/career-guide/conversations/{created['id']}"
    ).json()
    assert detail["message_count"] == 0  # AI 失败时用户消息同样不落库
