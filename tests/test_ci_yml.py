"""ci.yml YAML 구조 단위 테스트.

Validates: Requirements 5.1, 5.2, 5.6
"""

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CI_YML_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def ci() -> dict:
    """ci.yml을 파싱하여 dict로 반환."""
    with open(CI_YML_PATH) as f:
        return yaml.safe_load(f)


class TestCIJobDefinitions:
    """Requirement 5.1: ci.yml에 4개 job이 정의되어 있는지 검증."""

    def test_has_jobs_section(self, ci: dict) -> None:
        assert "jobs" in ci

    def test_lint_job_defined(self, ci: dict) -> None:
        assert "lint" in ci["jobs"]

    def test_unit_test_job_defined(self, ci: dict) -> None:
        assert "unit-test" in ci["jobs"]

    def test_integration_test_job_defined(self, ci: dict) -> None:
        assert "integration-test" in ci["jobs"]

    def test_docker_build_and_scan_job_defined(self, ci: dict) -> None:
        assert "docker-build-and-scan" in ci["jobs"]


class TestTriggerEvents:
    """Requirement 5.2: 트리거 이벤트가 main 브랜치를 대상으로 하는지 검증."""

    def test_has_on_section(self, ci: dict) -> None:
        assert True in [key in ci for key in ("on", True)]

    def _get_on(self, ci: dict) -> dict:
        """YAML에서 'on'은 True로 파싱될 수 있으므로 양쪽 모두 확인."""
        return ci.get("on") or ci.get(True)

    def test_push_trigger_defined(self, ci: dict) -> None:
        on = self._get_on(ci)
        assert "push" in on

    def test_push_targets_main(self, ci: dict) -> None:
        on = self._get_on(ci)
        assert "main" in on["push"]["branches"]

    def test_pull_request_trigger_defined(self, ci: dict) -> None:
        on = self._get_on(ci)
        assert "pull_request" in on

    def test_pull_request_targets_main(self, ci: dict) -> None:
        on = self._get_on(ci)
        assert "main" in on["pull_request"]["branches"]


class TestIntegrationTestServices:
    """Requirement 5.6: integration-test job에 services(postgres, redis)가 정의되어 있는지 검증."""

    def test_integration_test_has_services(self, ci: dict) -> None:
        job = ci["jobs"]["integration-test"]
        assert "services" in job

    def test_postgres_service_defined(self, ci: dict) -> None:
        services = ci["jobs"]["integration-test"]["services"]
        assert "postgres" in services

    def test_redis_service_defined(self, ci: dict) -> None:
        services = ci["jobs"]["integration-test"]["services"]
        assert "redis" in services
