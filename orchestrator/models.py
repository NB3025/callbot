"""callbot.orchestrator.models — 오케스트레이터 핵심 데이터 모델"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from callbot.orchestrator.enums import ActionType

# action_type → 허용 target_component 매핑
_ACTION_TARGET_MAP: dict[ActionType, str] = {
    ActionType.SYSTEM_CONTROL: "orchestrator",
    ActionType.PROCESS_BUSINESS: "llm_engine",
    ActionType.ESCALATE: "routing_engine",
}


@dataclass
class OrchestratorAction:
    """오케스트레이터 액션.

    Invariants:
    - action_type=SYSTEM_CONTROL  → target_component == "orchestrator"
    - action_type=PROCESS_BUSINESS → target_component == "llm_engine"
    - action_type=ESCALATE         → target_component == "routing_engine"
    """
    action_type: ActionType
    target_component: str
    context: dict

    def __post_init__(self) -> None:
        expected = _ACTION_TARGET_MAP.get(self.action_type)
        if expected is not None and self.target_component != expected:
            raise ValueError(
                f"action_type={self.action_type.name} requires "
                f"target_component='{expected}', got '{self.target_component}'"
            )


@dataclass
class SurveyResult:
    """만족도 조사 결과.

    Invariants:
    - is_skipped=False → score is not None and score ∈ [1, 5]
    - is_skipped=True  → score is None
    - score is not None → input_method is not None
    """
    score: Optional[int]
    input_method: Optional[str]
    is_skipped: bool

    def __post_init__(self) -> None:
        if self.is_skipped:
            if self.score is not None:
                raise ValueError("is_skipped=True requires score is None")
        else:
            if self.score is None:
                raise ValueError("is_skipped=False requires score is not None")
            if not (1 <= self.score <= 5):
                raise ValueError(
                    f"is_skipped=False requires score ∈ [1, 5], got {self.score}"
                )
        if self.score is not None and self.input_method is None:
            raise ValueError("score is not None requires input_method is not None")


@dataclass
class SystemControlResult:
    """시스템 제어 처리 결과."""
    intent: Any
    is_handled: bool
    action_taken: str


@dataclass
class EscalationAction:
    """상담사 연결 폴백 액션."""
    reason: Any
    summary: Any
    routing_result: Any


@dataclass
class SessionLimitAction:
    """세션 제한 도달 액션."""
    limit_status: Any
    action: str
    extra_turns_allowed: int = 2


@dataclass
class NoResponseAction:
    """무응답 처리 액션."""
    timeout_stage: int
    action: str


@dataclass
class AuthRequirement:
    """인증 필요 여부.

    Invariant:
    - is_already_authenticated=True → requires_auth=False
    """
    requires_auth: bool
    is_already_authenticated: bool
    auth_type_hint: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.is_already_authenticated and self.requires_auth:
            raise ValueError(
                "is_already_authenticated=True requires requires_auth=False"
            )


@dataclass
class HealthCheckStatus:
    """헬스체크 상태."""
    component_name: str
    component_type: str
    is_healthy: bool
    consecutive_failures: int
    error_rate: Optional[float]
    last_check_time: Any
    failure_declared_at: Optional[Any]
    check_interval_sec: int


@dataclass
class TrafficObservationMetrics:
    """트래픽 관찰 지표."""
    response_time_p95_general: float
    response_time_p95_billing: float
    error_rate: float
    escalation_rate_delta: float
    observation_window_min: int = 10
