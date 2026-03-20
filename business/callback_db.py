"""callbot.business.callback_db — 콜백 예약 DB 추상 인터페이스"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class CallbackDBBase(ABC):
    @abstractmethod
    def save_reservation(
        self,
        session_id: str,
        phone_number: str,
        scheduled_time: datetime,
        consent_given: bool,
    ) -> str:
        """예약 저장. 예약 ID 반환."""
        ...
