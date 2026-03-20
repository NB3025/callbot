"""callbot.orchestrator.tests.test_health_checker — HealthChecker 단위 테스트"""
from __future__ import annotations

import pytest

from callbot.orchestrator.health_checker import HealthChecker
from callbot.orchestrator.models import HealthCheckStatus


# ---------------------------------------------------------------------------
# 테스트: 외부 헬스체크 (Task 13.1)
# ---------------------------------------------------------------------------

class TestExternalHealthCheck:
    def test_two_consecutive_failures_still_healthy(self):
        """2회 연속 실패 → is_healthy=True (3회 미만)"""
        checker = HealthChecker()
        # 2회 실패 시뮬레이션
        checker.record_failure("stt_service")
        checker.record_failure("stt_service")

        status = checker.check_external("stt_service")

        assert status.is_healthy is True
        assert status.consecutive_failures == 2

    def test_three_consecutive_failures_unhealthy(self):
        """3회 연속 실패 → is_healthy=False"""
        checker = HealthChecker()
        checker.record_failure("stt_service")
        checker.record_failure("stt_service")
        checker.record_failure("stt_service")

        status = checker.check_external("stt_service")

        assert status.is_healthy is False
        assert status.consecutive_failures == 3

    def test_success_resets_consecutive_failure_count(self):
        """2회 실패 후 성공 → 연속 실패 카운트 초기화, is_healthy=True"""
        checker = HealthChecker()
        checker.record_failure("stt_service")
        checker.record_failure("stt_service")
        checker.record_success("stt_service")

        status = checker.check_external("stt_service")

        assert status.is_healthy is True
        assert status.consecutive_failures == 0

    def test_success_after_three_failures_becomes_healthy(self):
        """3회 실패 후 성공 → is_healthy=True, consecutive_failures=0"""
        checker = HealthChecker()
        checker.record_failure("llm_service")
        checker.record_failure("llm_service")
        checker.record_failure("llm_service")
        checker.record_success("llm_service")

        status = checker.check_external("llm_service")

        assert status.is_healthy is True
        assert status.consecutive_failures == 0

    def test_different_components_tracked_independently(self):
        """서로 다른 컴포넌트는 독립적으로 추적"""
        checker = HealthChecker()
        checker.record_failure("stt_service")
        checker.record_failure("stt_service")
        checker.record_failure("stt_service")

        stt_status = checker.check_external("stt_service")
        llm_status = checker.check_external("llm_service")

        assert stt_status.is_healthy is False
        assert llm_status.is_healthy is True

    def test_check_external_returns_health_check_status(self):
        """check_external() → HealthCheckStatus 반환"""
        checker = HealthChecker()

        status = checker.check_external("tts_service")

        assert isinstance(status, HealthCheckStatus)
        assert status.component_name == "tts_service"
        assert status.component_type == "external"

    def test_send_alert_called_on_third_failure(self):
        """3회 연속 실패 시 send_alert 호출 여부 확인"""
        alerts = []

        class AlertCapturingChecker(HealthChecker):
            def send_alert(self, alert_type, severity, component, message):
                alerts.append({
                    "alert_type": alert_type,
                    "severity": severity,
                    "component": component,
                    "message": message,
                })

        checker = AlertCapturingChecker()
        checker.record_failure("stt_service")
        checker.record_failure("stt_service")
        checker.record_failure("stt_service")
        checker.check_external("stt_service")

        assert len(alerts) == 1
        assert alerts[0]["component"] == "stt_service"
        assert alerts[0]["severity"] in ("critical", "high", "warning")


# ---------------------------------------------------------------------------
# 테스트: 내부 오류율 감시 (Task 14.1 속성 테스트 + 14.2 경계값 테스트)
# ---------------------------------------------------------------------------

from hypothesis import given, settings
import hypothesis.strategies as st


class TestInternalErrorRate:
    def test_error_rate_60pct_15_requests_is_failure(self):
        """오류율 60%, 요청 수 15건 → 장애 판단"""
        checker = HealthChecker()
        checker.record_internal_events("nlu", total=15, errors=9)

        assert checker.is_internal_failure("nlu") is True

    def test_error_rate_60pct_8_requests_not_failure(self):
        """오류율 60%, 요청 수 8건 → 장애 판단 보류 (오탐 방지)"""
        checker = HealthChecker()
        checker.record_internal_events("nlu", total=8, errors=5)

        assert checker.is_internal_failure("nlu") is False

    def test_error_rate_40pct_20_requests_not_failure(self):
        """오류율 40%, 요청 수 20건 → 정상 판단"""
        checker = HealthChecker()
        checker.record_internal_events("llm", total=20, errors=8)

        assert checker.is_internal_failure("llm") is False

    def test_error_rate_exactly_50pct_10_requests_not_failure(self):
        """오류율 정확히 50%, 요청 수 10건 → 정상 (> 0.5 조건이므로)"""
        checker = HealthChecker()
        checker.record_internal_events("tts", total=10, errors=5)

        assert checker.is_internal_failure("tts") is False

    def test_error_rate_51pct_10_requests_is_failure(self):
        """오류율 51%, 요청 수 10건 → 장애 판단"""
        checker = HealthChecker()
        checker.record_internal_events("tts", total=100, errors=51)

        assert checker.is_internal_failure("tts") is True

    def test_check_internal_error_rate_returns_float_in_range(self):
        """check_internal_error_rate() → 반환값 ∈ [0.0, 1.0]"""
        checker = HealthChecker()
        checker.record_internal_events("nlu", total=20, errors=10)

        rate = checker.check_internal_error_rate("nlu")

        assert 0.0 <= rate <= 1.0

    def test_no_requests_returns_zero_rate(self):
        """요청 없음 → 오류율 0.0"""
        checker = HealthChecker()

        rate = checker.check_internal_error_rate("nlu")

        assert rate == 0.0


class TestInternalErrorRateProperty:
    @given(
        total=st.integers(min_value=0, max_value=9),
        errors=st.integers(min_value=0, max_value=9),
    )
    @settings(max_examples=200)
    def test_fewer_than_10_requests_never_triggers_failure(self, total, errors):
        """Property 4: 요청 수 < 10건이면 오류율에 관계없이 장애 판단 보류"""
        errors = min(errors, total)  # errors <= total 보장
        checker = HealthChecker()
        checker.record_internal_events("module", total=total, errors=errors)

        assert checker.is_internal_failure("module") is False

    @given(
        total=st.integers(min_value=10, max_value=1000),
        errors=st.integers(min_value=0, max_value=1000),
    )
    @settings(max_examples=200)
    def test_high_error_rate_with_sufficient_requests_triggers_failure(self, total, errors):
        """오류율 > 0.5 AND 요청 수 >= 10건 → 장애 판단"""
        # errors > total / 2 이고 errors <= total 보장
        errors = min(errors, total)
        if errors * 2 <= total:
            errors = total // 2 + 1  # 반드시 > 50% 보장
        if errors > total:
            errors = total
        checker = HealthChecker()
        checker.record_internal_events("module", total=total, errors=errors)

        assert checker.is_internal_failure("module") is True


# ---------------------------------------------------------------------------
# 테스트: 트래픽 전환 판단 (Task 15.1)
# ---------------------------------------------------------------------------

from callbot.orchestrator.enums import SwitchDecision
from callbot.orchestrator.models import TrafficObservationMetrics


def _good_metrics(**overrides) -> TrafficObservationMetrics:
    """기본 정상 지표 팩토리."""
    defaults = dict(
        response_time_p95_general=3.0,
        response_time_p95_billing=5.0,
        error_rate=0.02,
        escalation_rate_delta=0.01,
        observation_window_min=10,
    )
    defaults.update(overrides)
    return TrafficObservationMetrics(**defaults)


class TestTrafficSwitch:
    def test_good_metrics_returns_proceed(self):
        """지표 정상 → SwitchDecision.PROCEED"""
        checker = HealthChecker()
        metrics = _good_metrics()

        decision = checker.evaluate_traffic_switch(metrics)

        assert decision == SwitchDecision.PROCEED

    def test_high_error_rate_returns_rollback(self):
        """오류율 임계값 초과 → SwitchDecision.ROLLBACK"""
        checker = HealthChecker()
        metrics = _good_metrics(error_rate=0.15)

        decision = checker.evaluate_traffic_switch(metrics)

        assert decision == SwitchDecision.ROLLBACK

    def test_high_escalation_delta_returns_rollback(self):
        """상담사 폴백률 급증 → SwitchDecision.ROLLBACK"""
        checker = HealthChecker()
        metrics = _good_metrics(escalation_rate_delta=0.25)

        decision = checker.evaluate_traffic_switch(metrics)

        assert decision == SwitchDecision.ROLLBACK

    def test_insufficient_observation_window_returns_extend(self):
        """관찰 시간 부족 (5분) → SwitchDecision.EXTEND"""
        checker = HealthChecker()
        metrics = _good_metrics(observation_window_min=5)

        decision = checker.evaluate_traffic_switch(metrics)

        assert decision == SwitchDecision.EXTEND

    def test_borderline_metrics_returns_manual(self):
        """경계값 지표 (오류율 8%, 폴백률 10%) → SwitchDecision.MANUAL"""
        checker = HealthChecker()
        metrics = _good_metrics(error_rate=0.08, escalation_rate_delta=0.10)

        decision = checker.evaluate_traffic_switch(metrics)

        assert decision == SwitchDecision.MANUAL

    def test_slow_response_time_returns_manual(self):
        """응답 시간 초과 (일반 6초) → SwitchDecision.MANUAL"""
        checker = HealthChecker()
        metrics = _good_metrics(response_time_p95_general=6.0)

        decision = checker.evaluate_traffic_switch(metrics)

        assert decision == SwitchDecision.MANUAL
