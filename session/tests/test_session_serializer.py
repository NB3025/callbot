"""test_session_serializer.py — session_serializer 속성 테스트 + 단위 테스트"""
from __future__ import annotations

import json
from datetime import datetime

import pytest
from hypothesis import given, settings

from callbot.session.enums import AuthStatus, TurnType
from callbot.session.exceptions import SessionSerializationError
from callbot.session.models import PlanListContext, SessionContext, Turn
from callbot.session.session_serializer import deserialize, serialize
from callbot.session.tests.conftest import session_contexts


# ---------------------------------------------------------------------------
# Property 3: SessionContext JSON 직렬화 라운드트립
# Validates: Requirements 3.3
# ---------------------------------------------------------------------------

@given(ctx=session_contexts())
@settings(max_examples=100)
def test_serialize_deserialize_roundtrip(ctx: SessionContext) -> None:
    """serialize → deserialize → 원본 일치 검증.

    **Validates: Requirements 3.3**
    """
    json_str = serialize(ctx)
    restored = deserialize(json_str)
    assert restored == ctx


# ---------------------------------------------------------------------------
# 단위 테스트 (Task 4.3)
# ---------------------------------------------------------------------------

def _make_minimal_context(**overrides) -> SessionContext:
    """테스트용 최소 SessionContext 생성."""
    defaults = dict(
        session_id="test-id",
        caller_id="010-1234-5678",
        is_authenticated=False,
        customer_info=None,
        auth_status=AuthStatus.NOT_ATTEMPTED,
        turns=[],
        business_turn_count=0,
        start_time=datetime(2025, 3, 16, 10, 30, 0),
        tts_speed_factor=1.0,
        cached_billing_data=None,
        injection_detection_count=0,
        masking_restore_failure_count=0,
        plan_list_context=None,
        pending_intent=None,
        pending_classification=None,
    )
    defaults.update(overrides)
    return SessionContext(**defaults)


def test_serialize_datetime_as_iso8601() -> None:
    """datetime 필드가 ISO 8601 형식으로 직렬화되는지 확인.

    Requirements: 3.4
    """
    ctx = _make_minimal_context(start_time=datetime(2025, 3, 16, 10, 30, 0))
    json_str = serialize(ctx)
    data = json.loads(json_str)
    assert data["start_time"] == "2025-03-16T10:30:00"


def test_serialize_enum_as_value_string() -> None:
    """Enum 필드가 .value 문자열로 직렬화되는지 확인.

    Requirements: 3.5
    """
    ctx = _make_minimal_context(auth_status=AuthStatus.SUCCESS)
    json_str = serialize(ctx)
    data = json.loads(json_str)
    assert data["auth_status"] == "인증성공"


def test_serialize_nested_turn_list() -> None:
    """Turn 목록이 재귀적으로 직렬화되는지 확인.

    Requirements: 3.6
    """
    turn = Turn(
        turn_id="turn-1",
        turn_type=TurnType.BUSINESS,
        customer_utterance="요금제 알려주세요",
        bot_response="네, 안내드리겠습니다.",
        intent="plan_inquiry",
        entities=["5G"],
        stt_confidence=0.95,
        intent_confidence=0.8,
        llm_confidence=None,
        verification_status=None,
        response_time_ms=150,
        is_dtmf_input=False,
        is_barge_in=False,
        timestamp=datetime(2025, 3, 16, 10, 31, 0),
    )
    ctx = _make_minimal_context(turns=[turn])
    json_str = serialize(ctx)
    data = json.loads(json_str)

    assert len(data["turns"]) == 1
    t = data["turns"][0]
    assert t["turn_type"] == "업무"
    assert t["timestamp"] == "2025-03-16T10:31:00"
    assert t["intent"] == "plan_inquiry"
    assert t["entities"] == ["5G"]


def test_serialize_nested_plan_list_context() -> None:
    """PlanListContext가 재귀적으로 직렬화되는지 확인.

    Requirements: 3.6
    """
    plc = PlanListContext(
        available_plans=[{"name": "5G_BASIC", "price": 55000}],
        current_page=0,
        page_size=3,
        current_plan={"name": "LTE_STANDARD"},
        is_exhausted=False,
    )
    ctx = _make_minimal_context(plan_list_context=plc)
    json_str = serialize(ctx)
    data = json.loads(json_str)

    assert data["plan_list_context"]["available_plans"] == [{"name": "5G_BASIC", "price": 55000}]
    assert data["plan_list_context"]["current_page"] == 0
    assert data["plan_list_context"]["is_exhausted"] is False


def test_serialize_non_json_type_raises_error() -> None:
    """set 타입 → SessionSerializationError.

    Requirements: 3.7
    """
    ctx = _make_minimal_context(customer_info={1, 2, 3})  # set은 JSON 비호환
    with pytest.raises(SessionSerializationError, match="non-JSON-compatible"):
        serialize(ctx)


def test_deserialize_invalid_json_raises_error() -> None:
    """잘못된 JSON → SessionSerializationError."""
    with pytest.raises(SessionSerializationError, match="Invalid JSON"):
        deserialize("not-valid-json{{{")
