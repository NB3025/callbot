"""callbot.health.router — 헬스체크 엔드포인트 (readiness + liveness)"""
from __future__ import annotations

import logging
from typing import Callable, Optional, Protocol

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic 응답 모델
# ---------------------------------------------------------------------------

class HealthCheckResult(BaseModel):
    """Readiness 응답 모델."""

    status: str  # "healthy" | "unhealthy"
    checks: dict[str, str]  # {"postgres": "ok", "redis": "ok"}
    details: Optional[dict[str, str]] = None  # 실패 시 상세 정보


class LivenessResult(BaseModel):
    """Liveness 응답 모델."""

    status: str  # "alive"


# ---------------------------------------------------------------------------
# 의존성 프로토콜 — health_check() -> bool 만 요구
# ---------------------------------------------------------------------------

class HealthCheckable(Protocol):
    def health_check(self) -> bool: ...


# ---------------------------------------------------------------------------
# 의존성 주입 레지스트리
# ---------------------------------------------------------------------------

_pg_provider: Callable[[], Optional[HealthCheckable]] = lambda: None
_redis_provider: Callable[[], Optional[HealthCheckable]] = lambda: None


def configure_health_dependencies(
    pg_provider: Callable[[], Optional[HealthCheckable]],
    redis_provider: Callable[[], Optional[HealthCheckable]],
) -> None:
    """앱 시작 시 DB/Redis 인스턴스 공급 함수를 등록한다."""
    global _pg_provider, _redis_provider
    _pg_provider = pg_provider
    _redis_provider = redis_provider


def _get_pg() -> Optional[HealthCheckable]:
    return _pg_provider()


def _get_redis() -> Optional[HealthCheckable]:
    return _redis_provider()


# ---------------------------------------------------------------------------
# 라우터
# ---------------------------------------------------------------------------

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResult)
async def readiness_check(
    response: Response,
    pg: Optional[HealthCheckable] = Depends(_get_pg),
    redis_store: Optional[HealthCheckable] = Depends(_get_redis),
) -> HealthCheckResult:
    """Readiness probe: DB + Redis 연결 확인."""
    checks: dict[str, str] = {}
    details: dict[str, str] = {}

    # PostgreSQL
    try:
        pg_ok = pg.health_check() if pg is not None else False
    except Exception as exc:
        pg_ok = False
        details["postgres"] = str(exc)

    checks["postgres"] = "ok" if pg_ok else "error"
    if not pg_ok and "postgres" not in details:
        details["postgres"] = "health_check returned False"

    # Redis
    try:
        redis_ok = redis_store.health_check() if redis_store is not None else False
    except Exception as exc:
        redis_ok = False
        details["redis"] = str(exc)

    checks["redis"] = "ok" if redis_ok else "error"
    if not redis_ok and "redis" not in details:
        details["redis"] = "health_check returned False"

    # 결과 판정
    if pg_ok and redis_ok:
        return HealthCheckResult(status="healthy", checks=checks)

    response.status_code = 503
    return HealthCheckResult(status="unhealthy", checks=checks, details=details)


@router.get("/health/live", response_model=LivenessResult)
async def liveness_check() -> LivenessResult:
    """Liveness probe: 프로세스 생존 확인. 항상 200."""
    return LivenessResult(status="alive")
