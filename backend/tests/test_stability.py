"""T8/T10：Ark 客户端重试与实验分流、SSE 流式复盘、工作流事件序列。"""

import httpx
import pytest

from app.services import ark_client as ark_module
from app.services.expression_workflow import iter_expression_workflow
from tests.conftest import use_fake_client


def _ok_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 42}},
    )


@pytest.fixture()
def observability_to_test_db(monkeypatch):
    from tests.conftest import TestingSessionLocal

    monkeypatch.setattr("app.services.llm_observability._session_factory", TestingSessionLocal)


def test_chat_retries_on_5xx_then_succeeds(db_session, monkeypatch, observability_to_test_db):
    monkeypatch.setattr(ark_module.time, "sleep", lambda seconds: None)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, content=b"unavailable")
        return _ok_response("你好")

    monkeypatch.setattr("app.services.ark_client._post", fake_post)
    client = ark_module.ArkClient(api_key="key", model="m")
    assert client.chat("sys", "user", service="scoring") == "你好"

    # 观测记录：重试成功计 2 次尝试
    from sqlalchemy import select

    from app.models import LlmCallRecord

    rows = list(db_session.scalars(select(LlmCallRecord)))
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].attempts == 2
    assert rows[0].service == "scoring"
    assert rows[0].prompt_version == "v1.0"
    assert rows[0].usage == {"total_tokens": 42}


def test_chat_gives_up_after_retries(db_session, monkeypatch, observability_to_test_db):
    monkeypatch.setattr(ark_module.time, "sleep", lambda seconds: None)

    def fake_post(*args, **kwargs):
        return httpx.Response(500, content=b"boom")

    monkeypatch.setattr("app.services.ark_client._post", fake_post)
    client = ark_module.ArkClient(api_key="key", model="m")
    with pytest.raises(ark_module.ArkError, match="HTTP 500"):
        client.chat("sys", "user")

    from sqlalchemy import select

    from app.models import LlmCallRecord

    rows = list(db_session.scalars(select(LlmCallRecord)))
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].attempts == 3  # 首次 + 2 次重试
    assert rows[0].error_type == "HTTP500"


def test_chat_honors_retry_after_on_429(db_session, monkeypatch, observability_to_test_db):
    sleeps: list[float] = []
    monkeypatch.setattr(ark_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    def fake_post(*args, **kwargs):
        if len(sleeps) == 0:
            return httpx.Response(429, content=b"limit", headers={"Retry-After": "2"})
        return _ok_response("ok")

    monkeypatch.setattr("app.services.ark_client._post", fake_post)
    client = ark_module.ArkClient(api_key="key", model="m")
    assert client.chat("sys", "user") == "ok"
    assert sleeps == [2.0]


def test_chat_timeout_maps_to_readable_error(db_session, monkeypatch, observability_to_test_db):
    def fake_post(*args, **kwargs):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr("app.services.ark_client._post", fake_post)
    monkeypatch.setattr(ark_module.time, "sleep", lambda seconds: None)
    client = ark_module.ArkClient(api_key="key", model="m")
    with pytest.raises(ark_module.ArkError, match="超时"):
        client.chat("sys", "user")


def test_experiment_routing(db_session, monkeypatch, observability_to_test_db):
    monkeypatch.setenv("LLM_EXPERIMENT_MODEL", "candidate-model")
    monkeypatch.setenv("LLM_EXPERIMENT_PERCENT", "100")
    seen_models: list[str] = []

    def fake_post(url, headers=None, json=None, timeout=None):
        seen_models.append(json["model"])
        return _ok_response("ok")

    monkeypatch.setattr("app.services.ark_client._post", fake_post)
    monkeypatch.setattr(ark_module.time, "sleep", lambda seconds: None)
    client = ark_module.ArkClient(api_key="key", model="baseline-model")
    client.chat("sys", "user")
    assert seen_models == ["candidate-model"]

    from sqlalchemy import select

    from app.models import LlmCallRecord
    from tests.conftest import TestingSessionLocal

    session = TestingSessionLocal()
    try:
        row = session.scalars(select(LlmCallRecord)).first()
        assert row is not None
        assert row.experiment is True
        assert row.model == "candidate-model"
    finally:
        session.close()


def _workflow_responses() -> list[dict]:
    structure = {
        "logic_score": 7.0,
        "structure_summary": "总分总结构",
        "discourse_markers": ["首先"],
        "issues": [],
    }
    depth = {
        "depth_score": 6.0,
        "concrete_examples": ["例子"],
        "missing_substance": [],
        "issues": [],
    }
    coach = {
        "overall_assessment": "整体不错",
        "priority_fixes": [{"title": "补充数据", "detail": "加入量化结果"}],
        "drill_suggestions": ["每天录音 2 分钟"],
    }
    return [structure, depth, coach]


def test_workflow_generator_event_sequence():
    from tests.conftest import FakeArkClient

    fake = FakeArkClient(_workflow_responses())
    kinds = []
    final = None
    for kind, payload in iter_expression_workflow("这是一段足够长的回答文本。", client=fake):
        kinds.append(kind)
        if kind == "done":
            final = payload
    assert kinds == [
        "step_started", "step_finished",
        "step_started", "step_finished",
        "step_started", "step_finished",
        "done",
    ]
    assert final["status"] == "completed"
    assert len(final["steps"]) == 3
    assert final["model_name"] == "fake-model-test"


def test_analyze_stream_endpoint(api_client):
    use_fake_client(_workflow_responses())
    response = api_client.post(
        "/api/v1/expression/analyze/stream",
        json={"text": "这是一个用于流式复盘测试的足够长的回答文本，包含具体的项目背景与结果。"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: step_started" in body
    assert "event: step_finished" in body
    assert "event: result" in body

    # 解析最后的 result 事件
    result_line = [line for line in body.split("\n") if line.startswith("data: ")][-1]
    import json

    result = json.loads(result_line.removeprefix("data: "))
    assert result["workflow"]["status"] == "completed"
    assert result["id"] > 0


def test_analyze_stream_validation_errors(api_client):
    # text 与 analysis_id 同时缺失 → 400（流开始前即报错）
    assert api_client.post("/api/v1/expression/analyze/stream", json={}).status_code == 400
    # 引用不存在的记录 → 404
    assert (
        api_client.post("/api/v1/expression/analyze/stream", json={"analysis_id": 99999}).status_code
        == 404
    )


def test_scoring_still_works_with_service_kwarg(api_client):
    """回归：面试创建链路在 Fake 客户端 + service 参数下行为不变。"""
    from tests.conftest import VALID_TASK, question_generation_response

    use_fake_client([question_generation_response(3)])
    response = api_client.post("/api/v1/interviews", json=VALID_TASK)
    assert response.status_code == 201
    assert len(response.json()["questions"]) == 3
