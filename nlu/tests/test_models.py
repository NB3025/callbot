"""callbot.nlu.tests.test_models — 데이터 모델 속성 기반 테스트

Validates: Requirements 1.5, 1.6, 2.5, 2.6, 2.7, 2.8, 3.4, 3.5
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.nlu.enums import (
    ClassificationStatus,
    EntityType,
    Intent,
    RelationType,
    SYSTEM_CONTROL_INTENTS,
    ESCALATION_INTENTS,
)
from callbot.nlu.models import (
    CONFIDENCE_THRESHOLD,
    ClassificationResult,
    DetectionStats,
    Entity,
    FilterResult,
    IntentRelation,
    MaskedText,
    RestoreResult,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_text = st.text(min_size=0, max_size=200)
st_pattern_name = st.text(min_size=1, max_size=50)
st_patterns = st.lists(st_pattern_name, min_size=1, max_size=5)
st_confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
st_threshold = st.floats(min_value=0.5, max_value=0.9, allow_nan=False)
st_intent = st.sampled_from(list(Intent))
st_non_system_control_intent = st.sampled_from(
    [i for i in Intent if i not in SYSTEM_CONTROL_INTENTS]
)
st_non_escalation_intent = st.sampled_from(
    [i for i in Intent if i not in ESCALATION_INTENTS]
)
st_token = st.text(min_size=1, max_size=20).map(lambda s: f"[{s}]")


# ---------------------------------------------------------------------------
# Property 1: FilterResult 안전성-패턴 일관성
# Validates: Requirements 1.5, 1.6
# ---------------------------------------------------------------------------

@given(original_text=st_text, processing_time_ms=st.integers(min_value=0, max_value=50))
@settings(max_examples=100)
def test_filter_result_safe_has_empty_patterns(original_text: str, processing_time_ms: int):
    """Property 1: is_safe=True이면 detected_patterns는 빈 리스트.
    Validates: Requirements 1.5, 1.6
    """
    result = FilterResult.safe(original_text=original_text, processing_time_ms=processing_time_ms)
    assert result.is_safe is True
    assert result.detected_patterns == []


@given(
    patterns=st_patterns,
    original_text=st_text,
    processing_time_ms=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=100)
def test_filter_result_unsafe_has_nonempty_patterns(
    patterns: list[str], original_text: str, processing_time_ms: int
):
    """Property 1: is_safe=False이면 detected_patterns는 최소 1개 이상.
    Validates: Requirements 1.5, 1.6
    """
    result = FilterResult.unsafe(
        detected_patterns=patterns,
        original_text=original_text,
        processing_time_ms=processing_time_ms,
    )
    assert result.is_safe is False
    assert len(result.detected_patterns) >= 1


@given(
    is_safe=st.booleans(),
    original_text=st_text,
    processing_time_ms=st.integers(min_value=0, max_value=50),
    patterns=st_patterns,
)
@settings(max_examples=100)
def test_filter_result_safety_pattern_biconditional(
    is_safe: bool, original_text: str, processing_time_ms: int, patterns: list[str]
):
    """Property 1: is_safe ↔ detected_patterns == [] 쌍방향 동치.
    Validates: Requirements 1.5, 1.6
    """
    if is_safe:
        result = FilterResult.safe(original_text=original_text, processing_time_ms=processing_time_ms)
    else:
        result = FilterResult.unsafe(
            detected_patterns=patterns,
            original_text=original_text,
            processing_time_ms=processing_time_ms,
        )
    # 쌍방향 동치 검증
    assert result.is_safe == (result.detected_patterns == [])


# ---------------------------------------------------------------------------
# Property 2: ClassificationResult 확신도-상태 일관성
# Validates: Requirements 2.5, 2.6
# ---------------------------------------------------------------------------

@given(
    intent=st.sampled_from([i for i in Intent if i != Intent.UNCLASSIFIED]),
    confidence=st_confidence,
    threshold=st_threshold,
)
@settings(max_examples=100)
def test_classification_result_confidence_status_consistency(
    intent: Intent, confidence: float, threshold: float
):
    """Property 2: classification_status=SUCCESS ↔ confidence >= threshold.
    Validates: Requirements 2.5, 2.6
    """
    result = ClassificationResult.create(
        primary_intent=intent,
        confidence=confidence,
        threshold=threshold,
    )
    if confidence >= threshold:
        assert result.classification_status == ClassificationStatus.SUCCESS
    else:
        assert result.classification_status == ClassificationStatus.FAILURE


# ---------------------------------------------------------------------------
# Property 3: 시스템 제어 의도 플래그 일관성
# Validates: Requirements 2.8
# ---------------------------------------------------------------------------

@given(confidence=st_confidence)
@settings(max_examples=100)
def test_system_control_intent_sets_flag(confidence: float):
    """Property 3: primary_intent ∈ SYSTEM_CONTROL_INTENTS → is_system_control=True.
    Validates: Requirements 2.8
    """
    for intent in SYSTEM_CONTROL_INTENTS:
        result = ClassificationResult.create(primary_intent=intent, confidence=confidence)
        assert result.is_system_control is True


@given(intent=st_non_system_control_intent, confidence=st_confidence)
@settings(max_examples=100)
def test_non_system_control_intent_clears_flag(intent: Intent, confidence: float):
    """Property 3: primary_intent ∉ SYSTEM_CONTROL_INTENTS → is_system_control=False.
    Validates: Requirements 2.8
    """
    result = ClassificationResult.create(primary_intent=intent, confidence=confidence)
    assert result.is_system_control is False


@given(intent=st_intent, confidence=st_confidence)
@settings(max_examples=100)
def test_system_control_flag_biconditional(intent: Intent, confidence: float):
    """Property 3: is_system_control ↔ primary_intent ∈ SYSTEM_CONTROL_INTENTS.
    Validates: Requirements 2.8
    """
    result = ClassificationResult.create(primary_intent=intent, confidence=confidence)
    assert result.is_system_control == (intent in SYSTEM_CONTROL_INTENTS)


# ---------------------------------------------------------------------------
# Property 4: 즉시 에스컬레이션 플래그 일관성
# Validates: Requirements 2.7
# ---------------------------------------------------------------------------

@given(confidence=st_confidence)
@settings(max_examples=100)
def test_escalation_intent_sets_flag(confidence: float):
    """Property 4: primary_intent ∈ ESCALATION_INTENTS → requires_immediate_escalation=True.
    Validates: Requirements 2.7
    """
    for intent in ESCALATION_INTENTS:
        result = ClassificationResult.create(primary_intent=intent, confidence=confidence)
        assert result.requires_immediate_escalation is True


@given(intent=st_non_escalation_intent, confidence=st_confidence)
@settings(max_examples=100)
def test_non_escalation_intent_clears_flag(intent: Intent, confidence: float):
    """Property 4: primary_intent ∉ ESCALATION_INTENTS → requires_immediate_escalation=False.
    Validates: Requirements 2.7
    """
    result = ClassificationResult.create(primary_intent=intent, confidence=confidence)
    assert result.requires_immediate_escalation is False


@given(intent=st_intent, confidence=st_confidence)
@settings(max_examples=100)
def test_escalation_flag_biconditional(intent: Intent, confidence: float):
    """Property 4: requires_immediate_escalation ↔ primary_intent ∈ ESCALATION_INTENTS.
    Validates: Requirements 2.7
    """
    result = ClassificationResult.create(primary_intent=intent, confidence=confidence)
    assert result.requires_immediate_escalation == (intent in ESCALATION_INTENTS)


# ---------------------------------------------------------------------------
# Property 6: RestoreResult 성공-미복원_토큰 일관성
# Validates: Requirements 3.4, 3.5
# ---------------------------------------------------------------------------

@given(text=st_text)
@settings(max_examples=100)
def test_restore_result_success_has_empty_unrestored(text: str):
    """Property 6: is_success=True이면 unrestored_tokens == [].
    Validates: Requirements 3.4, 3.5
    """
    result = RestoreResult.success(text=text)
    assert result.is_success is True
    assert result.unrestored_tokens == []


@given(
    text=st_text,
    tokens=st.lists(st_token, min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_restore_result_failure_has_nonempty_unrestored(text: str, tokens: list[str]):
    """Property 6: is_success=False이면 unrestored_tokens는 최소 1개 이상.
    Validates: Requirements 3.4, 3.5
    """
    result = RestoreResult.failure(text=text, unrestored_tokens=tokens)
    assert result.is_success is False
    assert len(result.unrestored_tokens) >= 1


@given(
    is_success=st.booleans(),
    text=st_text,
    tokens=st.lists(st_token, min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_restore_result_success_token_biconditional(
    is_success: bool, text: str, tokens: list[str]
):
    """Property 6: is_success ↔ unrestored_tokens == [] 쌍방향 동치.
    Validates: Requirements 3.4, 3.5
    """
    if is_success:
        result = RestoreResult.success(text=text)
    else:
        result = RestoreResult.failure(text=text, unrestored_tokens=tokens)
    assert result.is_success == (result.unrestored_tokens == [])
