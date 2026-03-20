"""callbot.business.callback_scheduler — 콜백 예약 모듈"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

from callbot.business.callback_db import CallbackDBBase
from callbot.business.models import (
    CallbackResult,
    ConsentResult,
    PhoneCollectionResult,
    TimeCollectionResult,
)

# 한국 전화번호 패턴
_MOBILE_PATTERN = re.compile(r"^01[016789]-?\d{3,4}-?\d{4}$")
_LANDLINE_PATTERN = re.compile(r"^0[2-9]\d?-?\d{3,4}-?\d{4}$")

_BUSINESS_OPEN_HOUR = 9
_BUSINESS_CLOSE_HOUR = 18


def _is_valid_korean_phone(number: str) -> bool:
    return bool(_MOBILE_PATTERN.match(number) or _LANDLINE_PATTERN.match(number))


def _normalize_phone(number: str) -> str:
    """하이픈 제거 후 반환."""
    return number.replace("-", "")


def _next_business_day() -> date:
    """오늘 다음 영업일(평일) 반환."""
    candidate = datetime.now().date() + timedelta(days=1)
    while candidate.weekday() >= 5:  # 5=Sat, 6=Sun
        candidate += timedelta(days=1)
    return candidate


def _is_future_business_hours(dt: datetime) -> bool:
    """미래 시간이고 영업시간(평일 09:00~18:00) 내인지 확인."""
    now = datetime.now()
    if dt <= now:
        return False
    if dt.weekday() >= 5:
        return False
    if dt.hour < _BUSINESS_OPEN_HOUR or dt.hour >= _BUSINESS_CLOSE_HOUR:
        return False
    return True


class CallbackScheduler:
    """콜백 예약 다단계 인터랙션 전담 모듈."""

    def __init__(self, routing_engine=None, db: Optional[CallbackDBBase] = None) -> None:
        self._routing_engine = routing_engine
        self._db = db
        self._phone_retry_counts: dict[str, int] = {}
        self._time_retry_counts: dict[str, int] = {}

    def collect_phone_number(self, session: Any, utterance: str) -> PhoneCollectionResult:
        """콜백 전화번호 수집 및 한국 전화번호 패턴 검증.

        - 1회 실패: retry_count=1, is_valid=False, fallback_to_caller=False
        - 2회 실패: fallback_to_caller=True, is_valid=False, retry_count=1
        - 성공: is_valid=True, phone_number=normalized
        """
        session_id: str = session.session_id
        current_retry = self._phone_retry_counts.get(session_id, 0)

        if _is_valid_korean_phone(utterance):
            return PhoneCollectionResult(
                is_valid=True,
                phone_number=_normalize_phone(utterance),
                retry_count=current_retry,
                fallback_to_caller=False,
            )

        # 유효하지 않은 번호
        if current_retry >= 1:
            # 2번째 실패 → fallback
            return PhoneCollectionResult(
                is_valid=False,
                phone_number=None,
                retry_count=1,
                fallback_to_caller=True,
            )

        # 1번째 실패
        self._phone_retry_counts[session_id] = current_retry + 1
        return PhoneCollectionResult(
            is_valid=False,
            phone_number=None,
            retry_count=1,
            fallback_to_caller=False,
        )

    def collect_preferred_time(
        self,
        session: Any,
        utterance: str,
        is_llm_available: bool = True,
    ) -> TimeCollectionResult:
        """콜백 희망 시간 수집.

        - is_llm_available=False: DTMF 모드 (1=오전, 2=오후)
        - is_llm_available=True: ISO datetime 문자열 파싱
        - 영업시간 내 미래 시간만 허용, 2회 실패 시 retry_count=2
        """
        session_id: str = session.session_id
        current_retry = self._time_retry_counts.get(session_id, 0)

        if not is_llm_available:
            return self._collect_time_dtmf(session_id, utterance, current_retry)
        return self._collect_time_voice(session_id, utterance, current_retry)

    def _collect_time_dtmf(
        self, session_id: str, utterance: str, current_retry: int
    ) -> TimeCollectionResult:
        next_biz = _next_business_day()

        if utterance == "1":
            parsed = datetime(next_biz.year, next_biz.month, next_biz.day, 10, 0)
            return TimeCollectionResult(
                is_valid=True,
                parsed_time=parsed,
                collection_mode="dtmf",
                retry_count=current_retry,
            )
        elif utterance == "2":
            parsed = datetime(next_biz.year, next_biz.month, next_biz.day, 14, 0)
            return TimeCollectionResult(
                is_valid=True,
                parsed_time=parsed,
                collection_mode="dtmf",
                retry_count=current_retry,
            )
        else:
            new_retry = min(current_retry + 1, 2)
            self._time_retry_counts[session_id] = new_retry
            return TimeCollectionResult(
                is_valid=False,
                parsed_time=None,
                collection_mode="dtmf",
                retry_count=new_retry,
            )

    def _collect_time_voice(
        self, session_id: str, utterance: str, current_retry: int
    ) -> TimeCollectionResult:
        try:
            parsed = datetime.fromisoformat(utterance)
        except (ValueError, TypeError):
            new_retry = min(current_retry + 1, 2)
            self._time_retry_counts[session_id] = new_retry
            return TimeCollectionResult(
                is_valid=False,
                parsed_time=None,
                collection_mode="voice",
                retry_count=new_retry,
            )

        if not _is_future_business_hours(parsed):
            new_retry = min(current_retry + 1, 2)
            self._time_retry_counts[session_id] = new_retry
            return TimeCollectionResult(
                is_valid=False,
                parsed_time=None,
                collection_mode="voice",
                retry_count=new_retry,
            )

        return TimeCollectionResult(
            is_valid=True,
            parsed_time=parsed,
            collection_mode="voice",
            retry_count=current_retry,
        )

    def collect_consent(self, session: Any) -> ConsentResult:
        """동의 수집 결과 객체 반환. 실제 동의 상태는 오케스트레이터가 관리."""
        return ConsentResult(consent_given=True, is_rejected=False)

    def schedule(
        self,
        session: Any,
        preferred_time: datetime,
        phone_number: str,
        consent_given: bool,
    ) -> CallbackResult:
        """최종 콜백 예약 실행."""
        if not consent_given:
            return CallbackResult(
                is_success=False,
                reservation_id=None,
                scheduled_time=None,
                phone_number=None,
                error_message="동의 미확인",
            )

        if self._db is None:
            return CallbackResult(
                is_success=False,
                reservation_id=None,
                scheduled_time=None,
                phone_number=None,
                error_message="DB 미연결",
            )

        session_id: str = session.session_id
        reservation_id = self._db.save_reservation(
            session_id=session_id,
            phone_number=phone_number,
            scheduled_time=preferred_time,
            consent_given=consent_given,
        )

        return CallbackResult(
            is_success=True,
            reservation_id=reservation_id,
            scheduled_time=preferred_time,
            phone_number=phone_number,
            error_message=None,
        )
