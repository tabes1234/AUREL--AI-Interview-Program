"""T7/T8：访问控制、限流、日志脱敏、就绪检查与隐私端点。"""

import logging

from fastapi.testclient import TestClient

from app.logging_setup import SecretRedactionFilter
from app.main import app
from app.middleware import reset_rate_limits

PROTECTED_PATH = "/api/v1/expression/records"


def test_access_disabled_by_default(api_client):
    """默认（未配置 AUREL_ACCESS_TOKEN）登录用户经会话 Cookie 正常访问。"""
    response = api_client.get(PROTECTED_PATH)
    assert response.status_code == 200


def test_access_token_enforced(anon_client, monkeypatch):
    monkeypatch.setenv("AUREL_ACCESS_TOKEN", "secret-token-123")
    # 无令牌无会话 → 401
    assert anon_client.get(PROTECTED_PATH).status_code == 401
    # 错误令牌 → 401
    assert (
        anon_client.get(PROTECTED_PATH, headers={"Authorization": "Bearer wrong"})
        .status_code
        == 401
    )
    # 正确 Bearer 属于运维机器通道：可通过网关但不绑定个人数据，业务接口仍要求登录
    machine = anon_client.get(PROTECTED_PATH, headers={"Authorization": "Bearer secret-token-123"})
    assert machine.status_code == 401
    assert "运维令牌" in machine.json()["detail"]
    # 免鉴权端点保持开放
    assert anon_client.get("/api/v1/health").status_code == 200
    assert anon_client.get("/api/v1/ai/status").status_code == 200


def test_rate_limit_429_with_retry_after(api_client, monkeypatch):
    monkeypatch.setenv("AUREL_RATE_LIMIT_PER_MINUTE", "2")
    reset_rate_limits()
    try:
        assert api_client.get(PROTECTED_PATH).status_code == 200
        assert api_client.get(PROTECTED_PATH).status_code == 200
        limited = api_client.get(PROTECTED_PATH)
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers
        assert "频繁" in limited.json()["detail"]
        # 免限流端点不受影响
        assert api_client.get("/api/v1/health").status_code == 200
    finally:
        reset_rate_limits()


def test_rate_limit_disabled_with_zero(api_client, monkeypatch):
    monkeypatch.setenv("AUREL_RATE_LIMIT_PER_MINUTE", "0")
    reset_rate_limits()
    for _ in range(5):
        assert api_client.get(PROTECTED_PATH).status_code == 200


def test_readiness_check(api_client):
    response = api_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


def test_privacy_endpoint(api_client):
    response = api_client.get("/api/v1/privacy")
    assert response.status_code == 200
    body = response.json()
    assert body["audio"]["storage"] == "memory_only"
    assert "DELETE /api/v1/expression/records/{id}" in body["deletion_endpoints"]


def test_secret_redaction_filter():
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="调用失败：Authorization: Bearer sk-abcdef123456 api_key=sk-xyz789",
        args=(), exc_info=None,
    )
    SecretRedactionFilter().filter(record)
    message = record.getMessage()
    assert "sk-abcdef123456" not in message
    assert "sk-xyz789" not in message
    assert "Bearer ***" in message
    assert "调用失败" in message
