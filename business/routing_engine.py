"""callbot.business.routing_engine — 라우팅 엔진: 상담사 그룹 매핑 및 영업시간 판단"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING, Any, Optional

from callbot.business.enums import AgentGroup
from callbot.business.models import BusinessHoursResult, RoutingResult, WaitTimeEstimate
from callbot.nlu.enums import Intent

if TYPE_CHECKING:
    from callbot.business.agent_system import AgentSystemBase

# 의도 → 상담사 그룹 매핑 테이블
_INTENT_TO_AGENT_GROUP: dict[Intent, AgentGroup] = {
    Intent.BILLING_INQUIRY: AgentGroup.BILLING,
    Intent.PAYMENT_CHECK: AgentGroup.BILLING,
    Intent.PLAN_CHANGE: AgentGroup.PLAN_SERVICE,
    Intent.PLAN_INQUIRY: AgentGroup.PLAN_SERVICE,
    Intent.CANCELLATION: AgentGroup.CANCELLATION_COMPLAINT,
    Intent.COMPLAINT: AgentGroup.CANCELLATION_COMPLAINT,
    Intent.GENERAL_INQUIRY: AgentGroup.GENERAL,
    Intent.UNCLASSIFIED: AgentGroup.GENERAL,
    Intent.AGENT_CONNECT: AgentGroup.GENERAL,
}

_BUSINESS_OPEN = time(9, 0)
_BUSINESS_CLOSE = time(18, 0)


class RoutingEngine:
    def __init__(
        self,
        holidays: set | None = None,
        agent_system: "AgentSystemBase | None" = None,
    ) -> None:
        self._holidays: set[date] = holidays if holidays is not None else set()
        self._agent_system = agent_system

    def resolve_agent_group(
        self,
        intent: Optional[Intent],
        escalation_reason: Any,
        session: Any,
    ) -> AgentGroup:
        """의도 → 상담사 그룹 매핑. 매핑 없거나 None이면 GENERAL 반환."""
        if intent is None:
            return AgentGroup.GENERAL
        return _INTENT_TO_AGENT_GROUP.get(intent, AgentGroup.GENERAL)

    def is_business_hours(self, timestamp: Optional[datetime] = None) -> BusinessHoursResult:
        """평일(월~금) 09:00~18:00, 공휴일 제외 영업시간 판단."""
        now = timestamp if timestamp is not None else datetime.now()
        current_date = now.date()
        current_time = now.time()

        is_weekday = now.weekday() <= 4  # 0=Mon … 4=Fri
        is_holiday = current_date in self._holidays
        in_time_range = _BUSINESS_OPEN <= current_time < _BUSINESS_CLOSE

        if is_weekday and not is_holiday and in_time_range:
            return BusinessHoursResult(is_open=True, next_open_time=None, message=None)

        # 영업시간 외 — 다음 영업 시작 시간 계산
        next_open = self._next_open_time(now)
        return BusinessHoursResult(
            is_open=False,
            next_open_time=next_open,
            message=f"영업시간은 평일 09:00~18:00입니다. 다음 영업 시작: {next_open.strftime('%Y-%m-%d %H:%M')}",
        )

    def check_agent_availability(self, group: AgentGroup) -> bool:
        """상담사 가용 여부 확인. agent_system 없으면 False 반환."""
        if self._agent_system is None:
            return False
        return self._agent_system.check_availability(group)

    def estimate_wait_time(self, agent_group: AgentGroup) -> WaitTimeEstimate:
        """예상 대기 시간 조회. agent_system 없으면 기본값 반환."""
        if self._agent_system is None:
            return WaitTimeEstimate(estimated_minutes=0, queue_position=0, is_available=False)
        return self._agent_system.get_wait_time(agent_group)

    def route_to_agent(self, session: Any, reason: Any, summary: Any) -> RoutingResult:
        """상담사 그룹으로 연결 요청. 시스템 장애 시 fallback_message 포함 반환."""
        intent = session.intent if hasattr(session, "intent") else None
        group = self.resolve_agent_group(intent, reason, session)
        session_id = session.session_id if hasattr(session, "session_id") else str(session)

        if self._agent_system is None:
            return RoutingResult(
                is_success=False,
                agent_group=group,
                is_system_error=True,
                fallback_message="고객센터(1234)로 연락 주시기 바랍니다.",
            )

        summary_dict: dict = summary if isinstance(summary, dict) else {}
        try:
            self._agent_system.connect_agent(group, session_id, summary_dict)
        except Exception:
            return RoutingResult(
                is_success=False,
                agent_group=group,
                is_system_error=True,
                fallback_message="고객센터(1234)로 연락 주시기 바랍니다.",
            )

        return RoutingResult(
            is_success=True,
            agent_group=group,
            is_system_error=False,
            fallback_message=None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_business_day(self, d: date) -> bool:
        return d.weekday() <= 4 and d not in self._holidays

    def _next_open_time(self, now: datetime) -> datetime:
        """다음 영업 시작 시각 반환.

        - 평일(비공휴일) 09:00 이전이면 당일 09:00
        - 그 외(주말, 공휴일, 18:00 이후)이면 다음 영업일 09:00
        """
        current_date = now.date()
        current_time = now.time()

        # 오늘이 영업일이고 아직 09:00 이전이면 오늘 09:00
        if self._is_business_day(current_date) and current_time < _BUSINESS_OPEN:
            return datetime.combine(current_date, _BUSINESS_OPEN)

        # 다음 영업일 09:00 탐색
        from datetime import timedelta
        candidate = current_date + timedelta(days=1)
        while not self._is_business_day(candidate):
            candidate += timedelta(days=1)
        return datetime.combine(candidate, _BUSINESS_OPEN)
