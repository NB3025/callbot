"""callbot.health.tests.test_health_router — 헬스체크 엔드포인트 단위 테스트.

Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from callbot.health.router import configure_health_dependencies, router


# ---------------------------------------------------------------------------
# Mock HealthCheckable 구현
# ---------------------------------------------------------------------------

class _HealthyService:
    """health_check() → True."""
    def health_check(self) -> bool:
        return True


class _UnhealthyService:
    """health_check() → False."""
    def health_check(self) -> bool:
        return False


class _ExplodingService:
    """health_check() raises."""
    def health_check(self) -> bool:
        raise RuntimeError("connection refused")


# ---------------------------------------------------------------------------
# 헬퍼: 테스트용 FastAPI 앱 + TestClient 생성
# ---------------------------------------------------------------------------

def _make_client(
    pg_healthy: bool = True,
    redis_healthy: bool = True,
    pg_explodes: bool = False,
) -> TestClient:
    """Mock provider를 주입한 TestClient를 반환한다."""
    if pg_explodes:
        pg_instance = _ExplodingService()
    else:
        pg_instance = _HealthyService() if pg_healthy else _UnhealthyService()

    redis_instance = _HealthyService() if redis_healthy else _UnhealthyService()

    configure_health_dependencies(
        pg_provider=lambda: pg_instance,
        redis_provider=lambda: redis_instance,
    )

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: /health (readiness)
# ---------------------------------------------------------------------------

class TestReadinessHealthy:
    """Req 4.2 — DB/Redis 모두 정상이면 200 + healthy."""

    def test_returns_200_when_all_healthy(self) -> None:
        client = _make_client(pg_healthy=True, redis_healthy=True)
        resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["checks"]["postgres"] == "ok"
        assert body["checks"]["redis"] == "ok"


class TestReadinessUnhealthy:
    """Req 4.3, 4.4, 4.5 — DB 또는 Redis 실패 시 503 + unhealthy."""

    def test_returns_503_when_db_fails(self) -> None:
        client = _make_client(pg_healthy=False, redis_healthy=True)
        resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["postgres"] == "error"
        assert body["checks"]["redis"] == "ok"

    def test_returns_503_when_redis_fails(self) -> None:
        client = _make_client(pg_healthy=True, redis_healthy=False)
        resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["postgres"] == "ok"
        assert body["checks"]["redis"] == "error"

    def test_returns_503_when_both_fail(self) -> None:
        client = _make_client(pg_healthy=False, redis_healthy=False)
        resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["postgres"] == "error"
        assert body["checks"]["redis"] == "error"

    def test_returns_503_with_details_when_db_raises(self) -> None:
        client = _make_client(pg_explodes=True, redis_healthy=True)
        resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert "connection refused" in body["details"]["postgres"]


# ---------------------------------------------------------------------------
# Tests: /health/live (liveness)
# ---------------------------------------------------------------------------

class TestLiveness:
    """Req 4.6 — /health/live는 항상 200 + alive."""

    def test_returns_200_alive(self) -> None:
        client = _make_client(pg_healthy=True, redis_healthy=True)
        resp = client.get("/health/live")

        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}

    def test_returns_200_even_when_deps_unhealthy(self) -> None:
        client = _make_client(pg_healthy=False, redis_healthy=False)
        resp = client.get("/health/live")

        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}
