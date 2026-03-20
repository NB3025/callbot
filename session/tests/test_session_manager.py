"""callbot.session.tests.test_session_manager — 세션 생성 및 턴 업데이트 단위 테스트

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 3.2, 4.2
"""
from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.session.enums import AuthStatus, EndReason, TurnType
from callbot.session.exceptions import SessionNotFoundError
from callbot.session.models import ConversationTurn, SessionContext, Turn
from callbot.session.repository import CallbotDBRepository
from callbot.session.session_manager import SessionManager
from callbot.session.session_store import InMemorySessionStore


def make_manager() -> tuple[SessionManager, MagicMock, InMemorySessionStore]:
    """SessionManager, mock repository, InMemorySessionStore를 함께 반환."""
    mock_repo = MagicMock(spec=CallbotDBRepository)
    store = InMemorySessionStore()
    manager = SessionManager(repository=mock_repo, session_store=store)
    return manager, mock_repo, store


# ---------------------------------------------------------------------------
# create_session() 단위 테스트
# ---------------------------------------------------------------------------

def test_create_session_returns_session_context() -> None:
    """create_session()은 SessionContext를 반환한다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert isinstance(result, SessionContext)


def test_create_session_returns_uuid_format_session_id() -> None:
    """create_session()의 session_id는 UUID 형식이다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    # UUID 파싱이 성공하면 유효한 UUID 형식
    parsed = uuid.UUID(result.session_id)
    assert str(parsed) == result.session_id


def test_create_session_initial_business_turn_count_is_zero() -> None:
    """새로 생성된 SessionContext의 business_turn_count는 0이다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert result.business_turn_count == 0


def test_create_session_initial_is_authenticated_is_false() -> None:
    """새로 생성된 SessionContext의 is_authenticated는 False이다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert result.is_authenticated is False


def test_create_session_initial_injection_detection_count_is_zero() -> None:
    """새로 생성된 SessionContext의 injection_detection_count는 0이다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert result.injection_detection_count == 0


def test_create_session_initial_masking_restore_failure_count_is_zero() -> None:
    """새로 생성된 SessionContext의 masking_restore_failure_count는 0이다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert result.masking_restore_failure_count == 0


def test_create_session_initial_tts_speed_factor_is_one() -> None:
    """새로 생성된 SessionContext의 tts_speed_factor는 1.0이다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert result.tts_speed_factor == 1.0


def test_create_session_initial_turns_is_empty() -> None:
    """새로 생성된 SessionContext의 turns는 빈 리스트이다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert result.turns == []


def test_create_session_initial_auth_status_is_not_attempted() -> None:
    """새로 생성된 SessionContext의 auth_status는 NOT_ATTEMPTED이다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert result.auth_status == AuthStatus.NOT_ATTEMPTED


def test_create_session_initial_optional_fields_are_none() -> None:
    """새로 생성된 SessionContext의 선택적 필드들은 None이다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert result.cached_billing_data is None
    assert result.plan_list_context is None
    assert result.pending_intent is None
    assert result.pending_classification is None
    assert result.customer_info is None


def test_create_session_stores_caller_id() -> None:
    """create_session()은 caller_id를 SessionContext에 저장한다."""
    manager, _, _ = make_manager()
    result = manager.create_session(caller_id="01099998888")
    assert result.caller_id == "01099998888"


def test_create_session_calls_repository_insert_session() -> None:
    """create_session()은 repository.insert_session()을 호출한다."""
    manager, mock_repo, _ = make_manager()
    manager.create_session(caller_id="01012345678")
    mock_repo.insert_session.assert_called_once()


def test_create_session_each_call_generates_unique_session_id() -> None:
    """create_session() 호출마다 고유한 session_id가 생성된다."""
    manager, _, _ = make_manager()
    s1 = manager.create_session(caller_id="01011111111")
    s2 = manager.create_session(caller_id="01022222222")
    assert s1.session_id != s2.session_id


def test_create_session_stores_session_in_memory() -> None:
    """create_session()은 세션을 내부 저장소에 저장한다."""
    manager, _, store = make_manager()
    result = manager.create_session(caller_id="01012345678")
    assert store.exists(result.session_id)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def make_turn(turn_type: TurnType = TurnType.BUSINESS) -> Turn:
    """최소한의 유효한 Turn 객체 생성 헬퍼."""
    return Turn(
        turn_id=str(uuid.uuid4()),
        turn_type=turn_type,
        customer_utterance="테스트 발화",
        bot_response="테스트 응답",
        intent=None,
        entities=[],
        stt_confidence=0.9,
        intent_confidence=0.8,
        llm_confidence=None,
        verification_status=None,
        response_time_ms=100,
        is_dtmf_input=False,
        is_barge_in=False,
        timestamp=datetime.now(),
    )


# ---------------------------------------------------------------------------
# 4.1 업무 턴 카운트 단위 테스트 (Validates: Requirements 1.3, 1.4)
# ---------------------------------------------------------------------------

def test_update_turn_business_increments_count_by_one() -> None:
    """update_turn(BUSINESS) 호출 시 business_turn_count가 정확히 1 증가한다."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    before = ctx.business_turn_count

    manager.update_turn(ctx.session_id, make_turn(TurnType.BUSINESS))

    assert ctx.business_turn_count == before + 1


def test_update_turn_system_does_not_change_count() -> None:
    """update_turn(SYSTEM) 호출 시 business_turn_count가 변하지 않는다."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    before = ctx.business_turn_count

    manager.update_turn(ctx.session_id, make_turn(TurnType.SYSTEM))

    assert ctx.business_turn_count == before


def test_update_turn_multiple_business_turns_accumulate() -> None:
    """여러 BUSINESS 턴 호출 시 business_turn_count가 누적된다."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")

    for _ in range(5):
        manager.update_turn(ctx.session_id, make_turn(TurnType.BUSINESS))

    assert ctx.business_turn_count == 5


def test_update_turn_mixed_turns_only_business_counted() -> None:
    """BUSINESS/SYSTEM 혼합 시 BUSINESS 턴만 카운트된다."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")

    manager.update_turn(ctx.session_id, make_turn(TurnType.BUSINESS))
    manager.update_turn(ctx.session_id, make_turn(TurnType.SYSTEM))
    manager.update_turn(ctx.session_id, make_turn(TurnType.BUSINESS))
    manager.update_turn(ctx.session_id, make_turn(TurnType.SYSTEM))
    manager.update_turn(ctx.session_id, make_turn(TurnType.BUSINESS))

    assert ctx.business_turn_count == 3


# ---------------------------------------------------------------------------
# 4.2 미존재 세션 오류 단위 테스트 (Validates: Requirements 3.2)
# ---------------------------------------------------------------------------

def test_update_turn_nonexistent_session_raises_session_not_found_error() -> None:
    """존재하지 않는 session_id로 update_turn() 호출 시 SessionNotFoundError가 발생한다."""
    manager, _, _ = make_manager()

    with pytest.raises(SessionNotFoundError) as exc_info:
        manager.update_turn("nonexistent-session-id", make_turn())

    assert exc_info.value.session_id == "nonexistent-session-id"


# ---------------------------------------------------------------------------
# 4.3 턴 저장 순서 속성 테스트 (Validates: Requirements 4.2)
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(n=st.integers(min_value=1, max_value=20))
def test_turn_number_sequence_matches_call_order(n: int) -> None:
    """Property 5: N번 update_turn() 호출 후 ConversationTurn.turn_number가 호출 순서(1..N)와 일치한다.

    Validates: Requirements 4.2
    """
    manager, mock_repo, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")

    for _ in range(n):
        manager.update_turn(ctx.session_id, make_turn())

    # insert_turn 호출 횟수 확인
    assert mock_repo.insert_turn.call_count == n

    # 각 호출에서 전달된 ConversationTurn의 turn_number가 순서대로 1, 2, ..., N인지 확인
    for i, call in enumerate(mock_repo.insert_turn.call_args_list, start=1):
        db_turn: ConversationTurn = call.args[0]
        assert db_turn.turn_number == i


# ---------------------------------------------------------------------------
# 5.1 제한 확인 경계값 단위 테스트 (Validates: Requirements 2.2, 2.3)
# ---------------------------------------------------------------------------

from datetime import timedelta


def test_check_limits_17_turns_no_warning_no_limit() -> None:
    """17턴 → is_warning_needed=False, is_limit_reached=False."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    ctx.business_turn_count = 17

    status = manager.check_limits(ctx.session_id)

    assert status.is_warning_needed is False
    assert status.is_limit_reached is False


def test_check_limits_18_turns_warning_no_limit() -> None:
    """18턴 → is_warning_needed=True, is_limit_reached=False."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    ctx.business_turn_count = 18

    status = manager.check_limits(ctx.session_id)

    assert status.is_warning_needed is True
    assert status.is_limit_reached is False


def test_check_limits_19_turns_warning_no_limit() -> None:
    """19턴 → is_warning_needed=True, is_limit_reached=False."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    ctx.business_turn_count = 19

    status = manager.check_limits(ctx.session_id)

    assert status.is_warning_needed is True
    assert status.is_limit_reached is False


def test_check_limits_20_turns_warning_and_limit() -> None:
    """20턴 → is_warning_needed=True, is_limit_reached=True."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    ctx.business_turn_count = 20

    status = manager.check_limits(ctx.session_id)

    assert status.is_warning_needed is True
    assert status.is_limit_reached is True


def test_check_limits_12_minutes_no_warning() -> None:
    """12분 경과 → is_warning_needed=False."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    ctx.start_time = datetime.now() - timedelta(minutes=12)

    status = manager.check_limits(ctx.session_id)

    assert status.is_warning_needed is False


def test_check_limits_13_minutes_warning() -> None:
    """13분 경과 → is_warning_needed=True."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    ctx.start_time = datetime.now() - timedelta(minutes=13)

    status = manager.check_limits(ctx.session_id)

    assert status.is_warning_needed is True


def test_check_limits_15_minutes_limit_reached() -> None:
    """15분 경과 → is_limit_reached=True."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    ctx.start_time = datetime.now() - timedelta(minutes=15)

    status = manager.check_limits(ctx.session_id)

    assert status.is_limit_reached is True


def test_check_limits_nonexistent_session_raises_error() -> None:
    """존재하지 않는 session_id로 check_limits() 호출 시 SessionNotFoundError 발생."""
    manager, _, _ = make_manager()

    with pytest.raises(SessionNotFoundError):
        manager.check_limits("nonexistent-session-id")


# ---------------------------------------------------------------------------
# 5.2 SessionLimitStatus 불변 조건 단위 테스트 (Validates: Requirements 2.4)
# ---------------------------------------------------------------------------

def test_check_limits_limit_reached_implies_warning_needed() -> None:
    """is_limit_reached=True이면 반드시 is_warning_needed=True이다."""
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    ctx.business_turn_count = 20

    status = manager.check_limits(ctx.session_id)

    assert status.is_limit_reached is True
    assert status.is_warning_needed is True


# ---------------------------------------------------------------------------
# 6.1 세션 종료 후 불변성 단위 테스트 (Validates: Requirements 1.5, 1.6, 1.7, 3.3)
# ---------------------------------------------------------------------------

def test_end_session_update_turn_raises_session_not_found_error() -> None:
    """end_session() 후 동일 session_id로 update_turn() 호출 시 SessionNotFoundError 발생.

    Validates: Requirements 1.5, 3.3
    """
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    manager.end_session(ctx.session_id, EndReason.NORMAL)

    with pytest.raises(SessionNotFoundError):
        manager.update_turn(ctx.session_id, make_turn())


def test_end_session_check_limits_raises_session_not_found_error() -> None:
    """end_session() 후 동일 session_id로 check_limits() 호출 시 SessionNotFoundError 발생.

    Validates: Requirements 1.5, 3.3
    """
    manager, _, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    manager.end_session(ctx.session_id, EndReason.NORMAL)

    with pytest.raises(SessionNotFoundError):
        manager.check_limits(ctx.session_id)


def test_end_session_removes_session_from_sessions_dict() -> None:
    """end_session() 후 session_id가 저장소에 존재하지 않는다.

    Validates: Requirements 3.3
    """
    manager, _, store = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    assert store.exists(ctx.session_id)

    manager.end_session(ctx.session_id, EndReason.NORMAL)

    assert not store.exists(ctx.session_id)


def test_end_session_calls_repository_update_session_with_correct_session_id() -> None:
    """end_session()은 repository.update_session()을 올바른 session_id로 호출한다.

    Validates: Requirements 1.7
    """
    manager, mock_repo, _ = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    manager.end_session(ctx.session_id, EndReason.NORMAL)

    mock_repo.update_session.assert_called_once()
    call_args = mock_repo.update_session.call_args
    assert call_args.args[0] == ctx.session_id


def test_end_session_nonexistent_session_raises_session_not_found_error() -> None:
    """존재하지 않는 session_id로 end_session() 호출 시 SessionNotFoundError 발생.

    Validates: Requirements 3.3
    """
    manager, _, _ = make_manager()

    with pytest.raises(SessionNotFoundError):
        manager.end_session("nonexistent-session-id", EndReason.NORMAL)


# ---------------------------------------------------------------------------
# 8.1 세션 격리 속성 테스트 (Validates: Requirements 3.1)
# ---------------------------------------------------------------------------

def test_session_isolation_update_turn_does_not_affect_other_session() -> None:
    """s1에 3번 BUSINESS 턴 업데이트 후 s2의 business_turn_count와 turns는 변하지 않는다.

    Validates: Requirements 3.1
    """
    manager, _, _ = make_manager()
    s1 = manager.create_session(caller_id="01011111111")
    s2 = manager.create_session(caller_id="01022222222")

    for _ in range(3):
        manager.update_turn(s1.session_id, make_turn(TurnType.BUSINESS))

    assert s2.business_turn_count == 0
    assert len(s2.turns) == 0


def test_session_isolation_end_session_does_not_affect_other_session() -> None:
    """s1 종료 후 s2는 여전히 접근 가능하고, s1은 SessionNotFoundError를 발생시킨다.

    Validates: Requirements 3.1
    """
    manager, _, _ = make_manager()
    s1 = manager.create_session(caller_id="01011111111")
    s2 = manager.create_session(caller_id="01022222222")

    manager.end_session(s1.session_id, EndReason.NORMAL)

    # s2는 여전히 접근 가능
    status = manager.check_limits(s2.session_id)
    assert status is not None

    # s1은 접근 불가
    with pytest.raises(SessionNotFoundError):
        manager.check_limits(s1.session_id)


@settings(max_examples=50)
@given(n=st.integers(min_value=1, max_value=10))
def test_property_session_isolation(n: int) -> None:
    """Property 4: s1에 n번 BUSINESS 턴 적용 후 s2의 business_turn_count는 0이고, s1은 n이다.

    Validates: Requirements 3.1
    """
    manager, _, _ = make_manager()
    s1 = manager.create_session(caller_id="01011111111")
    s2 = manager.create_session(caller_id="01022222222")

    for _ in range(n):
        manager.update_turn(s1.session_id, make_turn(TurnType.BUSINESS))

    assert s2.business_turn_count == 0
    assert s1.business_turn_count == n


# ---------------------------------------------------------------------------
# 10.3 Property 6: SessionManager 저장소 교체 호환성 (Validates: Requirements 6.4, 6.6)
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    n_business=st.integers(min_value=0, max_value=5),
    n_system=st.integers(min_value=0, max_value=5),
)
def test_property_store_replacement_compatibility(n_business: int, n_system: int) -> None:
    """Property 6: InMemorySessionStore 주입 후 create → update_turn → check_limits → end_session
    시퀀스가 기존 동작과 동일하게 작동한다.

    Validates: Requirements 6.4, 6.6
    """
    manager, _, store = make_manager()

    # 1. create_session
    ctx = manager.create_session(caller_id="01012345678")
    assert store.exists(ctx.session_id)
    assert ctx.business_turn_count == 0

    # 2. update_turn (business + system)
    for _ in range(n_business):
        manager.update_turn(ctx.session_id, make_turn(TurnType.BUSINESS))
    for _ in range(n_system):
        manager.update_turn(ctx.session_id, make_turn(TurnType.SYSTEM))

    assert ctx.business_turn_count == n_business
    assert len(ctx.turns) == n_business + n_system

    # 3. check_limits
    status = manager.check_limits(ctx.session_id)
    assert status.current_business_turns == n_business

    # 4. end_session
    manager.end_session(ctx.session_id, EndReason.NORMAL)
    assert not store.exists(ctx.session_id)

    # 5. 종료 후 접근 불가
    with pytest.raises(SessionNotFoundError):
        manager.update_turn(ctx.session_id, make_turn())
