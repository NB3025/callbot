"""callbot.session.tests.test_integration — 세션 모듈 통합 테스트

Validates: Requirements 1.1, 3.1, 4.3
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from callbot.session import (
    CallbotDBRepository,
    ConversationTurn,
    EndReason,
    InMemoryDBConnection,
    InMemorySessionStore,
    SessionManager,
    SessionNotFoundError,
    TurnType,
    Turn,
)
from callbot.session.repository import DBOperationError


NO_SLEEP = [0.0, 0.0, 0.0]


def make_turn(turn_type: TurnType = TurnType.BUSINESS) -> Turn:
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


def make_stack() -> tuple[SessionManager, CallbotDBRepository, InMemoryDBConnection]:
    db = InMemoryDBConnection()
    repo = CallbotDBRepository(db=db, retry_delays=NO_SLEEP)
    store = InMemorySessionStore()
    manager = SessionManager(repository=repo, session_store=store)
    return manager, repo, db


# ---------------------------------------------------------------------------
# 전체 흐름 통합 테스트 (Validates: Requirements 1.1)
# ---------------------------------------------------------------------------

def test_full_session_lifecycle() -> None:
    """세션 생성 → 업무 턴 N회 업데이트 → 제한 확인 → 세션 종료 전체 흐름."""
    manager, repo, db = make_stack()

    # 1. 세션 생성
    ctx = manager.create_session(caller_id="01012345678")
    assert ctx.business_turn_count == 0
    assert repo.get_session(ctx.session_id) is not None

    # 2. 업무 턴 5회 업데이트
    for _ in range(5):
        manager.update_turn(ctx.session_id, make_turn(TurnType.BUSINESS))

    assert ctx.business_turn_count == 5
    turns_in_db = repo.get_turns(ctx.session_id)
    assert len(turns_in_db) == 5

    # 3. 시스템 턴 1회 (카운트 불변)
    manager.update_turn(ctx.session_id, make_turn(TurnType.SYSTEM))
    assert ctx.business_turn_count == 5
    assert len(repo.get_turns(ctx.session_id)) == 6

    # 4. 제한 확인
    status = manager.check_limits(ctx.session_id)
    assert status.current_business_turns == 5
    assert status.is_warning_needed is False
    assert status.is_limit_reached is False

    # 5. 세션 종료
    manager.end_session(ctx.session_id, EndReason.NORMAL)

    # 종료 후 접근 불가
    with pytest.raises(SessionNotFoundError):
        manager.update_turn(ctx.session_id, make_turn())

    # DB에는 end_time, end_reason이 기록됨
    db_session = repo.get_session(ctx.session_id)
    assert db_session.end_time is not None
    assert db_session.end_reason == EndReason.NORMAL


def test_turn_number_sequence_in_db() -> None:
    """DB에 저장된 ConversationTurn의 turn_number가 1부터 순서대로 증가한다."""
    manager, repo, db = make_stack()
    ctx = manager.create_session(caller_id="01012345678")

    for _ in range(4):
        manager.update_turn(ctx.session_id, make_turn())

    turns = repo.get_turns(ctx.session_id)
    assert [t.turn_number for t in turns] == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# 동시 세션 격리 통합 테스트 (Validates: Requirements 3.1)
# ---------------------------------------------------------------------------

def test_concurrent_session_isolation() -> None:
    """두 세션이 동일한 manager/repo를 공유해도 데이터가 완전히 격리된다."""
    manager, repo, db = make_stack()

    s1 = manager.create_session(caller_id="01011111111")
    s2 = manager.create_session(caller_id="01022222222")

    # s1에 3턴, s2에 7턴
    for _ in range(3):
        manager.update_turn(s1.session_id, make_turn(TurnType.BUSINESS))
    for _ in range(7):
        manager.update_turn(s2.session_id, make_turn(TurnType.BUSINESS))

    assert s1.business_turn_count == 3
    assert s2.business_turn_count == 7

    assert len(repo.get_turns(s1.session_id)) == 3
    assert len(repo.get_turns(s2.session_id)) == 7

    # s1 종료 후 s2는 여전히 정상
    manager.end_session(s1.session_id, EndReason.NORMAL)

    status = manager.check_limits(s2.session_id)
    assert status.current_business_turns == 7

    with pytest.raises(SessionNotFoundError):
        manager.check_limits(s1.session_id)


# ---------------------------------------------------------------------------
# DB 저장 실패 재시도 통합 테스트 (Validates: Requirements 4.3)
# ---------------------------------------------------------------------------

def test_db_retry_on_insert_turn_failure_then_success() -> None:
    """insert_turn() 1회 실패 후 재시도 성공 시 세션 상태는 정상 유지된다."""
    db = InMemoryDBConnection()
    repo = CallbotDBRepository(db=db, retry_delays=NO_SLEEP)
    manager = SessionManager(repository=repo, session_store=InMemorySessionStore())

    ctx = manager.create_session(caller_id="01012345678")

    # 다음 execute() 1회 실패 → 재시도 성공
    db.fail_next_n = 1
    manager.update_turn(ctx.session_id, make_turn(TurnType.BUSINESS))

    assert ctx.business_turn_count == 1
    assert len(repo.get_turns(ctx.session_id)) == 1


def test_db_retry_exhausted_raises_error() -> None:
    """insert_turn() 3회 모두 실패 시 DBOperationError가 발생한다."""
    db = InMemoryDBConnection()
    repo = CallbotDBRepository(db=db, retry_delays=NO_SLEEP)
    manager = SessionManager(repository=repo, session_store=InMemorySessionStore())

    ctx = manager.create_session(caller_id="01012345678")

    db.fail_next_n = 3
    with pytest.raises(DBOperationError):
        manager.update_turn(ctx.session_id, make_turn(TurnType.BUSINESS))


# ---------------------------------------------------------------------------
# 공개 API import 검증
# ---------------------------------------------------------------------------

def test_public_api_imports_work() -> None:
    """callbot.session 패키지에서 모든 공개 심볼을 import할 수 있다."""
    from callbot.session import (
        AuthAttempt,
        AuthStatus,
        AuthType,
        CallbotDBRepository,
        ConversationSession,
        ConversationTurn,
        DBConnectionBase,
        DBOperationError,
        EndReason,
        InMemoryDBConnection,
        PlanListContext,
        SessionContext,
        SessionFKError,
        SessionLimitStatus,
        SessionManager,
        SessionNotFoundError,
        Turn,
        TurnType,
    )
    # 모든 심볼이 None이 아님을 확인
    assert all([
        SessionManager, CallbotDBRepository, SessionContext,
        SessionLimitStatus, Turn, ConversationSession, ConversationTurn,
        TurnType, EndReason, AuthStatus, AuthType, SessionNotFoundError,
        DBConnectionBase, InMemoryDBConnection, DBOperationError,
        SessionFKError, PlanListContext, AuthAttempt,
    ])
