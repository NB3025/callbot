"""pyproject.toml 구조 단위 테스트.

Validates: Requirements 1.1, 1.2, 1.3, 1.7
"""

import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


@pytest.fixture(scope="module")
def pyproject() -> dict:
    """pyproject.toml을 파싱하여 dict로 반환."""
    with open(PYPROJECT_PATH, "rb") as f:
        return tomllib.load(f)


class TestProjectMetadata:
    """Requirement 1.1: 프로젝트명이 callbot인지 검증."""

    def test_project_name_is_callbot(self, pyproject: dict) -> None:
        assert pyproject["project"]["name"] == "callbot"


class TestRuntimeDependencies:
    """Requirement 1.2: 12개 런타임 의존성이 모두 포함되어 있는지 검증."""

    EXPECTED_PACKAGES = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "boto3",
        "psycopg2-binary",
        "cryptography",
        "requests",
        "pyyaml",
        "redis",
        "alembic",
        "sqlalchemy",
        "pyjwt",
    ]

    def test_has_all_12_runtime_dependencies(self, pyproject: dict) -> None:
        deps = pyproject["project"]["dependencies"]
        dep_names = [d.split(">")[0].split("[")[0].strip().lower() for d in deps]
        for pkg in self.EXPECTED_PACKAGES:
            assert pkg in dep_names, f"Missing runtime dependency: {pkg}"

    def test_runtime_dependency_count(self, pyproject: dict) -> None:
        deps = pyproject["project"]["dependencies"]
        assert len(deps) >= 12, f"Expected at least 12 dependencies, got {len(deps)}"


class TestOptionalDependencies:
    """Requirement 1.3: test, dev, nlu optional-dependency 그룹 검증."""

    def test_test_group_exists(self, pyproject: dict) -> None:
        opt = pyproject["project"]["optional-dependencies"]
        assert "test" in opt

    def test_dev_group_exists(self, pyproject: dict) -> None:
        opt = pyproject["project"]["optional-dependencies"]
        assert "dev" in opt

    def test_nlu_group_exists(self, pyproject: dict) -> None:
        opt = pyproject["project"]["optional-dependencies"]
        assert "nlu" in opt

    def test_test_group_contains_pytest(self, pyproject: dict) -> None:
        test_deps = pyproject["project"]["optional-dependencies"]["test"]
        names = [d.split(">")[0].split("[")[0].strip().lower() for d in test_deps]
        assert "pytest" in names

    def test_test_group_contains_hypothesis(self, pyproject: dict) -> None:
        test_deps = pyproject["project"]["optional-dependencies"]["test"]
        names = [d.split(">")[0].split("[")[0].strip().lower() for d in test_deps]
        assert "hypothesis" in names

    def test_test_group_contains_coverage(self, pyproject: dict) -> None:
        test_deps = pyproject["project"]["optional-dependencies"]["test"]
        names = [d.split(">")[0].split("[")[0].strip().lower() for d in test_deps]
        assert "coverage" in names

    def test_dev_group_contains_ruff(self, pyproject: dict) -> None:
        dev_deps = pyproject["project"]["optional-dependencies"]["dev"]
        names = [d.split(">")[0].split("[")[0].strip().lower() for d in dev_deps]
        assert "ruff" in names

    def test_dev_group_contains_mypy(self, pyproject: dict) -> None:
        dev_deps = pyproject["project"]["optional-dependencies"]["dev"]
        names = [d.split(">")[0].split("[")[0].strip().lower() for d in dev_deps]
        assert "mypy" in names

    def test_nlu_group_contains_torch(self, pyproject: dict) -> None:
        nlu_deps = pyproject["project"]["optional-dependencies"]["nlu"]
        names = [d.split(">")[0].split("[")[0].strip().lower() for d in nlu_deps]
        assert "torch" in names


class TestEntrypoint:
    """Requirement 1.7: callbot 엔트리포인트가 web_tester.app:main을 가리키는지 검증."""

    def test_callbot_script_exists(self, pyproject: dict) -> None:
        scripts = pyproject["project"]["scripts"]
        assert "callbot" in scripts

    def test_callbot_points_to_main(self, pyproject: dict) -> None:
        scripts = pyproject["project"]["scripts"]
        assert scripts["callbot"] == "web_tester.app:main"
