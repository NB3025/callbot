"""Tests for CallbackScheduler — Task 8 (8.1, 8.2, 8.3)"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from callbot.business.callback_scheduler import CallbackScheduler


def _next_weekday_at(hour: int) -> datetime:
    """Returns next weekday datetime at given hour."""
    from datetime import date, timedelta
    d = datetime.now().date() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return datetime(d.year, d.month, d.day, hour, 0)


# ---------------------------------------------------------------------------
# 8.1 전화번호 패턴 검증
# ---------------------------------------------------------------------------

def test_collect_phone_valid_mobile():
    # 유효한 휴대폰 번호 → is_valid=True
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "s1"
    result = scheduler.collect_phone_number(session, "010-1234-5678")
    assert result.is_valid is True
    assert result.phone_number is not None


def test_collect_phone_valid_landline():
    # 유효한 유선 번호 → is_valid=True
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "s2"
    result = scheduler.collect_phone_number(session, "02-1234-5678")
    assert result.is_valid is True


def test_collect_phone_invalid_then_fallback():
    # 2회 실패 → fallback_to_caller=True
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "s3"
    scheduler.collect_phone_number(session, "invalid")  # 1st fail
    result = scheduler.collect_phone_number(session, "invalid")  # 2nd fail
    assert result.is_valid is False
    assert result.fallback_to_caller is True


def test_collect_phone_invalid_first_retry():
    # 1회 실패 → fallback_to_caller=False, retry_count=1
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "s4"
    result = scheduler.collect_phone_number(session, "invalid")
    assert result.is_valid is False
    assert result.fallback_to_caller is False
    assert result.retry_count == 1


# ---------------------------------------------------------------------------
# 8.2 희망 시간 유효성
# ---------------------------------------------------------------------------

def test_collect_time_valid_future_business_hours():
    # 영업시간 내 미래 시간 → is_valid=True
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "t1"
    future = _next_weekday_at(10)
    result = scheduler.collect_preferred_time(session, future.isoformat())
    assert result.is_valid is True
    assert result.parsed_time is not None


def test_collect_time_invalid_outside_business_hours():
    # 영업시간 외 시간 → is_valid=False
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "t2"
    future = _next_weekday_at(20)  # 20:00 — outside hours
    result = scheduler.collect_preferred_time(session, future.isoformat())
    assert result.is_valid is False


def test_collect_time_invalid_past():
    # 과거 시간 → is_valid=False
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "t3"
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    result = scheduler.collect_preferred_time(session, past)
    assert result.is_valid is False


# ---------------------------------------------------------------------------
# 8.3 LLM 장애 시 DTMF 대안
# ---------------------------------------------------------------------------

def test_collect_time_dtmf_mode_when_llm_unavailable():
    # is_llm_available=False → collection_mode="dtmf"
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "d1"
    result = scheduler.collect_preferred_time(session, "1", is_llm_available=False)
    assert result.collection_mode == "dtmf"


def test_collect_time_dtmf_1_maps_to_morning():
    # DTMF 1 → 다음 영업일 오전 10:00
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "d2"
    result = scheduler.collect_preferred_time(session, "1", is_llm_available=False)
    assert result.is_valid is True
    assert result.parsed_time is not None
    assert result.parsed_time.hour == 10


def test_collect_time_dtmf_2_maps_to_afternoon():
    # DTMF 2 → 다음 영업일 오후 14:00
    scheduler = CallbackScheduler()
    session = MagicMock()
    session.session_id = "d3"
    result = scheduler.collect_preferred_time(session, "2", is_llm_available=False)
    assert result.is_valid is True
    assert result.parsed_time is not None
    assert result.parsed_time.hour == 14
