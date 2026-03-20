"""Unit tests for .dockerignore file.

Validates: Requirements 2.7
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERIGNORE_PATH = REPO_ROOT / ".dockerignore"


def test_dockerignore_file_exists() -> None:
    """`.dockerignore` 파일이 프로젝트 루트에 존재해야 한다."""
    assert DOCKERIGNORE_PATH.exists(), ".dockerignore file not found at project root"


def test_dockerignore_contains_required_patterns() -> None:
    """`.dockerignore`에 필수 제외 패턴이 모두 포함되어야 한다."""
    content = DOCKERIGNORE_PATH.read_text()
    lines = [line.strip() for line in content.splitlines()]

    required_patterns = [".venv", "__pycache__", ".git", ".hypothesis", "*.pyc"]
    for pattern in required_patterns:
        assert pattern in lines, f"Missing required pattern: {pattern}"
