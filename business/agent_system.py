"""callbot.business.agent_system — 상담사 시스템 추상 인터페이스"""
from __future__ import annotations

from abc import ABC, abstractmethod

from callbot.business.enums import AgentGroup
from callbot.business.models import WaitTimeEstimate


class AgentSystemBase(ABC):
    @abstractmethod
    def connect_agent(self, group: AgentGroup, session_id: str, summary: dict) -> bool:
        """상담사 연결 요청. 성공 시 True, 시스템 장애 시 False."""
        ...

    @abstractmethod
    def get_wait_time(self, group: AgentGroup) -> WaitTimeEstimate:
        """예상 대기 시간 조회."""
        ...

    @abstractmethod
    def check_availability(self, group: AgentGroup) -> bool:
        """상담사 가용 여부 확인."""
        ...
