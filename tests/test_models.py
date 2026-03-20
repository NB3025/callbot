"""
Property-based tests for voice_io data models.

Sub-task 1.1: STTResult 속성 테스트
Sub-task 1.2: DTMFResult 속성 테스트
"""
from hypothesis import given, assume, settings
from hypothesis import strategies as st
import pytest

from callbot.voice_io.models import STTResult, DTMFResult


# ---------------------------------------------------------------------------
# Sub-task 1.1 — Property 1: STT 확신도-유효성-failure_type 일관성
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------

@given(
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    threshold=st.floats(min_value=0.3, max_value=0.7, allow_nan=False),
)
@settings(max_examples=200)
def test_stt_result_validity_consistency(confidence: float, threshold: float):
    """
    **Validates: Requirements 1.5**

    Property 1: STT 확신도-유효성-failure_type 일관성
    is_valid = (confidence >= threshold) = (failure_type is None) 세 조건이 항상 동치.
    """
    result = STTResult.create(
        text="테스트",
        confidence=confidence,
        threshold=threshold,
        processing_time_ms=100,
    )

    expected_valid = confidence >= threshold

    # is_valid must match confidence >= threshold
    assert result.is_valid == expected_valid, (
        f"is_valid={result.is_valid} but confidence={confidence} >= threshold={threshold} "
        f"is {expected_valid}"
    )

    # failure_type is None iff is_valid is True
    if result.is_valid:
        assert result.failure_type is None, (
            f"is_valid=True but failure_type={result.failure_type!r}"
        )
    else:
        assert result.failure_type is not None, (
            f"is_valid=False but failure_type is None"
        )


# ---------------------------------------------------------------------------
# Sub-task 1.2 — Property 2: DTMF 자릿수 완료 판단 및 상호 배타성
# Validates: Requirements 2.1, 2.2, 2.3
# ---------------------------------------------------------------------------

@given(
    digits=st.text(alphabet="0123456789", min_size=0, max_size=10),
    expected_length=st.integers(min_value=1, max_value=10),
    is_timeout=st.booleans(),
)
@settings(max_examples=200)
def test_dtmf_result_completeness_and_mutual_exclusion(
    digits: str, expected_length: int, is_timeout: bool
):
    """
    **Validates: Requirements 2.1, 2.2, 2.3**

    Property 2: DTMF 자릿수 완료 판단 및 상호 배타성
    - is_complete = (len(digits) == expected_length)
    - is_complete와 is_timeout은 동시에 True일 수 없음
    """
    # When digits fill expected_length, is_timeout must be False (complete takes priority)
    # When is_timeout=True, digits must be shorter than expected_length
    if is_timeout:
        assume(len(digits) < expected_length)

    result = DTMFResult.create(
        digits=digits,
        expected_length=expected_length,
        is_timeout=is_timeout,
        input_type="unknown",
    )

    expected_complete = len(digits) == expected_length

    # is_complete must match len(digits) == expected_length
    assert result.is_complete == expected_complete, (
        f"is_complete={result.is_complete} but len(digits)={len(digits)} "
        f"expected_length={expected_length}"
    )

    # is_complete and is_timeout cannot both be True
    assert not (result.is_complete and result.is_timeout), (
        f"is_complete={result.is_complete} and is_timeout={result.is_timeout} "
        "cannot both be True"
    )
