"""T10：调用观测 API 与提示词版本注册。"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import LlmCallRecord
from app.services.prompt_registry import PROMPT_VERSIONS, version_for


def _add_record(db_session, **overrides) -> LlmCallRecord:
    defaults = dict(
        service="scoring",
        model="glm-test",
        prompt_version="v1.0",
        status="success",
        attempts=1,
        latency_ms=800,
        experiment=False,
    )
    defaults.update(overrides)
    record = LlmCallRecord(**defaults)
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def test_record_llm_call_persists(db_session, monkeypatch):
    from tests.conftest import TestingSessionLocal

    monkeypatch.setattr("app.services.llm_observability._session_factory", TestingSessionLocal)
    from app.services.llm_observability import record_llm_call

    record_llm_call(
        service="question_generator",
        model="glm-real",
        prompt_version="v1.0",
        status="error",
        attempts=3,
        latency_ms=1500,
        error_type="HTTP429",
        error_message="限额",
    )
    rows = list(db_session.scalars(select(LlmCallRecord)))
    assert len(rows) == 1
    assert rows[0].service == "question_generator"
    assert rows[0].status == "error"
    assert rows[0].attempts == 3
    assert rows[0].error_type == "HTTP429"


def test_record_failure_never_raises(monkeypatch):
    class BrokenFactory:
        def __call__(self):
            raise RuntimeError("db down")

    monkeypatch.setattr("app.services.llm_observability._session_factory", BrokenFactory())
    from app.services.llm_observability import record_llm_call

    # 不应抛出异常：观测失败绝不影响业务调用
    record_llm_call(
        service="scoring", model="m", prompt_version="v1.0",
        status="success", attempts=1, latency_ms=10,
    )


def test_llm_calls_endpoint(api_client, db_session):
    _add_record(db_session, service="scoring", status="success", latency_ms=500)
    _add_record(db_session, service="follow_up", status="error", latency_ms=100,
                error_type="HTTP500", experiment=True)

    response = api_client.get("/api/v1/observability/llm-calls")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    services = {row["service"] for row in body}
    assert services == {"scoring", "follow_up"}
    error_row = next(row for row in body if row["status"] == "error")
    assert error_row["error_type"] == "HTTP500"
    assert error_row["experiment"] is True


def test_llm_stats_endpoint(api_client, db_session):
    _add_record(db_session, service="scoring", status="success", latency_ms=500)
    _add_record(db_session, service="scoring", status="error", latency_ms=1500)
    _add_record(db_session, service="follow_up", status="success", latency_ms=200)

    response = api_client.get("/api/v1/observability/llm-stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["errors"] == 1
    assert body["success_rate"] == round(2 / 3, 4)
    assert body["by_service"]["scoring"]["calls"] == 2
    assert body["by_service"]["scoring"]["errors"] == 1
    assert body["by_service"]["follow_up"]["avg_latency_ms"] == 200.0
    assert "glm-test" in body["by_model"]


def test_llm_stats_empty(api_client):
    response = api_client.get("/api/v1/observability/llm-stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["success_rate"] == 0.0


def test_prompt_versions_endpoint(api_client):
    response = api_client.get("/api/v1/observability/prompt-versions")
    assert response.status_code == 200
    body = response.json()
    assert body["versions"] == PROMPT_VERSIONS
    assert "scoring" in body["changelog"]


def test_version_for_unknown_service():
    assert version_for("nonexistent") == "unversioned"


def test_created_at_timezone_aware(db_session):
    record = _add_record(db_session)
    assert record.created_at is not None
    # SQLite 存储为 naive UTC，与当前 UTC 时间差应在 1 天内
    delta = datetime.now(timezone.utc).replace(tzinfo=None) - record.created_at
    assert delta.total_seconds() < 86400
