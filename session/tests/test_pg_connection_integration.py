"""통합 테스트 — 실제 PostgreSQL DB 필요 (pytest.mark.integration)

실행 방법:
    docker-compose up -d postgres
    uv run --with pytest --with psycopg2-binary --with alembic pytest \\
        callbot/session/tests/test_pg_connection_integration.py -v -m integration
"""
from __future__ import annotations

import os
import subprocess
import threading
import uuid
from datetime import datetime, timezone

import pytest

from callbot.session.enums import TurnType
from callbot.session.models import ConversationSession, ConversationTurn
from callbot.session.pg_connection import PostgreSQLConnection


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_session(session_id: str | None = None) -> ConversationSession:
    sid = session_id or str(uuid.uuid4())
    now = _now()
    return ConversationSession(
        session_id=sid,
        caller_id="010-0000-0000",
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
        expires_at=now,
    )


def _make_turn(session_id: str, turn_number: int = 1) -> ConversationTurn:
    return ConversationTurn(
        turn_id=str(uuid.uuid4()),
        session_id=session_id,
        turn_number=turn_number,
        turn_type=TurnType.BUSINESS,
        customer_utterance="안녕하세요",
        stt_confidence=0.95,
        intent="greeting",
        intent_confidence=0.9,
        entities=[],
        bot_response="안녕하세요, 무엇을 도와드릴까요?",
        llm_confidence=None,
        verification_status=None,
        response_time_ms=120,
        is_dtmf_input=False,
        is_barge_in=False,
        is_legal_required=False,
        masking_applied=False,
        masking_restore_success=True,
        unrestored_tokens=[],
        response_replaced_by_template=False,
        timestamp=_now(),
    )


# ---------------------------------------------------------------------------
# Task 7.2: Alembic upgrade / downgrade
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_alembic_upgrade_and_downgrade(migrated_db: str):
    """upgrade head → downgrade -1 이 오류 없이 동작한다."""
    env = {**os.environ, "CALLBOT_DB_DSN": migrated_db}
    result = subprocess.run(
        ["uv", "run", "--with", "alembic", "--with", "psycopg2-binary",
         "alembic", "downgrade", "-1"],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    # 다시 upgrade
    result = subprocess.run(
        ["uv", "run", "--with", "alembic", "--with", "psycopg2-binary",
         "alembic", "upgrade", "head"],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# Task 7.3: Session / Turn CRUD 라운드트립
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_session_crud_roundtrip(pg_connection: PostgreSQLConnection):
    """INSERT_SESSION → SELECT_SESSION 동등성 검증."""
    session = _make_session()
    pg_connection.execute("INSERT_SESSION", (session,))
    fetched = pg_connection.fetchone("SELECT_SESSION", (session.session_id,))
    assert fetched is not None
    assert fetched.session_id == session.session_id
    assert fetched.caller_id == session.caller_id
    assert fetched.is_authenticated == session.is_authenticated


@pytest.mark.integration
def test_turn_crud_roundtrip(pg_connection: PostgreSQLConnection):
    """세션 생성 후 INSERT_TURN → SELECT_TURNS 목록 포함 검증."""
    session = _make_session()
    pg_connection.execute("INSERT_SESSION", (session,))
    turn = _make_turn(session.session_id)
    pg_connection.execute("INSERT_TURN", (turn,))
    turns = pg_connection.fetchall("SELECT_TURNS", (session.session_id,))
    assert len(turns) == 1
    assert turns[0].turn_id == turn.turn_id
    assert turns[0].customer_utterance == turn.customer_utterance


# ---------------------------------------------------------------------------
# Task 7.4: FK 제약 및 SQL 인젝션 방어
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_fk_violation_raises_error(pg_connection: PostgreSQLConnection):
    """존재하지 않는 session_id로 턴 INSERT 시 예외 발생."""
    import psycopg2
    turn = _make_turn(session_id="nonexistent-session-id")
    with pytest.raises(psycopg2.Error):
        pg_connection.execute("INSERT_TURN", (turn,))


@pytest.mark.integration
def test_sql_injection_stored_as_literal(pg_connection: PostgreSQLConnection):
    """SQL 메타문자가 포함된 값이 리터럴로 저장/조회된다."""
    malicious = "'; DROP TABLE conversation_sessions; --"
    session = _make_session()
    # escalation_reason에 SQL 인젝션 시도 문자열 삽입
    object.__setattr__(session, "escalation_reason", malicious)
    pg_connection.execute("INSERT_SESSION", (session,))
    fetched = pg_connection.fetchone("SELECT_SESSION", (session.session_id,))
    assert fetched is not None
    assert fetched.escalation_reason == malicious


# ---------------------------------------------------------------------------
# Task 7.5: 커넥션 풀 동시 접근
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_concurrent_pool_access(pg_connection: PostgreSQLConnection):
    """스레드 기반 동시 쿼리 실행 후 연결 누수 없음."""
    sessions = [_make_session() for _ in range(5)]
    for s in sessions:
        pg_connection.execute("INSERT_SESSION", (s,))

    errors: list[Exception] = []
    semaphore_before = pg_connection._semaphore._value

    def fetch(sid: str) -> None:
        try:
            pg_connection.fetchone("SELECT_SESSION", (sid,))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=fetch, args=(s.session_id,)) for s in sessions]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"스레드 오류 발생: {errors}"
    assert pg_connection._semaphore._value == semaphore_before, "연결 누수 감지"
