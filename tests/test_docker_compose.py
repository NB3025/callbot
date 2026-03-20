"""docker-compose.yml 구조 단위 테스트.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = PROJECT_ROOT / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose() -> dict:
    """docker-compose.yml을 파싱하여 dict로 반환."""
    with open(COMPOSE_PATH) as f:
        return yaml.safe_load(f)


class TestServiceDefinitions:
    """Requirement 3.1, 3.2: app, redis, postgres 3개 서비스가 정의되어 있는지 검증."""

    def test_has_services_section(self, compose: dict) -> None:
        assert "services" in compose

    def test_postgres_service_defined(self, compose: dict) -> None:
        assert "postgres" in compose["services"]

    def test_redis_service_defined(self, compose: dict) -> None:
        assert "redis" in compose["services"]

    def test_app_service_defined(self, compose: dict) -> None:
        assert "app" in compose["services"]


class TestAppService:
    """Requirement 3.1, 3.3, 3.4, 3.6: app 서비스의 depends_on, 환경변수, 포트 매핑 검증."""

    def test_app_depends_on_postgres(self, compose: dict) -> None:
        app = compose["services"]["app"]
        assert "postgres" in app["depends_on"]

    def test_app_depends_on_redis(self, compose: dict) -> None:
        app = compose["services"]["app"]
        assert "redis" in app["depends_on"]

    def test_app_postgres_depends_on_healthy(self, compose: dict) -> None:
        app = compose["services"]["app"]
        assert app["depends_on"]["postgres"]["condition"] == "service_healthy"

    def test_app_redis_depends_on_healthy(self, compose: dict) -> None:
        app = compose["services"]["app"]
        assert app["depends_on"]["redis"]["condition"] == "service_healthy"

    def test_app_has_db_dsn_env(self, compose: dict) -> None:
        env = compose["services"]["app"]["environment"]
        assert "CALLBOT_DB_DSN" in env

    def test_app_has_redis_host_env(self, compose: dict) -> None:
        env = compose["services"]["app"]["environment"]
        assert "CALLBOT_REDIS_HOST" in env

    def test_app_has_secret_backend_env(self, compose: dict) -> None:
        env = compose["services"]["app"]["environment"]
        assert env["CALLBOT_SECRET_BACKEND"] == "env"

    def test_app_port_mapping(self, compose: dict) -> None:
        ports = compose["services"]["app"]["ports"]
        assert "8000:8000" in ports


class TestRedisService:
    """Requirement 3.2, 3.5: redis 서비스의 healthcheck 설정 검증."""

    def test_redis_has_healthcheck(self, compose: dict) -> None:
        redis_svc = compose["services"]["redis"]
        assert "healthcheck" in redis_svc

    def test_redis_healthcheck_uses_ping(self, compose: dict) -> None:
        hc = compose["services"]["redis"]["healthcheck"]
        test_cmd = hc["test"]
        assert "redis-cli" in test_cmd
        assert "ping" in test_cmd

    def test_redis_healthcheck_has_interval(self, compose: dict) -> None:
        hc = compose["services"]["redis"]["healthcheck"]
        assert "interval" in hc

    def test_redis_healthcheck_has_timeout(self, compose: dict) -> None:
        hc = compose["services"]["redis"]["healthcheck"]
        assert "timeout" in hc

    def test_redis_healthcheck_has_retries(self, compose: dict) -> None:
        hc = compose["services"]["redis"]["healthcheck"]
        assert "retries" in hc
