from fastapi.testclient import TestClient

from app.config import SERVICE_NAME, VERSION
from app.main import app


def make_client() -> TestClient:
    return TestClient(app)


def test_health_returns_200_with_expected_fields() -> None:
    with make_client() as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"status", "service", "version"}
    assert data["status"] == "ok"
    assert data["service"] == SERVICE_NAME
    assert data["version"] == VERSION


def test_unknown_api_path_returns_404(api_client) -> None:
    # 未登录访问未知路径会被访问控制中间件以 401 拦截，这里验证登录后的 404 语义
    response = api_client.get("/api/v1/definitely-not-a-real-path")
    assert response.status_code == 404


def test_unknown_root_path_returns_404(api_client) -> None:
    response = api_client.get("/no-such-page")
    assert response.status_code == 404
