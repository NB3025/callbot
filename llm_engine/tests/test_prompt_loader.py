"""Property-based tests for PromptLoader — 메모리 기반 (pbt-guidelines 준수)."""
from __future__ import annotations

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from callbot.llm_engine.llm_engine import PromptLoader


# Feature: callbot-llm-integration, Property 7: YAML 프롬프트 로드 round-trip
# Validates: Requirements 7.2
@given(st.dictionaries(
    st.text(min_size=1),
    st.text(min_size=1),
    min_size=1,
))
@settings(max_examples=100)
def test_yaml_prompt_roundtrip(data: dict) -> None:
    """정의된 모든 intent 키에 대해 get_prompt는 해당 값을 그대로 반환한다."""
    loader = PromptLoader.from_dict(data)
    for key, value in data.items():
        assert loader.get_prompt(key) == value


# Feature: callbot-llm-integration, Property 8: YAML 미정의 intent → default fallback
# Validates: Requirements 7.3
@given(
    default_value=st.text(min_size=1),
    unknown_key=st.text(min_size=1),
)
@settings(max_examples=100)
def test_yaml_undefined_intent_returns_default(default_value: str, unknown_key: str) -> None:
    """YAML에 없는 intent 키에 대해 get_prompt는 default 키의 값을 반환한다."""
    assume(unknown_key != "default")
    loader = PromptLoader.from_dict({"default": default_value})
    assert loader.get_prompt(unknown_key) == default_value


# 파일 로딩 단위 테스트 — 파일 I/O는 여기서만 처리
def test_load_from_yaml_file(tmp_path) -> None:
    """실제 YAML 파일에서 정상적으로 로드된다."""
    yaml_file = tmp_path / "prompts.yaml"
    yaml_file.write_text("default: 안녕하세요\nbilling_inquiry: 요금 문의입니다", encoding="utf-8")
    loader = PromptLoader(str(yaml_file))
    assert loader.get_prompt("default") == "안녕하세요"
    assert loader.get_prompt("billing_inquiry") == "요금 문의입니다"


def test_load_missing_file_returns_empty() -> None:
    """존재하지 않는 파일 경로는 예외 없이 빈 dict로 처리된다."""
    loader = PromptLoader("/nonexistent/path/prompts.yaml")
    assert loader.get_prompt("any_key") is None
