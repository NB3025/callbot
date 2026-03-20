"""callbot.session.pg_serializers — ConversationSession/Turn 직렬화 함수"""
from __future__ import annotations

import json
from typing import Any, Optional

from callbot.session.enums import AuthType, EndReason, TurnType
from callbot.session.models import AuthAttempt, ConversationSession, ConversationTurn


def _enum_val(v: Any) -> Optional[str]:
    return v.value if v is not None else None


def _to_json(v: Any) -> str:
    return json.dumps(v)


def _from_json(v: Any) -> Any:
    if isinstance(v, str):
        return json.loads(v)
    return v  # psycopg2 JSONB는 이미 dict/list로 반환될 수 있음


# ---------------------------------------------------------------------------
# ConversationSession
# ---------------------------------------------------------------------------

def session_to_row(session: ConversationSession) -> dict:
    """ConversationSession → DB row dict."""
    return {
        "session_id": session.session_id,
        "caller_id": session.caller_id,
        "customer_id": session.customer_id,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "end_reason": _enum_val(session.end_reason),
        "is_authenticated": session.is_authenticated,
        "auth_method": _enum_val(session.auth_method),
        "business_turn_count": session.business_turn_count,
        "total_turn_count": session.total_turn_count,
        "tts_speed_factor": session.tts_speed_factor,
        "csat_score": session.csat_score,
        "escalation_reason": session.escalation_reason,
        "escalation_reasons": _to_json(session.escalation_reasons),
        "auth_attempts": _to_json(
            [
                {
                    "auth_type": a.auth_type.value,
                    "is_success": a.is_success,
                    "attempted_at": a.attempted_at.isoformat(),
                }
                for a in session.auth_attempts
            ]
        ),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "expires_at": session.expires_at,
    }


def row_to_session(row: dict) -> ConversationSession:
    """DB row dict → ConversationSession."""
    from datetime import datetime

    def _dt(v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(v)

    auth_attempts_raw = _from_json(row["auth_attempts"])
    auth_attempts = [
        AuthAttempt(
            auth_type=AuthType(a["auth_type"]),
            is_success=a["is_success"],
            attempted_at=_dt(a["attempted_at"]),
        )
        for a in auth_attempts_raw
    ]

    return ConversationSession(
        session_id=row["session_id"],
        caller_id=row["caller_id"],
        customer_id=row.get("customer_id"),
        start_time=_dt(row["start_time"]),
        end_time=_dt(row.get("end_time")),
        end_reason=EndReason(row["end_reason"]) if row.get("end_reason") else None,
        is_authenticated=row["is_authenticated"],
        auth_method=AuthType(row["auth_method"]) if row.get("auth_method") else None,
        business_turn_count=row["business_turn_count"],
        total_turn_count=row["total_turn_count"],
        tts_speed_factor=row["tts_speed_factor"],
        csat_score=row.get("csat_score"),
        escalation_reason=row.get("escalation_reason"),
        escalation_reasons=_from_json(row["escalation_reasons"]),
        auth_attempts=auth_attempts,
        created_at=_dt(row["created_at"]),
        updated_at=_dt(row["updated_at"]),
        expires_at=_dt(row["expires_at"]),
    )


# ---------------------------------------------------------------------------
# ConversationTurn
# ---------------------------------------------------------------------------

def turn_to_row(turn: ConversationTurn) -> dict:
    """ConversationTurn → DB row dict."""
    return {
        "turn_id": turn.turn_id,
        "session_id": turn.session_id,
        "turn_number": turn.turn_number,
        "turn_type": _enum_val(turn.turn_type),
        "customer_utterance": turn.customer_utterance,
        "stt_confidence": turn.stt_confidence,
        "intent": turn.intent,
        "intent_confidence": turn.intent_confidence,
        "entities": _to_json(turn.entities),
        "bot_response": turn.bot_response,
        "llm_confidence": turn.llm_confidence,
        "verification_status": turn.verification_status,
        "response_time_ms": turn.response_time_ms,
        "is_dtmf_input": turn.is_dtmf_input,
        "is_barge_in": turn.is_barge_in,
        "is_legal_required": turn.is_legal_required,
        "masking_applied": turn.masking_applied,
        "masking_restore_success": turn.masking_restore_success,
        "unrestored_tokens": _to_json(turn.unrestored_tokens),
        "response_replaced_by_template": turn.response_replaced_by_template,
        "timestamp": turn.timestamp,
    }


def row_to_turn(row: dict) -> ConversationTurn:
    """DB row dict → ConversationTurn."""
    return ConversationTurn(
        turn_id=row["turn_id"],
        session_id=row["session_id"],
        turn_number=row["turn_number"],
        turn_type=TurnType(row["turn_type"]),
        customer_utterance=row["customer_utterance"],
        stt_confidence=row["stt_confidence"],
        intent=row.get("intent"),
        intent_confidence=row["intent_confidence"],
        entities=_from_json(row["entities"]),
        bot_response=row["bot_response"],
        llm_confidence=row.get("llm_confidence"),
        verification_status=row.get("verification_status"),
        response_time_ms=row["response_time_ms"],
        is_dtmf_input=row["is_dtmf_input"],
        is_barge_in=row["is_barge_in"],
        is_legal_required=row["is_legal_required"],
        masking_applied=row["masking_applied"],
        masking_restore_success=row["masking_restore_success"],
        unrestored_tokens=_from_json(row["unrestored_tokens"]),
        response_replaced_by_template=row["response_replaced_by_template"],
        timestamp=row["timestamp"],
    )
