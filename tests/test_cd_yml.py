"""cd.yml YAML 구조 단위 테스트.

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.5, 8.1, 8.5
"""

from pathlib import Path

import json
import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CD_YML_PATH = PROJECT_ROOT / ".github" / "workflows" / "cd.yml"
ECS_TASK_DEF_PATH = PROJECT_ROOT / "ecs-task-def.json"


@pytest.fixture(scope="module")
def cd() -> dict:
    """cd.yml을 파싱하여 dict로 반환."""
    with open(CD_YML_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def cd_raw() -> str:
    """cd.yml 원본 텍스트 반환 (GitHub Actions 표현식은 YAML 파싱 시 손실될 수 있으므로)."""
    return CD_YML_PATH.read_text()


@pytest.fixture(scope="module")
def deploy_steps(cd: dict) -> list[dict]:
    """deploy job의 steps 리스트 반환."""
    return cd["jobs"]["deploy"]["steps"]


@pytest.fixture(scope="module")
def ecs_task_def() -> dict:
    """ecs-task-def.json을 파싱하여 dict로 반환."""
    with open(ECS_TASK_DEF_PATH) as f:
        return json.load(f)


class TestWorkflowRunTrigger:
    """Requirement 6.2, 6.3: workflow_run 트리거가 CI 워크플로를 참조하는지 검증."""

    def _get_on(self, cd: dict) -> dict:
        return cd.get("on") or cd.get(True)

    def test_workflow_run_trigger_defined(self, cd: dict) -> None:
        on = self._get_on(cd)
        assert "workflow_run" in on

    def test_workflow_run_references_ci(self, cd: dict) -> None:
        on = self._get_on(cd)
        workflows = on["workflow_run"]["workflows"]
        assert "CI" in workflows

    def test_workflow_run_targets_main(self, cd: dict) -> None:
        on = self._get_on(cd)
        assert "main" in on["workflow_run"]["branches"]


class TestDeployJobCondition:
    """Requirement 6.3: deploy job의 if 조건에 conclusion == 'success'가 포함되어 있는지 검증."""

    def test_deploy_job_exists(self, cd: dict) -> None:
        assert "deploy" in cd["jobs"]

    def test_deploy_has_if_condition(self, cd: dict) -> None:
        deploy = cd["jobs"]["deploy"]
        assert "if" in deploy

    def test_deploy_if_contains_success_check(self, cd_raw: str) -> None:
        assert "conclusion == 'success'" in cd_raw


class TestECRImageBuildPush:
    """Requirement 6.4, 6.5: ECR 이미지 빌드/푸시 step이 존재하는지 검증."""

    def test_ecr_login_step_exists(self, deploy_steps: list[dict]) -> None:
        names = [s.get("name", "") for s in deploy_steps]
        assert any("ECR" in n for n in names)

    def test_docker_build_push_step_exists(self, deploy_steps: list[dict]) -> None:
        names = [s.get("name", "") for s in deploy_steps]
        assert any("Build" in n and "push" in n for n in names)

    def test_docker_push_command_present(self, cd_raw: str) -> None:
        assert "docker push" in cd_raw


class TestRDSSnapshotBeforeMigration:
    """Requirement 7.5: RDS 스냅샷 생성 step이 마이그레이션 step 이전에 위치하는지 검증."""

    def _find_step_index(self, steps: list[dict], keyword: str) -> int:
        for i, step in enumerate(steps):
            name = step.get("name", "")
            run_cmd = step.get("run", "")
            if keyword.lower() in name.lower() or keyword.lower() in run_cmd.lower():
                return i
        return -1

    def test_rds_snapshot_step_exists(self, deploy_steps: list[dict]) -> None:
        idx = self._find_step_index(deploy_steps, "snapshot")
        assert idx != -1, "RDS snapshot step not found"

    def test_alembic_migration_step_exists(self, deploy_steps: list[dict]) -> None:
        idx = self._find_step_index(deploy_steps, "alembic")
        assert idx != -1, "Alembic migration step not found"

    def test_snapshot_before_migration(self, deploy_steps: list[dict]) -> None:
        snapshot_idx = self._find_step_index(deploy_steps, "snapshot")
        migration_idx = self._find_step_index(deploy_steps, "alembic")
        assert snapshot_idx < migration_idx, (
            f"RDS snapshot (index {snapshot_idx}) must come before migration (index {migration_idx})"
        )


class TestECSRunTaskAlembic:
    """Requirement 7.1, 7.2: ECS run-task(alembic) step이 존재하고 실패 조건이 있는지 검증."""

    def test_run_task_step_exists(self, cd_raw: str) -> None:
        assert "run-task" in cd_raw

    def test_alembic_upgrade_command(self, cd_raw: str) -> None:
        assert "alembic" in cd_raw
        assert "upgrade" in cd_raw

    def test_migration_failure_check(self, cd_raw: str) -> None:
        """마이그레이션 실패 시 배포를 중단하는 조건이 있는지 검증."""
        assert "exit 1" in cd_raw or "exit_code" in cd_raw.lower() or "EXIT_CODE" in cd_raw


class TestECSServiceUpdate:
    """Requirement 8.1: ECS 서비스 업데이트 step에 minimumHealthyPercent, maximumPercent가 포함되어 있는지 검증."""

    def test_update_service_step_exists(self, cd_raw: str) -> None:
        assert "update-service" in cd_raw

    def test_minimum_healthy_percent(self, cd_raw: str) -> None:
        assert "minimumHealthyPercent" in cd_raw

    def test_maximum_percent(self, cd_raw: str) -> None:
        assert "maximumPercent" in cd_raw


class TestECSTaskDefJson:
    """Requirement 8.5, 8.6: ecs-task-def.json에 stopTimeout과 circuit breaker 설정 검증."""

    def test_task_def_file_exists(self) -> None:
        assert ECS_TASK_DEF_PATH.exists()

    def test_stop_timeout_is_45(self, ecs_task_def: dict) -> None:
        container = ecs_task_def["containerDefinitions"][0]
        assert container["stopTimeout"] == 45

    def test_circuit_breaker_in_cd_yml(self, cd_raw: str) -> None:
        """Circuit breaker 설정은 cd.yml의 서비스 업데이트 step에 포함."""
        assert "deploymentCircuitBreaker" in cd_raw or "circuit" in cd_raw.lower()

    def test_circuit_breaker_enable_true(self, cd_raw: str) -> None:
        assert "enable=true" in cd_raw or "enable: true" in cd_raw

    def test_circuit_breaker_rollback_true(self, cd_raw: str) -> None:
        assert "rollback=true" in cd_raw or "rollback: true" in cd_raw
