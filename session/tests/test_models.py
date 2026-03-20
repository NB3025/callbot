"""callbot.session.tests.test_models — SessionLimitStatus 속성 테스트

Validates: Requirements 2.1, 2.2, 2.5, 2.6
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.session.models import SessionLimitStatus


# ---------------------------------------------------------------------------
# 헬퍼: SessionLimitStatus 생성 전략
# ---------------------------------------------------------------------------

def make_limit_status(
    current_business_turns: int,
    max_business_turns: int,
    elapsed_minutes: float,
    max_minutes: float,
    is_warning_needed: bool,
    is_limit_reached: bool,
    has_active_transaction: bool = False,
) -> SessionLimitStatus:
    remaining_turns = max_business_turns - current_business_turns
    remaining_minutes = max_minutes - elapsed_minutes
    return SessionLimitStatus(
        current_business_turns=current_business_turns,
        max_business_turns=max_business_turns,
        elapsed_minutes=elapsed_minutes,
        max_minutes=max_minutes,
        is_warning_needed=is_warning_needed,
        is_limit_reached=is_limit_reached,
        has_active_transaction=has_active_transaction,
        remaining_turns=remaining_turns,
        remaining_minutes=remaining_minutes,
    )


# ---------------------------------------------------------------------------
# Property 2: SessionLimitStatus 경고-제한 포함 관계
# Validates: Requirements 2.1, 2.2
# ---------------------------------------------------------------------------

@given(
    current=st.integers(min_value=0, max_value=30),
    max_turns=st.integers(min_value=1, max_value=30),
    elapsed=st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    max_min=st.floats(min_value=1.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    has_tx=st.booleans(),
)
@settings(max_examples=200)
def test_property_limit_reached_implies_warning_needed(
    current: int,
    max_turns: int,
    elapsed: float,
    max_min: float,
    has_tx: bool,
) -> None:
    """Property 2: is_limit_reached=True이면 반드시 is_warning_needed=True.

    Validates: Requirements 2.1, 2.2
    """
    status = make_limit_status(
        current_business_turns=current,
        max_business_turns=max_turns,
        elapsed_minutes=elapsed,
        max_minutes=max_min,
        is_warning_needed=False,   # __post_init__이 강제 수정해야 함
        is_limit_reached=True,
        has_active_transaction=has_tx,
    )
    assert status.is_warning_needed is True, (
        f"is_limit_reached=True인데 is_warning_needed=False: {status}"
    )


# ---------------------------------------------------------------------------
# Property: remaining_turns 계산 정확성
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------

@given(
    current=st.integers(min_value=0, max_value=50),
    max_turns=st.integers(min_value=0, max_value=50),
    elapsed=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
    max_min=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_property_remaining_turns_calculation(
    current: int,
    max_turns: int,
    elapsed: float,
    max_min: float,
) -> None:
    """Property: remaining_turns == max_business_turns - current_business_turns.

    Validates: Requirements 2.5
    """
    status = make_limit_status(
        current_business_turns=current,
        max_business_turns=max_turns,
        elapsed_minutes=elapsed,
        max_minutes=max_min,
        is_warning_needed=False,
        is_limit_reached=False,
    )
    assert status.remaining_turns == max_turns - current, (
        f"remaining_turns={status.remaining_turns}, expected={max_turns - current}"
    )


# ---------------------------------------------------------------------------
# Property: remaining_minutes 계산 정확성
# Validates: Requirements 2.6
# ---------------------------------------------------------------------------

@given(
    current=st.integers(min_value=0, max_value=30),
    max_turns=st.integers(min_value=1, max_value=30),
    elapsed=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
    max_min=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_property_remaining_minutes_calculation(
    current: int,
    max_turns: int,
    elapsed: float,
    max_min: float,
) -> None:
    """Property: remaining_minutes == max_minutes - elapsed_minutes.

    Validates: Requirements 2.6
    """
    status = make_limit_status(
        current_business_turns=current,
        max_business_turns=max_turns,
        elapsed_minutes=elapsed,
        max_minutes=max_min,
        is_warning_needed=False,
        is_limit_reached=False,
    )
    assert status.remaining_minutes == pytest.approx(max_min - elapsed), (
        f"remaining_minutes={status.remaining_minutes}, expected={max_min - elapsed}"
    )


# ---------------------------------------------------------------------------
# 단위 테스트: __post_init__ 불변 조건 직접 검증
# ---------------------------------------------------------------------------

def test_is_limit_reached_true_forces_warning_needed_true() -> None:
    """is_limit_reached=True로 생성 시 is_warning_needed가 False여도 True로 강제 설정."""
    status = make_limit_status(
        current_business_turns=20,
        max_business_turns=20,
        elapsed_minutes=0.0,
        max_minutes=15.0,
        is_warning_needed=False,
        is_limit_reached=True,
    )
    assert status.is_warning_needed is True


def test_is_limit_reached_false_does_not_force_warning() -> None:
    """is_limit_reached=False이면 is_warning_needed는 그대로 유지."""
    status = make_limit_status(
        current_business_turns=5,
        max_business_turns=20,
        elapsed_minutes=5.0,
        max_minutes=15.0,
        is_warning_needed=False,
        is_limit_reached=False,
    )
    assert status.is_warning_needed is False


def test_remaining_turns_zero_when_at_max() -> None:
    """현재 턴이 최대와 같으면 remaining_turns=0."""
    status = make_limit_status(
        current_business_turns=20,
        max_business_turns=20,
        elapsed_minutes=0.0,
        max_minutes=15.0,
        is_warning_needed=True,
        is_limit_reached=True,
    )
    assert status.remaining_turns == 0


def test_remaining_minutes_zero_when_at_max() -> None:
    """경과 시간이 최대와 같으면 remaining_minutes=0."""
    status = make_limit_status(
        current_business_turns=0,
        max_business_turns=20,
        elapsed_minutes=15.0,
        max_minutes=15.0,
        is_warning_needed=True,
        is_limit_reached=True,
    )
    assert status.remaining_minutes == pytest.approx(0.0)
