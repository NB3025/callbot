"""callbot.orchestrator.tests.test_models — 오케스트레이터 데이터 모델 속성 기반 테스트"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.orchestrator.enums import ActionType, SwitchDecision
from callbot.orchestrator.models import (
    AuthRequirement,
    OrchestratorAction,
    SurveyResult,
)


# ---------------------------------------------------------------------------
# Property 1: OrchestratorAction 분기 일관성
# Validates: Requirements 1.1, 1.2
# ---------------------------------------------------------------------------

@given(context=st.fixed_dictionaries({}))
@settings(max_examples=100)
def test_orchestrator_action_system_control_target(context: dict) -> None:
    """**Property 1a: OrchestratorAction 분기 일관성 — SYSTEM_CONTROL**

    action_type=SYSTEM_CONTROL → target_component == "orchestrator"

    Validates: Requirements 1.1, 1.2
    """
    action = OrchestratorAction(
        action_type=ActionType.SYSTEM_CONTROL,
        target_component="orchestrator",
        context=context,
    )
    assert action.target_component == "orchestrator"


@given(context=st.fixed_dictionaries({}))
@settings(max_examples=100)
def test_orchestrator_action_system_control_invalid_target_raises(context: dict) -> None:
    """SYSTEM_CONTROL에 잘못된 target_component → ValueError"""
    with pytest.raises(ValueError):
        OrchestratorAction(
            action_type=ActionType.SYSTEM_CONTROL,
            target_component="llm_engine",
            context=context,
        )


@given(context=st.fixed_dictionaries({}))
@settings(max_examples=100)
def test_orchestrator_action_process_business_target(context: dict) -> None:
    """**Property 1b: OrchestratorAction 분기 일관성 — PROCESS_BUSINESS**

    action_type=PROCESS_BUSINESS → target_component == "llm_engine"

    Validates: Requirements 1.1, 1.2
    """
    action = OrchestratorAction(
        action_type=ActionType.PROCESS_BUSINESS,
        target_component="llm_engine",
        context=context,
    )
    assert action.target_component == "llm_engine"


@given(context=st.fixed_dictionaries({}))
@settings(max_examples=100)
def test_orchestrator_action_process_business_invalid_target_raises(context: dict) -> None:
    """PROCESS_BUSINESS에 잘못된 target_component → ValueError"""
    with pytest.raises(ValueError):
        OrchestratorAction(
            action_type=ActionType.PROCESS_BUSINESS,
            target_component="orchestrator",
            context=context,
        )


@given(context=st.fixed_dictionaries({}))
@settings(max_examples=100)
def test_orchestrator_action_escalate_target(context: dict) -> None:
    """**Property 1c: OrchestratorAction 분기 일관성 — ESCALATE**

    action_type=ESCALATE → target_component == "routing_engine"

    Validates: Requirements 1.1, 1.2
    """
    action = OrchestratorAction(
        action_type=ActionType.ESCALATE,
        target_component="routing_engine",
        context=context,
    )
    assert action.target_component == "routing_engine"


@given(context=st.fixed_dictionaries({}))
@settings(max_examples=100)
def test_orchestrator_action_escalate_invalid_target_raises(context: dict) -> None:
    """ESCALATE에 잘못된 target_component → ValueError"""
    with pytest.raises(ValueError):
        OrchestratorAction(
            action_type=ActionType.ESCALATE,
            target_component="llm_engine",
            context=context,
        )


@given(
    action_type=st.sampled_from([ActionType.SYSTEM_CONTROL, ActionType.PROCESS_BUSINESS, ActionType.ESCALATE]),
    target_component=st.text(min_size=1, max_size=50),
    context=st.fixed_dictionaries({}),
)
@settings(max_examples=200)
def test_orchestrator_action_invariant_property(
    action_type: ActionType,
    target_component: str,
    context: dict,
) -> None:
    """**Property 1: OrchestratorAction 분기 일관성 (전체)**

    SYSTEM_CONTROL → "orchestrator", PROCESS_BUSINESS → "llm_engine", ESCALATE → "routing_engine"

    Validates: Requirements 1.1, 1.2
    """
    expected = {
        ActionType.SYSTEM_CONTROL: "orchestrator",
        ActionType.PROCESS_BUSINESS: "llm_engine",
        ActionType.ESCALATE: "routing_engine",
    }
    correct_target = expected[action_type]

    if target_component == correct_target:
        action = OrchestratorAction(
            action_type=action_type,
            target_component=target_component,
            context=context,
        )
        assert action.target_component == correct_target
    else:
        with pytest.raises(ValueError):
            OrchestratorAction(
                action_type=action_type,
                target_component=target_component,
                context=context,
            )


# ---------------------------------------------------------------------------
# Property 3: SurveyResult 점수-건너뜀 일관성
# Validates: Requirements 3.1, 3.2
# ---------------------------------------------------------------------------

@given(
    score=st.integers(min_value=1, max_value=5),
    input_method=st.sampled_from(["voice", "dtmf"]),
)
@settings(max_examples=100)
def test_survey_result_not_skipped_valid_score(score: int, input_method: str) -> None:
    """**Property 3a: SurveyResult — is_skipped=False → score ∈ [1, 5]**

    Validates: Requirements 3.1
    """
    result = SurveyResult(score=score, input_method=input_method, is_skipped=False)
    assert result.is_skipped is False
    assert result.score is not None
    assert 1 <= result.score <= 5


@given(
    score=st.integers().filter(lambda x: x < 1 or x > 5),
    input_method=st.sampled_from(["voice", "dtmf"]),
)
@settings(max_examples=100)
def test_survey_result_not_skipped_invalid_score_raises(score: int, input_method: str) -> None:
    """is_skipped=False + score 범위 외 → ValueError"""
    with pytest.raises(ValueError):
        SurveyResult(score=score, input_method=input_method, is_skipped=False)


def test_survey_result_skipped_score_none() -> None:
    """**Property 3b: SurveyResult — is_skipped=True → score is None**

    Validates: Requirements 3.2
    """
    result = SurveyResult(score=None, input_method=None, is_skipped=True)
    assert result.is_skipped is True
    assert result.score is None


def test_survey_result_skipped_with_score_raises() -> None:
    """is_skipped=True + score is not None → ValueError"""
    with pytest.raises(ValueError):
        SurveyResult(score=3, input_method="voice", is_skipped=True)


@given(
    score=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=100)
def test_survey_result_score_requires_input_method(score: int) -> None:
    """**Property 3c: SurveyResult — score is not None → input_method is not None**

    Validates: Requirements 3.1
    """
    with pytest.raises(ValueError):
        SurveyResult(score=score, input_method=None, is_skipped=False)


@given(
    is_skipped=st.booleans(),
    score=st.one_of(st.none(), st.integers(min_value=-10, max_value=10)),
    input_method=st.one_of(st.none(), st.sampled_from(["voice", "dtmf"])),
)
@settings(max_examples=300)
def test_survey_result_invariant_property(
    is_skipped: bool,
    score: int | None,
    input_method: str | None,
) -> None:
    """**Property 3: SurveyResult 점수-건너뜀 일관성 (전체)**

    Validates: Requirements 3.1, 3.2
    """
    violates = (
        (not is_skipped and score is None)
        or (not is_skipped and score is not None and (score < 1 or score > 5))
        or (is_skipped and score is not None)
        or (score is not None and input_method is None)
    )

    if violates:
        with pytest.raises(ValueError):
            SurveyResult(score=score, input_method=input_method, is_skipped=is_skipped)
    else:
        result = SurveyResult(score=score, input_method=input_method, is_skipped=is_skipped)
        if not result.is_skipped:
            assert result.score is not None
            assert 1 <= result.score <= 5
        if result.is_skipped:
            assert result.score is None
        if result.score is not None:
            assert result.input_method is not None


# ---------------------------------------------------------------------------
# Property 2: AuthRequirement 인증 상태 유지 불변성
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

def test_auth_requirement_already_authenticated_requires_auth_false() -> None:
    """**Property 2: 인증 상태 유지 불변성**

    is_already_authenticated=True → requires_auth=False

    Validates: Requirements 2.3
    """
    result = AuthRequirement(
        requires_auth=False,
        is_already_authenticated=True,
        auth_type_hint=None,
    )
    assert result.is_already_authenticated is True
    assert result.requires_auth is False


def test_auth_requirement_already_authenticated_with_requires_auth_raises() -> None:
    """is_already_authenticated=True + requires_auth=True → ValueError"""
    with pytest.raises(ValueError):
        AuthRequirement(
            requires_auth=True,
            is_already_authenticated=True,
            auth_type_hint=None,
        )


@given(
    requires_auth=st.booleans(),
    is_already_authenticated=st.booleans(),
)
@settings(max_examples=200)
def test_auth_requirement_invariant_property(
    requires_auth: bool,
    is_already_authenticated: bool,
) -> None:
    """**Property 2: AuthRequirement 인증 상태 유지 불변성 (전체)**

    is_already_authenticated=True → requires_auth=False

    Validates: Requirements 2.3
    """
    violates = is_already_authenticated and requires_auth

    if violates:
        with pytest.raises(ValueError):
            AuthRequirement(
                requires_auth=requires_auth,
                is_already_authenticated=is_already_authenticated,
                auth_type_hint=None,
            )
    else:
        result = AuthRequirement(
            requires_auth=requires_auth,
            is_already_authenticated=is_already_authenticated,
            auth_type_hint=None,
        )
        if result.is_already_authenticated:
            assert result.requires_auth is False
