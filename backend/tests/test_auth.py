"""认证 API 集成测试：用户名密码注册/登录、会话与越权。

数据库为进程内内存库；密码只以 PBKDF2 摘要落库，任何用例都不落明文。
"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import User
from app.services import auth_service

from .conftest import (
    VALID_TASK,
    login_user,
    make_user,
    question_generation_response,
    use_fake_client,
)

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


def _session_cookie(response) -> str:
    """从 Set-Cookie 响应头中提取会话令牌明文（仅测试断言用）。"""
    set_cookie = response.headers.get("set-cookie", "")
    assert "aurel_session=" in set_cookie
    return set_cookie.split("aurel_session=")[1].split(";")[0]


def _client_with_token(token: str) -> TestClient:
    """携带指定会话令牌的独立客户端（用于重放/登出验证）。"""
    client = TestClient(app)
    client.cookies.set(auth_service.SESSION_COOKIE_NAME, token)
    return client


# ---------- 注册流程 ----------


def test_register_creates_account_and_sets_httponly_cookie(anon_client, db_session):
    payload = {"username": "newbie", "password": "still-water5", "nickname": "新用户"}
    resp = anon_client.post(REGISTER, json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["authenticated"] is True
    assert body["user"]["username"] == "newbie"
    assert body["user"]["nickname"] == "新用户"
    assert "password" not in body["user"]

    cookie_header = resp.headers.get("set-cookie", "").lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "path=/" in cookie_header

    # httpx 自动携带会话 Cookie，/me 应识别登录态
    me = anon_client.get(ME).json()
    assert me["authenticated"] is True
    assert me["user"]["username"] == "newbie"

    # 库内只存 PBKDF2 摘要，绝不存明文
    user = db_session.scalar(select(User).where(User.username == "newbie"))
    assert user.password_hash.startswith("pbkdf2_sha256$")
    assert payload["password"] not in user.password_hash


def test_register_rejects_duplicate_username(anon_client, db_session):
    make_user(db_session, username="taken", nickname="先来者")

    resp = anon_client.post(
        REGISTER, json={"username": "Taken", "password": "evening-tide9", "nickname": "后来者"}
    )
    assert resp.status_code == 400
    assert "已被使用" in resp.json()["detail"]


def test_register_rejects_bad_username(anon_client):
    for username in ("ab", "含 空格", "x" * 25, "bad!name"):
        resp = anon_client.post(
            REGISTER, json={"username": username, "password": "evening-tide9", "nickname": "名字"}
        )
        assert resp.status_code == 422, username


def test_register_rejects_weak_password(anon_client):
    weak = ["short1", "nodigitpassword", "12345678", "x" * 65 + "1"]
    for password in weak:
        resp = anon_client.post(
            REGISTER, json={"username": "weakpw", "password": password, "nickname": "弱密码"}
        )
        assert resp.status_code == 422, password


def test_register_rejects_bad_nickname(anon_client):
    resp = anon_client.post(
        REGISTER, json={"username": "nickcheck", "password": "evening-tide9", "nickname": "名"}
    )
    assert resp.status_code == 422


# ---------- 登录流程 ----------


def test_login_flow_updates_last_login(anon_client, db_session):
    user = make_user(db_session, username="oldcomer", nickname="老用户")
    assert user.last_login_at is None

    resp = anon_client.post(
        LOGIN, json={"username": "oldcomer", "password": "harbor-light8"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert body["user"]["username"] == "oldcomer"

    db_session.refresh(user)
    assert user.last_login_at is not None


def test_login_rejects_wrong_password(anon_client, db_session):
    make_user(db_session, username="wrongpw", nickname="口令不对")

    resp = anon_client.post(LOGIN, json={"username": "wrongpw", "password": "not-the-one1"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "用户名或密码不匹配，请核对后再试"


def test_login_unknown_user_same_error_as_wrong_password(anon_client):
    """防用户名枚举：不存在账户与密码错误的提示必须一致。"""
    ghost = anon_client.post(LOGIN, json={"username": "ghost", "password": "no-such-one1"})
    known = anon_client.post(LOGIN, json={"username": "wrongpw", "password": "not-the-one1"})

    assert ghost.status_code == 401
    assert ghost.json()["detail"] == known.json()["detail"]


def test_login_disabled_account_403(anon_client, db_session):
    user = make_user(db_session, username="paused", nickname="暂停中")
    user.status = "disabled"
    db_session.commit()

    resp = anon_client.post(LOGIN, json={"username": "paused", "password": "harbor-light8"})
    assert resp.status_code == 403
    assert "不可用" in resp.json()["detail"]


# ---------- 会话与访问控制 ----------


def test_me_reports_login_state(anon_client, api_client):
    anon = anon_client.get(ME).json()
    assert anon["authenticated"] is False
    assert anon["user"] is None

    me = api_client.get(ME).json()
    assert me["authenticated"] is True
    assert me["user"]["username"] == "tester"
    assert me["user"]["nickname"] == "测试用户"


def test_logout_revokes_session_server_side(anon_client):
    resp = anon_client.post(
        REGISTER, json={"username": "farewell", "password": "evening-tide9", "nickname": "登出者"}
    )
    token = _session_cookie(resp)

    session_client = _client_with_token(token)
    assert session_client.get("/api/v1/interviews").status_code == 200

    assert session_client.post(LOGOUT).status_code == 200

    # 旧令牌重放：服务端已真实撤销
    replay = _client_with_token(token)
    assert replay.get("/api/v1/interviews").status_code == 401
    assert replay.get(ME).json()["authenticated"] is False


def test_protected_endpoints_require_login(anon_client):
    resp = anon_client.get("/api/v1/interviews")
    assert resp.status_code == 401
    assert "请先登录" in resp.json()["detail"]


def test_bearer_machine_channel_does_not_access_user_data(api_client, monkeypatch):
    monkeypatch.setenv("AUREL_ACCESS_TOKEN", "machine-token")
    headers = {"Authorization": "Bearer machine-token"}

    assert api_client.get("/api/v1/health", headers=headers).status_code == 200

    resp = api_client.get("/api/v1/interviews", headers=headers)
    assert resp.status_code == 401
    assert "运维令牌" in resp.json()["detail"]

    bad = api_client.get("/api/v1/interviews", headers={"Authorization": "Bearer wrong"})
    assert bad.status_code == 401
    assert "访问令牌无效" in bad.json()["detail"]


def test_cross_site_write_request_rejected(anon_client):
    resp = anon_client.post(
        REGISTER,
        json={"username": "csrf", "password": "evening-tide9", "nickname": "跨站"},
        headers={"Origin": "https://evil.example"},
    )
    assert resp.status_code == 403

    trusted = anon_client.post(
        REGISTER,
        json={"username": "csrf2", "password": "evening-tide9", "nickname": "同源"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert trusted.status_code == 201


def test_cross_user_data_isolation(api_client, db_session):
    """用户无法访问/看到其他用户的业务数据。"""
    use_fake_client([question_generation_response(3)])
    created = api_client.post("/api/v1/interviews", json=VALID_TASK)
    assert created.status_code == 201
    task_id = created.json()["id"]

    other = make_user(db_session, username="islander", nickname="乙用户")
    other_client = _client_with_token(login_user(db_session, other))

    assert other_client.get(f"/api/v1/interviews/{task_id}").status_code == 404

    visible_ids = [item["id"] for item in other_client.get("/api/v1/interviews").json()]
    assert task_id not in visible_ids

    owner_ids = [item["id"] for item in api_client.get("/api/v1/interviews").json()]
    assert task_id in owner_ids
