"""callbot.health.tests.test_health_properties — 헬스체크 property-based 테스트.

Feature: callbot-deployment
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.health.router import configure_health_dependencies, router


# ---------------------------------------------------------------------------
# Mock HealthCheckable 구현
# ---------------------------------------------------------------------------

class _MockService:
    """health_check() 반환값을 외부에서 제어할 수 있는 Mock."""

    def __init__(self, healthy: bool) -> None:
        self._healthy = healthy

    def health_check(self) -> bool:
        return self._healthy


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_client(pg_healthy: bool, redis_healthy: bool) -> TestClient:
    """주어진 상태 조합으로 TestClient를 생성한다."""
    pg = _MockService(pg_healthy)
    redis_svc = _MockService(redis_healthy)

    configure_health_dependencies(
        pg_provider=lambda: pg,
        redis_provider=lambda: redis_svc,
    )

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Property 1: 헬스체크 응답은 의존 서비스 상태를 정확히 반영한다
# Tag: Feature: callbot-deployment, Property 1: 헬스체크 응답은 의존 서비스 상태를 정확히 반영한다
# Validates: Requirements 4.2, 4.3, 4.4, 4.5
# ---------------------------------------------------------------------------

@given(
    postgres_healthy=st.booleans(),
    redis_healthy=st.booleans(),
)
@settings(max_examples=100)
def test_health_reflects_dependency_status(
    postgres_healthy: bool,
    redis_healthy: bool,
) -> None:
    """**Validates: Requirements 4.2, 4.3, 4.4, 4.5**

    For any combination of (postgres_healthy, redis_healthy),
    /health returns 200 only when both are True, otherwise 503.
    The checks field accurately reflects each service state.
    """
    client = _make_client(postgres_healthy, redis_healthy)
    resp = client.get("/health")
    body = resp.json()

    both_healthy = postgres_healthy and redis_healthy

    # Status code: 200 iff both healthy, 503 otherwise
    expected_status = 200 if both_healthy else 503
    assert resp.status_code == expected_status, (
        f"Expected {expected_status} for pg={postgres_healthy}, redis={redis_healthy}, "
        f"got {resp.status_code}"
    )

    # status field
    expected_label = "healthy" if both_healthy else "unhealthy"
    assert body["status"] == expected_label

    # checks field reflects individual service states
    assert body["checks"]["postgres"] == ("ok" if postgres_healthy else "error")
    assert body["checks"]["redis"] == ("ok" if redis_healthy else "error")


# ---------------------------------------------------------------------------
# Property 2: Liveness 엔드포인트는 의존 서비스 상태와 무관하게 항상 200을 반환한다
# Tag: Feature: callbot-deployment, Property 2: Liveness 엔드포인트는 의존 서비스 상태와 무관하게 항상 200을 반환한다
# Validates: Requirements 4.6
# ---------------------------------------------------------------------------

@given(
    postgres_healthy=st.booleans(),
    redis_healthy=st.booleans(),
)
@settings(max_examples=100)
def test_liveness_always_returns_200(
    postgres_healthy: bool,
    redis_healthy: bool,
) -> None:
    """**Validates: Requirements 4.6**

    For any combination of (postgres_healthy, redis_healthy),
    /health/live always returns 200 + {"status": "alive"}.
    """
    client = _make_client(postgres_healthy, redis_healthy)
    resp = client.get("/health/live")

    assert resp.status_code == 200, (
        f"Expected 200 for pg={postgres_healthy}, redis={redis_healthy}, "
        f"got {resp.status_code}"
    )
    assert resp.json() == {"status": "alive"}
