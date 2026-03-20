"""Task 5 — 라우팅 엔진 단위 테스트"""
from datetime import datetime, date

import pytest

from callbot.business.routing_engine import RoutingEngine
from callbot.business.enums import AgentGroup
from callbot.nlu.enums import Intent


# ---------------------------------------------------------------------------
# 5.1 의도 → 상담사 그룹 매핑
# ---------------------------------------------------------------------------

def _engine() -> RoutingEngine:
    return RoutingEngine()


def test_resolve_billing_inquiry():
    assert _engine().resolve_agent_group(Intent.BILLING_INQUIRY, None, None) == AgentGroup.BILLING


def test_resolve_payment_check():
    assert _engine().resolve_agent_group(Intent.PAYMENT_CHECK, None, None) == AgentGroup.BILLING


def test_resolve_plan_change():
    assert _engine().resolve_agent_group(Intent.PLAN_CHANGE, None, None) == AgentGroup.PLAN_SERVICE


def test_resolve_plan_inquiry():
    assert _engine().resolve_agent_group(Intent.PLAN_INQUIRY, None, None) == AgentGroup.PLAN_SERVICE


def test_resolve_cancellation():
    assert _engine().resolve_agent_group(Intent.CANCELLATION, None, None) == AgentGroup.CANCELLATION_COMPLAINT


def test_resolve_complaint():
    assert _engine().resolve_agent_group(Intent.COMPLAINT, None, None) == AgentGroup.CANCELLATION_COMPLAINT


def test_resolve_general_inquiry():
    assert _engine().resolve_agent_group(Intent.GENERAL_INQUIRY, None, None) == AgentGroup.GENERAL


def test_resolve_unclassified():
    assert _engine().resolve_agent_group(Intent.UNCLASSIFIED, None, None) == AgentGroup.GENERAL


def test_resolve_agent_connect():
    assert _engine().resolve_agent_group(Intent.AGENT_CONNECT, None, None) == AgentGroup.GENERAL


def test_resolve_none_intent():
    assert _engine().resolve_agent_group(None, None, None) == AgentGroup.GENERAL


# ---------------------------------------------------------------------------
# 5.2 영업시간 판단
# ---------------------------------------------------------------------------

def test_business_hours_weekday_morning_open():
    # 평일 09:00 → is_open=True
    ts = datetime(2024, 1, 2, 9, 0)  # Tuesday
    result = RoutingEngine().is_business_hours(ts)
    assert result.is_open is True


def test_business_hours_weekday_at_18_closed():
    # 평일 18:00 → is_open=False (18:00은 영업시간 외)
    ts = datetime(2024, 1, 2, 18, 0)  # Tuesday
    result = RoutingEngine().is_business_hours(ts)
    assert result.is_open is False


def test_business_hours_saturday_closed():
    # 토요일 → is_open=False
    ts = datetime(2024, 1, 6, 10, 0)  # Saturday
    result = RoutingEngine().is_business_hours(ts)
    assert result.is_open is False


def test_business_hours_holiday_closed():
    # 공휴일 → is_open=False
    holiday = date(2024, 1, 2)  # Tuesday but marked as holiday
    engine = RoutingEngine(holidays={holiday})
    ts = datetime(2024, 1, 2, 10, 0)
    result = engine.is_business_hours(ts)
    assert result.is_open is False


def test_business_hours_before_open_next_open_is_today():
    # 평일 08:00 → 당일 09:00이 next_open_time
    ts = datetime(2024, 1, 2, 8, 0)  # Tuesday 08:00
    result = RoutingEngine().is_business_hours(ts)
    assert result.is_open is False
    assert result.next_open_time == datetime(2024, 1, 2, 9, 0)


def test_business_hours_after_close_next_open_is_next_weekday():
    # 금요일 18:00 이후 → 다음 월요일 09:00
    ts = datetime(2024, 1, 5, 19, 0)  # Friday 19:00
    result = RoutingEngine().is_business_hours(ts)
    assert result.is_open is False
    assert result.next_open_time == datetime(2024, 1, 8, 9, 0)  # Monday


def test_business_hours_sunday_next_open_is_monday():
    ts = datetime(2024, 1, 7, 12, 0)  # Sunday
    result = RoutingEngine().is_business_hours(ts)
    assert result.is_open is False
    assert result.next_open_time == datetime(2024, 1, 8, 9, 0)  # Monday


def test_business_hours_weekday_just_before_close():
    # 평일 17:59 → is_open=True
    ts = datetime(2024, 1, 2, 17, 59)
    result = RoutingEngine().is_business_hours(ts)
    assert result.is_open is True


# ---------------------------------------------------------------------------
# 6.1 상담사 연결 장애 단위 테스트
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock
from callbot.business.agent_system import AgentSystemBase
from callbot.business.models import RoutingResult, WaitTimeEstimate


def test_route_to_agent_system_error_returns_fallback():
    """상담사 시스템 장애 → is_system_error=True, fallback_message 포함"""
    agent_sys = MagicMock()
    agent_sys.connect_agent.side_effect = Exception("연결 실패")
    engine = RoutingEngine(agent_system=agent_sys)

    session = MagicMock()
    session.session_id = "sess-x"
    session.intent = None

    result = engine.route_to_agent(session, None, None)

    assert result.is_success is False
    assert result.is_system_error is True
    assert result.fallback_message is not None


def test_route_to_agent_success():
    """상담사 연결 성공 → is_success=True"""
    agent_sys = MagicMock()
    agent_sys.connect_agent.return_value = True
    engine = RoutingEngine(agent_system=agent_sys)

    session = MagicMock()
    session.session_id = "sess-y"
    session.intent = None

    result = engine.route_to_agent(session, None, None)

    assert result.is_success is True
    assert result.is_system_error is False
