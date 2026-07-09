from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from respx import MockRouter


def test_health_endpoint(client: TestClient) -> None:
    """Test that the basic /health endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("redis.Redis.from_url")
@patch("src.analytics.db.async_engine")
def test_ready_endpoint_healthy(
    mock_engine: MagicMock,
    mock_redis_from_url: MagicMock,
    client: TestClient,
    respx_mock: MockRouter,
) -> None:
    """Test that /ready returns 200 when all dependencies are healthy."""
    # Mock Redis ping to succeed
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_from_url.return_value = mock_redis

    # Mock DB connection context manager
    mock_conn = MagicMock()
    mock_conn.__aenter__.return_value = mock_conn
    mock_engine.connect.return_value = mock_conn

    # Mock Qdrant HTTP health check
    respx_mock.get("http://localhost:6333/healthz").mock(
        return_value=httpx.Response(200, json={"title": "qdrant"})
    )

    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["redis"] == "ok"
    assert data["qdrant"] == "ok"
    assert data["database"] == "ok"


@patch("redis.Redis.from_url")
@patch("src.analytics.db.async_engine")
def test_ready_endpoint_redis_down(
    mock_engine: MagicMock,
    mock_redis_from_url: MagicMock,
    client: TestClient,
    respx_mock: MockRouter,
) -> None:
    """Test that /ready returns 503 when Redis mock is down."""
    # Mock Redis ping to raise exception
    mock_redis = MagicMock()
    mock_redis.ping.side_effect = Exception("Redis connection failed")
    mock_redis_from_url.return_value = mock_redis

    # Mock DB connection
    mock_conn = MagicMock()
    mock_conn.__aenter__.return_value = mock_conn
    mock_engine.connect.return_value = mock_conn

    # Mock Qdrant HTTP health check
    respx_mock.get("http://localhost:6333/healthz").mock(
        return_value=httpx.Response(200, json={"title": "qdrant"})
    )

    response = client.get("/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["redis"] == "down"
    assert data["qdrant"] == "ok"
    assert data["database"] == "ok"
