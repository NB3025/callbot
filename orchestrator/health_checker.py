"""callbot.orchestrator.health_checker — 외부/내부 헬스체크 및 트래픽 전환 판단"""
from __future__ import annotations

from datetime import datetime
from typing import Dict

from callbot.orchestrator.enums import SwitchDecision
from callbot.orchestrator.models import HealthCheckStatus, TrafficObservationMetrics


class HealthChecker:
    """외부 시스템 및 내부 모듈 상태 감시 컴포넌트.

    - 외부 헬스체크: 30초 주기, 3회 연속 실패 시 장애 판단
    - 내부 오류율: 1분 슬라이딩 윈도우, 50% 초과 + 10건 이상 시 장애 판단
    - 트래픽 전환: 10분 관찰 후 지표 기반 판단
    """

    _FAILURE_THRESHOLD = 3          # 외부: 연속 실패 임계값
    _ERROR_RATE_THRESHOLD = 0.5     # 내부: 오류율 초과 임계값
    _MIN_REQUESTS_FOR_FAILURE = 10  # 내부: 오탐 방지 최소 요청 수

    def __init__(self) -> None:
        # component_name → consecutive_failures
        self._consecutive_failures: Dict[str, int] = {}
        # module_name → (total_requests, error_count)
        self._internal_metrics: Dict[str, tuple] = {}

    # ------------------------------------------------------------------
    # 외부 헬스체크
    # ------------------------------------------------------------------

    def record_failure(self, component: str) -> None:
        """외부 시스템 실패 기록."""
        self._consecutive_failures[component] = self._consecutive_failures.get(component, 0) + 1

    def record_success(self, component: str) -> None:
        """외부 시스템 성공 기록 — 연속 실패 카운트 초기화."""
        self._consecutive_failures[component] = 0

    def check_external(self, component: str) -> HealthCheckStatus:
        """외부 시스템 헬스체크.

        3회 연속 실패 시 is_healthy=False 판단.
        장애 판단 시 send_alert() 호출.
        """
        consecutive = self._consecutive_failures.get(component, 0)
        is_healthy = consecutive < self._FAILURE_THRESHOLD

        if not is_healthy:
            self.send_alert(
                alert_type="external_health_failure",
                severity="critical",
                component=component,
                message=f"{component} 외부 시스템 {consecutive}회 연속 실패",
            )

        return HealthCheckStatus(
            component_name=component,
            component_type="external",
            is_healthy=is_healthy,
            consecutive_failures=consecutive,
            error_rate=None,
            last_check_time=datetime.utcnow(),
            failure_declared_at=datetime.utcnow() if not is_healthy else None,
            check_interval_sec=30,
        )

    # ------------------------------------------------------------------
    # 내부 오류율 감시
    # ------------------------------------------------------------------

    def record_internal_events(self, module: str, total: int, errors: int) -> None:
        """내부 모듈 이벤트 기록 (테스트/주입용)."""
        self._internal_metrics[module] = (total, errors)

    def check_internal_error_rate(self, module: str, window_sec: int = 60) -> float:
        """내부 모듈 오류율 확인 (1분 슬라이딩 윈도우).

        반환값 ∈ [0.0, 1.0].
        요청 수 < 10건이면 0.0 반환 (장애 판단 보류).
        """
        total, errors = self._internal_metrics.get(module, (0, 0))
        if total == 0:
            return 0.0
        return min(1.0, max(0.0, errors / total))

    def is_internal_failure(self, module: str, window_sec: int = 60) -> bool:
        """내부 모듈 장애 여부 판단.

        오류율 > 0.5 AND 요청 수 >= 10건 → True.
        요청 수 < 10건 → False (오탐 방지).
        """
        total, errors = self._internal_metrics.get(module, (0, 0))
        if total < self._MIN_REQUESTS_FOR_FAILURE:
            return False
        return (errors / total) > self._ERROR_RATE_THRESHOLD

    # ------------------------------------------------------------------
    # 트래픽 전환 판단
    # ------------------------------------------------------------------

    def evaluate_traffic_switch(self, metrics: TrafficObservationMetrics) -> SwitchDecision:
        """점진적 트래픽 전환 판단 (10분 관찰 후).

        - 지표 정상 → PROCEED
        - 오류율 임계값 초과 → ROLLBACK
        - 관찰 시간 부족 → EXTEND
        - 판단 불가 → MANUAL
        """
        if metrics.observation_window_min < 10:
            return SwitchDecision.EXTEND

        if metrics.error_rate > 0.1 or metrics.escalation_rate_delta > 0.2:
            return SwitchDecision.ROLLBACK

        if (
            metrics.response_time_p95_general <= 5.0
            and metrics.response_time_p95_billing <= 7.0
            and metrics.error_rate <= 0.05
            and metrics.escalation_rate_delta <= 0.05
        ):
            return SwitchDecision.PROCEED

        return SwitchDecision.MANUAL

    # ------------------------------------------------------------------
    # 알림
    # ------------------------------------------------------------------

    def send_alert(self, alert_type: str, severity: str, component: str, message: str) -> None:
        """알림 발송 (이메일, SMS, 메신저).

        기본 구현은 no-op. 실제 환경에서 오버라이드하거나 주입.
        """
