"""管理中心 API 测试：管理员权限边界、统计口径真实性、用户管理与审计。

核心原则断言：
- 非管理员 403、未登录 401，且角色只能来自数据库（无前端可绕过路径）；
- 所有统计数字与直接查询业务表的结果一致（无伪造数据）；
- 敏感操作（状态变更/导出）留审计痕。
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import get_db
from app.main import app
from app.models import AdminAuditLog, LlmCallRecord, UsageEvent, User, UserSession, utcnow
from app.services import auth_service

from .conftest import login_user, make_user

OVERVIEW = "/api/v1/admin/overview"
TRENDS = "/api/v1/admin/trends"
USERS = "/api/v1/admin/users"
MODULES = "/api/v1/admin/modules"
AI = "/api/v1/admin/ai"
AUDIT = "/api/v1/admin/audit"
EXPORT = "/api/v1/admin/export"


def make_admin(db_session, username: str = "chief", nickname: str = "管理员小观") -> User:
    user = make_user(db_session, username=username, nickname=nickname)
    user.role = "admin"
    db_session.commit()
    return user


@pytest.fixture()
def admin_client(db_session):
    """管理员客户端：注册 get_db 覆盖并在用例结束后还原。"""
    admin = make_admin(db_session)

    def override_get_db():
        yield db_session

    token = login_user(db_session, admin)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.cookies.set(auth_service.SESSION_COOKIE_NAME, token)
    yield client, admin
    app.dependency_overrides.pop(get_db, None)


def add_event(db_session, user_id: int | None, module: str, name: str, event_type: str = "action", status: str | None = "success", created_at: datetime | None = None):
    event = UsageEvent(
        user_id=user_id, event_type=event_type, module=module, name=name, status=status
    )
    if created_at is not None:
        event.created_at = created_at
    db_session.add(event)
    db_session.commit()
    return event


def add_llm_record(db_session, **kwargs) -> LlmCallRecord:
    record = LlmCallRecord(
        service=kwargs.get("service", "question_set"),
        model=kwargs.get("model", "test-model"),
        status=kwargs.get("status", "success"),
        attempts=1,
        latency_ms=kwargs.get("latency_ms", 100),
        error_type=kwargs.get("error_type"),
        error_message=kwargs.get("error_message"),
        usage=kwargs.get("usage"),
        user_id=kwargs.get("user_id"),
        created_at=kwargs.get("created_at"),
    )
    db_session.add(record)
    db_session.commit()
    return record


# ---------- 权限边界 ----------


def test_admin_endpoints_require_login(anon_client):
    assert anon_client.get(OVERVIEW).status_code == 401
    assert anon_client.get(USERS).status_code == 401
    assert anon_client.get(AI).status_code == 401
    assert anon_client.get(AUDIT).status_code == 401
    assert anon_client.get(EXPORT).status_code == 401


def test_admin_endpoints_forbidden_for_normal_user(api_client):
    assert api_client.get(OVERVIEW).status_code == 403
    assert api_client.get(USERS).status_code == 403
    assert api_client.get(MODULES).status_code == 403
    assert api_client.get(AI).status_code == 403
    assert api_client.get(AUDIT).status_code == 403
    assert api_client.get(EXPORT).status_code == 403
    # 状态变更同样拒绝
    assert api_client.post(f"{USERS}/1/status", json={"status": "disabled"}).status_code == 403


def test_admin_overview_accessible_for_admin(admin_client):
    client, _admin = admin_client
    resp = client.get(OVERVIEW)
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"].startswith("UTC+8")
    assert "definitions" in body
    assert body["users"]["total"] >= 1


def test_invalid_range_rejected(admin_client):
    client, _admin = admin_client
    resp = client.get(OVERVIEW, params={"start": "2026-13-99", "end": "2026-10-01"})
    assert resp.status_code == 400
    resp = client.get(OVERVIEW, params={"start": "2026-10-10", "end": "2026-10-01"})
    assert resp.status_code == 400


# ---------- 统计口径与真实数据 ----------


def test_overview_counts_match_real_records(db_session, admin_client):
    client, admin = admin_client
    other = make_user(db_session, username="alice", nickname="爱丽丝")
    # 事件：admin 1 次 page_view + 2 次 action；other 1 次 action（1 次失败）
    add_event(db_session, admin.id, "xingzhou", "dashboard", event_type="page_view")
    add_event(db_session, admin.id, "wenlan", "task_create")
    add_event(db_session, other.id, "wenlan", "task_create")
    add_event(db_session, other.id, "zhitu", "message_send", status="error")
    # AI：1 成功 + 1 失败，成功带真实 usage
    add_llm_record(db_session, user_id=admin.id, status="success", latency_ms=200, usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
    add_llm_record(db_session, user_id=other.id, status="error", latency_ms=0, error_type="HTTP500", error_message="upstream boom")

    body = client.get(OVERVIEW).json()

    assert body["users"]["total"] == 2
    assert body["users"]["new_in_range"] == 2
    assert body["users"]["active_in_range"] == 2
    assert body["pages"]["views_in_range"] == 1
    ai = body["ai"]
    assert ai["total"] == 2
    assert ai["success"] == 1
    assert ai["failed"] == 1
    assert ai["success_rate"] == 0.5
    assert ai["tokens_total"] == 150
    assert ai["avg_latency_ms"] == 200
    modules = {m["module"]: m for m in body["modules"]}
    assert modules["wenlan"]["actions"] == 2
    assert modules["zhitu"]["action_errors"] == 1
    assert modules["xingzhou"]["page_views"] == 1


def test_time_range_filters_all_stats(db_session, admin_client):
    client, admin = admin_client
    now = utcnow()
    # 窗口外（41 天前）的事件与用户不计入
    old = now - timedelta(days=41)
    add_event(db_session, admin.id, "wenlan", "task_create", created_at=old)
    # 窗口内的一条真实活动（保持活跃口径为 1）
    add_event(db_session, admin.id, "zhitu", "message_send")
    outsider = User(username="ancient", nickname="旧用户", password_hash="x", created_at=old)
    db_session.add(outsider)
    db_session.commit()

    body = client.get(OVERVIEW, params={"start": (now - timedelta(days=29)).date().isoformat(), "end": now.date().isoformat()}).json()
    assert body["users"]["new_in_range"] == 1  # 只有 admin 本人
    assert body["users"]["active_in_range"] == 1
    modules = {m["module"]: m for m in body["modules"]}
    assert modules["wenlan"]["actions"] == 0


def test_trends_bucket_by_utc8_day(db_session, admin_client):
    client, admin = admin_client
    # 20:00 UTC 落在次日（UTC+8）
    late_evening = datetime(2026, 10, 10, 20, 0, 0)
    add_event(db_session, admin.id, "wenlan", "task_create", created_at=late_evening)

    body = client.get(TRENDS, params={"start": "2026-10-10", "end": "2026-10-12"}).json()
    assert "2026-10-10" in body["days"]
    assert body["series"]["module_usage"]["wenlan"]["2026-10-11"] == 1
    assert body["series"]["module_usage"]["wenlan"]["2026-10-10"] == 0


def test_users_list_pagination_search_and_filters(db_session, admin_client):
    client, _admin = admin_client
    for i in range(15):
        user = make_user(db_session, username=f"batch_{i:02d}", nickname=f"同学{i}")
        if i < 3:
            for _ in range(i + 1):
                add_event(db_session, user.id, "wenlan", "task_create")

    # 分页
    page1 = client.get(USERS, params={"page": 1, "page_size": 10, "sort": "created_at"}).json()
    assert page1["total"] == 16
    assert len(page1["items"]) == 10
    page2 = client.get(USERS, params={"page": 2, "page_size": 10, "sort": "created_at"}).json()
    assert len(page2["items"]) == 6
    # 搜索
    searched = client.get(USERS, params={"q": "batch_07"}).json()
    assert searched["total"] == 1
    assert searched["items"][0]["username"] == "batch_07"
    # 状态筛选
    assert client.get(USERS, params={"status": "active"}).json()["total"] == 16
    # 按使用次数排序：batch_02 事件最多（3 次）
    by_usage = client.get(USERS, params={"sort": "usage", "page_size": 5}).json()
    assert by_usage["items"][0]["usage_count"] == 3


def test_user_detail_aggregates_real_data(db_session, admin_client):
    client, admin = admin_client
    other = make_user(db_session, username="bob", nickname="波波")
    add_event(db_session, other.id, "wenlan", "task_create")
    add_event(db_session, other.id, "wenlan", "task_create")
    add_llm_record(db_session, user_id=other.id, status="success", latency_ms=300, usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

    body = client.get(f"{USERS}/{other.id}").json()
    assert body["user"]["username"] == "bob"
    modules = {m["module"]: m for m in body["modules_in_range"]}
    assert modules["wenlan"]["actions"] == 2
    assert body["ai_in_range"]["total"] == 1
    assert body["ai_in_range"]["avg_latency_ms"] == 300
    assert body["ai_all_time"]["tokens_total"] == 15
    # 不泄露密码摘要等敏感字段
    assert "password_hash" not in body["user"]

    assert client.get(f"{USERS}/9999").status_code == 404


# ---------- AI 统计 ----------


def test_ai_stats_percentiles_errors_and_models(db_session, admin_client):
    client, admin = admin_client
    for latency in (100, 200, 300, 400, 500):
        add_llm_record(db_session, user_id=admin.id, status="success", latency_ms=latency)
    add_llm_record(db_session, status="error", latency_ms=0, error_type="ReadTimeout", error_message="Bearer abc123 timed out", service="scoring")
    add_llm_record(db_session, status="error", latency_ms=0, error_type="HTTP429", model="another-model", service="career_guide")

    body = client.get(AI).json()
    totals = body["totals"]
    assert totals["total"] == 7
    assert totals["success"] == 5
    assert totals["success_rate"] == round(5 / 7, 4)
    assert totals["p50_ms"] == 300
    assert totals["p95_ms"] == 500
    assert totals["timeouts"] == 1
    # 服务归属
    by_service = {s["service"]: s for s in body["by_service"]}
    assert by_service["question_set"]["total"] == 5
    assert by_service["career_guide"]["module_label"] == "知途规划"
    # 错误分类与脱敏
    categories = {c["category"]: c["count"] for c in body["error_categories"]}
    assert categories["请求超时"] == 1
    assert categories["调用限额（429）"] == 1
    recent = body["recent_errors"]
    assert all("Bearer abc123" not in (e["message"] or "") for e in recent)
    assert any("[已脱敏]" in (e["message"] or "") for e in recent)
    # 模型维度
    models = {m["model"]: m for m in body["by_model"]}
    assert models["test-model"]["total"] == 6
    assert models["another-model"]["total"] == 1


# ---------- 用户管理操作与审计 ----------


def test_status_change_revokes_sessions_and_audits(db_session, admin_client):
    client, admin = admin_client
    target = make_user(db_session, username="naughty", nickname="调皮用户")
    token = login_user(db_session, target)

    resp = client.post(f"{USERS}/{target.id}/status", json={"status": "disabled"})
    assert resp.status_code == 200
    assert resp.json()["changed"] is True

    # 会话被真实撤销：旧令牌不再可用
    probe = TestClient(app)
    probe.cookies.set(auth_service.SESSION_COOKIE_NAME, token)
    assert probe.get("/api/v1/auth/me").json()["authenticated"] is False

    # 审计留痕
    logs = db_session.scalars(select(AdminAuditLog)).all()
    assert any(log.action == "user_status_update" and log.target_id == str(target.id) for log in logs)


def test_cannot_change_own_status(admin_client):
    client, admin = admin_client
    resp = client.post(f"{USERS}/{admin.id}/status", json={"status": "disabled"})
    assert resp.status_code == 400


def test_status_change_requires_valid_body(db_session, admin_client):
    client, _admin = admin_client
    target = make_user(db_session, username="target2", nickname="目标")
    assert client.post(f"{USERS}/{target.id}/status", json={"status": "hacked"}).status_code == 422


def test_export_csv_audited(db_session, admin_client):
    client, admin = admin_client
    make_user(db_session, username="csv_user", nickname="表格用户")
    add_event(db_session, admin.id, "wenlan", "task_create")

    resp = client.get(EXPORT, params={"kind": "users"})
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    text = resp.content.decode("utf-8-sig")
    assert "csv_user" in text
    assert "password" not in text.lower()

    resp = client.get(EXPORT, params={"kind": "overview"})
    assert resp.status_code == 200
    resp = client.get(EXPORT, params={"kind": "ai"})
    assert resp.status_code == 200
    resp = client.get(EXPORT, params={"kind": "secret"})
    assert resp.status_code == 400

    logs = db_session.scalars(select(AdminAuditLog)).all()
    export_logs = [log for log in logs if log.action == "export_stats"]
    assert len(export_logs) == 3


def test_audit_list_only_for_admin_and_paginated(db_session, admin_client):
    client, admin = admin_client
    target = make_user(db_session, username="audited", nickname="被审计")
    for _ in range(3):
        client.post(f"{USERS}/{target.id}/status", json={"status": "active"})  # 无变化也留痕？——无变化不写日志
    # 制造真实变更
    client.post(f"{USERS}/{target.id}/status", json={"status": "disabled"})
    client.post(f"{USERS}/{target.id}/status", json={"status": "active"})

    body = client.get(AUDIT).json()
    assert body["total"] == 2
    assert all(entry["action"] == "user_status_update" for entry in body["items"])


# ---------- 事件采集 ----------


def test_register_and_login_record_usage_events(db_session, anon_client):
    resp = anon_client.post(
        "/api/v1/auth/register",
        json={"username": "event_user", "password": "quiet-lake7", "nickname": "事件用户"},
    )
    assert resp.status_code == 201
    anon_client.post(
        "/api/v1/auth/login",
        json={"username": "event_user", "password": "quiet-lake7"},
    )

    events = db_session.scalars(select(UsageEvent).where(UsageEvent.module == "auth")).all()
    names = {event.name for event in events}
    assert "register" in names
    assert "login" in names
    user = db_session.scalar(select(User).where(User.username == "event_user"))
    registered = [e for e in events if e.name == "register"]
    assert registered[0].user_id == user.id


def test_page_view_deduped_within_window(admin_client):
    client, _admin = admin_client
    payload = {"module": "xingzhou", "name": "dashboard"}
    first = client.post("/api/v1/usage/page-view", json=payload)
    assert first.json()["recorded"] is True
    second = client.post("/api/v1/usage/page-view", json=payload)
    assert second.json()["recorded"] is False

    unknown = client.post("/api/v1/usage/page-view", json={"module": "hacker", "name": "x"})
    assert unknown.status_code == 422
