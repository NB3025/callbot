"""callbot.session.session_serializer — SessionContext ↔ JSON 직렬화/역직렬화"""
from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime
from enum import Enum
from typing import Any

from callbot.session.enums import AuthStatus, TurnType
from callbot.session.exceptions import SessionSerializationError
from callbot.session.models import PlanListContext, SessionContext, Turn

# JSON 호환 타입 (Optional[Any] 필드 검증용)
_JSON_COMPATIBLE_TYPES = (type(None), str, int, float, bool, list, dict)

# Optional[Any] 필드 이름 (SessionContext + Turn)
_SESSION_ANY_FIELDS = frozenset({
    "customer_info", "pending_intent", "pending_classification",
})
_TURN_ANY_FIELDS = frozenset({"intent", "verification_status"})


def _validate_json_compatible(value: Any, field_name: str) -> None:
    """Optional[Any] 필드 값이 JSON 호환 타입인지 검증."""
    if not isinstance(value, _JSON_COMPATIBLE_TYPES):
        raise SessionSerializationError(
            f"Field '{field_name}' has non-JSON-compatible type: {type(value).__name__}"
        )


def _turn_to_dict(turn: Turn) -> dict:
    """Turn dataclass → dict 변환."""
    d: dict[str, Any] = {}
    for f in fields(turn):
        val = getattr(turn, f.name)
        if f.name in _TURN_ANY_FIELDS:
            _validate_json_compatible(val, f"Turn.{f.name}")
        if isinstance(val, datetime):
            d[f.name] = val.isoformat()
        elif isinstance(val, Enum):
            d[f.name] = val.value
        else:
            d[f.name] = val
    return d


def _plan_list_context_to_dict(plc: PlanListContext) -> dict:
    """PlanListContext dataclass → dict 변환."""
    return {f.name: getattr(plc, f.name) for f in fields(plc)}


def _session_to_dict(ctx: SessionContext) -> dict:
    """SessionContext dataclass → dict 변환 (재귀)."""
    d: dict[str, Any] = {}
    for f in fields(ctx):
        val = getattr(ctx, f.name)
        if f.name in _SESSION_ANY_FIELDS:
            _validate_json_compatible(val, f"SessionContext.{f.name}")
        if isinstance(val, datetime):
            d[f.name] = val.isoformat()
        elif isinstance(val, Enum):
            d[f.name] = val.value
        elif f.name == "turns":
            d[f.name] = [_turn_to_dict(t) for t in val]
        elif f.name == "plan_list_context" and val is not None:
            d[f.name] = _plan_list_context_to_dict(val)
        else:
            d[f.name] = val
    return d


def serialize(context: SessionContext) -> str:
    """SessionContext → JSON 문자열.

    - datetime → ISO 8601 문자열
    - Enum → .value 문자열
    - Turn, PlanListContext 등 중첩 dataclass → 재귀 dict 변환
    - Optional[Any] 필드는 JSON 호환 타입만 허용

    Raises:
        SessionSerializationError: JSON 비호환 타입 발견 시
    """
    try:
        d = _session_to_dict(context)
        return json.dumps(d, ensure_ascii=False)
    except SessionSerializationError:
        raise
    except Exception as exc:
        raise SessionSerializationError(f"Serialization failed: {exc}") from exc


def deserialize(json_str: str) -> SessionContext:
    """JSON 문자열 → SessionContext.

    - ISO 8601 문자열 → datetime
    - Enum value 문자열 → Enum 인스턴스
    - 중첩 dict → Turn, PlanListContext 등 dataclass 복원

    Raises:
        SessionSerializationError: 역직렬화 실패 시
    """
    try:
        d = json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SessionSerializationError(f"Invalid JSON: {exc}") from exc

    try:
        turns = [_dict_to_turn(t) for t in d.get("turns", [])]
        plc_data = d.get("plan_list_context")
        plan_list_context = _dict_to_plan_list_context(plc_data) if plc_data is not None else None

        return SessionContext(
            session_id=d["session_id"],
            caller_id=d["caller_id"],
            is_authenticated=d["is_authenticated"],
            customer_info=d.get("customer_info"),
            auth_status=AuthStatus(d["auth_status"]),
            turns=turns,
            business_turn_count=d["business_turn_count"],
            start_time=datetime.fromisoformat(d["start_time"]),
            tts_speed_factor=d["tts_speed_factor"],
            cached_billing_data=d.get("cached_billing_data"),
            injection_detection_count=d["injection_detection_count"],
            masking_restore_failure_count=d["masking_restore_failure_count"],
            plan_list_context=plan_list_context,
            pending_intent=d.get("pending_intent"),
            pending_classification=d.get("pending_classification"),
        )
    except SessionSerializationError:
        raise
    except Exception as exc:
        raise SessionSerializationError(f"Deserialization failed: {exc}") from exc


def _dict_to_turn(d: dict) -> Turn:
    """dict → Turn dataclass 복원."""
    return Turn(
        turn_id=d["turn_id"],
        turn_type=TurnType(d["turn_type"]),
        customer_utterance=d["customer_utterance"],
        bot_response=d["bot_response"],
        intent=d.get("intent"),
        entities=d.get("entities", []),
        stt_confidence=d["stt_confidence"],
        intent_confidence=d["intent_confidence"],
        llm_confidence=d.get("llm_confidence"),
        verification_status=d.get("verification_status"),
        response_time_ms=d["response_time_ms"],
        is_dtmf_input=d["is_dtmf_input"],
        is_barge_in=d["is_barge_in"],
        timestamp=datetime.fromisoformat(d["timestamp"]),
    )


def _dict_to_plan_list_context(d: dict) -> PlanListContext:
    """dict → PlanListContext dataclass 복원."""
    return PlanListContext(
        available_plans=d.get("available_plans", []),
        current_page=d["current_page"],
        page_size=d["page_size"],
        current_plan=d.get("current_plan", {}),
        is_exhausted=d["is_exhausted"],
    )
