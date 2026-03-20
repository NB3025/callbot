"""Unit tests for Dockerfile structure.

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8, 4.7, 9.1, 9.2
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"


def _read_dockerfile() -> str:
    return DOCKERFILE_PATH.read_text()


def _split_stages(content: str) -> dict[str, str]:
    """Dockerfile 내용을 스테이지별로 분리하여 반환한다."""
    stages: dict[str, str] = {}
    current_stage: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("FROM ") and " AS " in stripped.upper():
            if current_stage is not None:
                stages[current_stage] = "\n".join(current_lines)
            # "FROM ... AS name" 에서 name 추출
            current_stage = stripped.split()[-1].lower()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_stage is not None:
        stages[current_stage] = "\n".join(current_lines)

    return stages


def test_dockerfile_exists() -> None:
    """Dockerfile이 프로젝트 루트에 존재해야 한다."""
    assert DOCKERFILE_PATH.exists(), "Dockerfile not found at project root"


def test_multistage_builder_and_runtime() -> None:
    """멀티스테이지 빌드: builder와 runtime 스테이지가 python:3.12-slim 기반이어야 한다.

    Validates: Requirements 2.1, 2.3
    """
    content = _read_dockerfile()
    assert "FROM python:3.12-slim AS builder" in content, (
        "Missing 'FROM python:3.12-slim AS builder' stage"
    )
    assert "FROM python:3.12-slim AS runtime" in content, (
        "Missing 'FROM python:3.12-slim AS runtime' stage"
    )


def test_builder_stage_uv_sync() -> None:
    """builder 스테이지에 uv sync --frozen --no-dev 명령이 포함되어야 한다.

    Validates: Requirements 2.2
    """
    stages = _split_stages(_read_dockerfile())
    assert "builder" in stages, "builder stage not found"
    assert "uv sync --frozen --no-dev" in stages["builder"], (
        "Missing 'uv sync --frozen --no-dev' in builder stage"
    )


def test_user_appuser() -> None:
    """런타임 스테이지에서 USER appuser로 실행해야 한다.

    Validates: Requirements 2.4
    """
    content = _read_dockerfile()
    assert "USER appuser" in content, "Missing 'USER appuser' directive"


def test_healthcheck_calls_health_live() -> None:
    """HEALTHCHECK 명령이 /health/live 엔드포인트를 호출해야 한다.

    Validates: Requirements 4.7
    """
    content = _read_dockerfile()
    assert "HEALTHCHECK" in content, "Missing HEALTHCHECK directive"
    assert "/health/live" in content, (
        "HEALTHCHECK must call /health/live endpoint"
    )


def test_expose_8000() -> None:
    """EXPOSE 8000 포트 선언이 포함되어야 한다.

    Validates: Requirements 2.5
    """
    content = _read_dockerfile()
    assert "EXPOSE 8000" in content, "Missing 'EXPOSE 8000' directive"


def test_cmd_callbot() -> None:
    """CMD ["callbot"] 엔트리포인트가 설정되어야 한다.

    Validates: Requirements 2.6
    """
    content = _read_dockerfile()
    assert 'CMD ["callbot"]' in content, 'Missing \'CMD ["callbot"]\' directive'


def test_pip_uninstall_in_runtime() -> None:
    """런타임 스테이지에서 pip uninstall 명령이 포함되어야 한다.

    Validates: Requirements 9.2
    """
    stages = _split_stages(_read_dockerfile())
    assert "runtime" in stages, "runtime stage not found"
    assert "pip uninstall" in stages["runtime"], (
        "Missing 'pip uninstall' in runtime stage"
    )


def test_copy_alembic_from_builder() -> None:
    """builder에서 alembic 디렉토리와 alembic.ini를 복사해야 한다.

    Validates: Requirements 2.8
    """
    content = _read_dockerfile()
    assert "COPY --from=builder /app/alembic" in content, (
        "Missing 'COPY --from=builder /app/alembic' directive"
    )
    assert "COPY --from=builder /app/alembic.ini" in content, (
        "Missing 'COPY --from=builder /app/alembic.ini' directive"
    )
