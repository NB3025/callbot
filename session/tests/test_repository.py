"""callbot.session.tests.test_repository — CallbotDBRepository 단위 테스트

Validates: Requirements 1.6, 1.7, 4.1, 4.3, 4.4, 4.5
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from callbot.session.enums import AuthStatus, EndReason, TurnType
from callbot.session.models import ConversationSession, ConversationTurn
from callbot.session.repository import (
    CallbotDBRepository,
    DBOperationError,
    InMemoryDBConnection,
    SessionFKError,
)

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

NO_SLEEP = [0.0, 0.0, 0.0]  # 재시도 테스트 시 sleep 없이 빠르게 실행


def make_db() -> InMemoryDBConnection:
    return InMemoryDBConnection()


def make_repo(db: InMemoryDBConnection | None = None) -> tuple[CallbotDBRepository, InMemoryDBConnection]:
    if db is None:
        db = make_db()
    repo = CallbotDBRepository(db=db, retry_delays=NO_SLEEP)
    return repo, db


def make_session(session_id: str | None = None) -> ConversationSession:
    now = datetime.now()
    sid = session_id or str(uuid.uuid4())
    return ConversationSession(
        session_id=sid,
        caller_id="01012345678",
        customer_id=None,
        start_time=now,
        end_time=None,
        end_reason=None,
        is_authenticated=False,
        auth_method=None,
        business_turn_count=0,
        total_turn_count=0,
        tts_speed_factor=1.0,
        csat_score=None,
        escalation_reason=None,
        escalation_reasons=[],
        auth_attempts=[],
        created_at=now,
        updated_at=now,
        expires_at=now.replace(year=now.year + 1),
    )


def make_turn(session_id: str, turn_number: int = 1) -> ConversationTurn:
    return ConversationTurn(
        turn_id=str(uuid.uuid4()),
        session_id=session_id,
        turn_number=turn_number,
        turn_type=TurnType.BUSINESS,
        customer_utterance="테스트 발화",
        stt_confidence=0.9,
        intent=None,
        intent_confidence=0.8,
        entities=[],
        bot_response="테스트 응답",
        llm_confidence=None,
        verification_status=None,
        response_time_ms=100,
        is_dtmf_input=False,
        is_barge_in=False,
        is_legal_required=False,
        masking_applied=False,
        masking_restore_success=True,
        unrestored_tokens=[],
        response_replaced_by_template=False,
        timestamp=datetime.now(),
    )


# ---------------------------------------------------------------------------
# 기본 CRUD 테스트
# ---------------------------------------------------------------------------

def test_insert_session_stores_session() -> None:
    """insert_session() 후 get_session()으로 조회 가능하다."""
    repo, _ = make_repo()
    session = make_session()
    repo.insert_session(session)
    result = repo.get_session(session.session_id)
    assert result is not None
    assert result.session_id == session.session_id


def test_get_session_returns_none_for_unknown_id() -> None:
    """존재하지 않는 session_id 조회 시 None을 반환한다."""
    repo, _ = make_repo()
    assert repo.get_session("nonexistent") is None


def test_insert_turn_stores_turn() -> None:
    """insert_session() 후 insert_turn() 호출 시 턴이 저장된다."""
    repo, _ = make_repo()
    session = make_session()
    repo.insert_session(session)
    turn = make_turn(session.session_id)
    repo.insert_turn(turn)
    turns = repo.get_turns(session.session_id)
    assert len(turns) == 1
    assert turns[0].turn_id == turn.turn_id


def test_get_turns_returns_empty_for_unknown_session() -> None:
    """존재하지 않는 session_id의 턴 조회 시 빈 리스트를 반환한다."""
    repo, _ = make_repo()
    assert repo.get_turns("nonexistent") == []


def test_update_session_updates_end_time_and_reason() -> None:
    """update_session()은 end_time과 end_reason을 업데이트한다."""
    repo, _ = make_repo()
    session = make_session()
    repo.insert_session(session)

    end_time = datetime.now()
    repo.update_session(session.session_id, {"end_time": end_time, "end_reason": EndReason.NORMAL})

    result = repo.get_session(session.session_id)
    assert result.end_time == end_time
    assert result.end_reason == EndReason.NORMAL


# ---------------------------------------------------------------------------
# 9.1 DB 저장 재시도 단위 테스트 (Validates: Requirements 4.3, 4.4)
# ---------------------------------------------------------------------------

def test_insert_turn_retries_on_failure_then_succeeds() -> None:
    """insert_turn() 1회 실패 후 재시도 성공 테스트.

    Validates: Requirements 4.3
    """
    db = make_db()
    repo = CallbotDBRepository(db=db, retry_delays=NO_SLEEP)
    session = make_session()
    repo.insert_session(session)

    # 다음 1번 execute() 실패 → 재시도 시 성공
    db.fail_next_n = 1
    turn = make_turn(session.session_id)
    repo.insert_turn(turn)  # 예외 없이 성공해야 함

    turns = repo.get_turns(session.session_id)
    assert len(turns) == 1


def test_insert_turn_fails_after_max_retries() -> None:
    """insert_turn() 3회 모두 실패 시 DBOperationError 발생.

    Validates: Requirements 4.4
    """
    db = make_db()
    repo = CallbotDBRepository(db=db, retry_delays=NO_SLEEP)
    session = make_session()
    repo.insert_session(session)

    # 3번 모두 실패
    db.fail_next_n = 3
    turn = make_turn(session.session_id)

    with pytest.raises(DBOperationError):
        repo.insert_turn(turn)


# ---------------------------------------------------------------------------
# 9.2 세션-턴 FK 제약 단위 테스트 (Validates: Requirements 4.5)
# ---------------------------------------------------------------------------

def test_insert_turn_without_session_raises_fk_error() -> None:
    """insert_session() 없이 insert_turn() 호출 시 SessionFKError 발생.

    Validates: Requirements 4.5
    """
    repo, _ = make_repo()
    turn = make_turn(session_id=str(uuid.uuid4()))

    with pytest.raises(SessionFKError):
        repo.insert_turn(turn)


def test_insert_multiple_turns_preserves_order() -> None:
    """여러 턴 삽입 시 순서가 보존된다."""
    repo, _ = make_repo()
    session = make_session()
    repo.insert_session(session)

    for i in range(1, 4):
        repo.insert_turn(make_turn(session.session_id, turn_number=i))

    turns = repo.get_turns(session.session_id)
    assert len(turns) == 3
    assert [t.turn_number for t in turns] == [1, 2, 3]
