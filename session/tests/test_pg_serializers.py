"""test_pg_serializers.py — Property 3 & 4: 직렬화 라운드트립 PBT"""
from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.session.enums import AuthType, EndReason, TurnType
from callbot.session.models import AuthAttempt, ConversationSession, ConversationTurn
from callbot.session.pg_serializers import (
    row_to_session,
    row_to_turn,
    session_to_row,
    turn_to_row,
)

# ---------------------------------------------------------------------------
# Hypothesis 전략
# ---------------------------------------------------------------------------

_dt = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2099, 12, 31),
    timezones=st.just(timezone.utc),
)
_opt_dt = st.one_of(st.none(), _dt)
_text = st.text(max_size=64)
_opt_text = st.one_of(st.none(), _text)

_auth_attempt = st.builds(
    AuthAttempt,
    auth_type=st.sampled_from(AuthType),
    is_success=st.booleans(),
    attempted_at=_dt,
)

_session = st.builds(
    ConversationSession,
    session_id=_text,
    caller_id=_text,
    customer_id=_opt_text,
    start_time=_dt,
    end_time=_opt_dt,
    end_reason=st.one_of(st.none(), st.sampled_from(EndReason)),
    is_authenticated=st.booleans(),
    auth_method=st.one_of(st.none(), st.sampled_from(AuthType)),
    business_turn_count=st.integers(min_value=0, max_value=100),
    total_turn_count=st.integers(min_value=0, max_value=100),
    tts_speed_factor=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
    csat_score=st.one_of(st.none(), st.integers(min_value=1, max_value=5)),
    escalation_reason=_opt_text,
    escalation_reasons=st.lists(st.text(max_size=32), max_size=5),
    auth_attempts=st.lists(_auth_attempt, max_size=3),
    created_at=_dt,
    updated_at=_dt,
    expires_at=_dt,
)

_turn = st.builds(
    ConversationTurn,
    turn_id=_text,
    session_id=_text,
    turn_number=st.integers(min_value=0, max_value=100),
    turn_type=st.sampled_from(TurnType),
    customer_utterance=_text,
    stt_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    intent=_opt_text,
    intent_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    entities=st.lists(st.text(max_size=16), max_size=5),
    bot_response=_text,
    llm_confidence=st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
    verification_status=_opt_text,
    response_time_ms=st.integers(min_value=0, max_value=10000),
    is_dtmf_input=st.booleans(),
    is_barge_in=st.booleans(),
    is_legal_required=st.booleans(),
    masking_applied=st.booleans(),
    masking_restore_success=st.booleans(),
    unrestored_tokens=st.lists(st.text(max_size=16), max_size=5),
    response_replaced_by_template=st.booleans(),
    timestamp=_dt,
)


# ---------------------------------------------------------------------------
# Property 3: ConversationSession 라운드트립
# ---------------------------------------------------------------------------

@given(_session)
@settings(max_examples=100)
def test_session_serialization_roundtrip(session: ConversationSession):
    """Property 3: session_to_row → row_to_session 후 원본과 동등해야 한다."""
    row = session_to_row(session)
    restored = row_to_session(row)
    assert restored == session


# ---------------------------------------------------------------------------
# Property 4: ConversationTurn 라운드트립
# ---------------------------------------------------------------------------

@given(_turn)
@settings(max_examples=100)
def test_turn_serialization_roundtrip(turn: ConversationTurn):
    """Property 4: turn_to_row → row_to_turn 후 원본과 동등해야 한다."""
    row = turn_to_row(turn)
    restored = row_to_turn(row)
    assert restored == turn
