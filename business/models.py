"""callbot.business.models — 비즈니스 계층 핵심 데이터 모델"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from callbot.business.enums import AgentGroup, APIErrorType, AuthType


@dataclass
class AuthResult:
    """본인 인증 결과.

    Invariants:
    - is_authenticated=True  → failure_count < max_attempts
    - failure_count >= max_attempts → is_authenticated=False
    """
    is_authenticated: bool
    failure_count: int
    max_attempts: int
    has_password: bool
    can_switch_method: bool
    alternative_method: Optional[AuthType]

    def __post_init__(self) -> None:
        if self.is_authenticated and self.failure_count >= self.max_attempts:
            raise ValueError(
                f"is_authenticated=True requires failure_count({self.failure_count}) < max_attempts({self.max_attempts})"
            )
        if self.failure_count >= self.max_attempts and self.is_authenticated:
            raise ValueError(
                f"failure_count({self.failure_count}) >= max_attempts({self.max_attempts}) requires is_authenticated=False"
            )


@dataclass
class IdentificationResult:
    """고객 식별 결과.

    Invariants:
    - is_found=True  ↔ customer_info is not None
    - is_found=False ↔ customer_info is None
    """
    is_found: bool
    customer_info: Optional[dict]
    is_db_error: bool
    lookup_count: int

    def __post_init__(self) -> None:
        if self.is_found and self.customer_info is None:
            raise ValueError("is_found=True requires customer_info is not None")
        if not self.is_found and self.customer_info is not None:
            raise ValueError("is_found=False requires customer_info is None")


@dataclass
class DTMFValidationResult:
    """DTMF 입력 검증 결과.

    Invariants:
    - is_valid=True  → error_type is None
    - is_valid=False → error_type is not None
    """
    is_valid: bool
    error_type: Optional[str]
    error_message: Optional[str]

    def __post_init__(self) -> None:
        if self.is_valid and self.error_type is not None:
            raise ValueError("is_valid=True requires error_type is None")
        if not self.is_valid and self.error_type is None:
            raise ValueError("is_valid=False requires error_type is not None")


@dataclass
class RoutingResult:
    """상담사 라우팅 결과."""
    is_success: bool
    agent_group: AgentGroup
    is_system_error: bool
    fallback_message: Optional[str]


@dataclass
class WaitTimeEstimate:
    """상담사 대기 시간 예측."""
    estimated_minutes: int
    queue_position: int
    is_available: bool


@dataclass
class BusinessHoursResult:
    """영업시간 판단 결과."""
    is_open: bool
    next_open_time: Optional[datetime]
    message: Optional[str]


@dataclass
class CallbackResult:
    """콜백 예약 결과."""
    is_success: bool
    reservation_id: Optional[str]
    scheduled_time: Optional[datetime]
    phone_number: Optional[str]
    error_message: Optional[str]


@dataclass
class PhoneVerificationResult:
    """발신번호 콜백 사용 여부 확인 결과."""
    use_caller_number: bool
    phone_number: Optional[str]


@dataclass
class PhoneCollectionResult:
    """콜백 전화번호 수집 결과.

    Invariants:
    - is_valid=True → phone_number is not None
    """
    is_valid: bool
    phone_number: Optional[str]
    retry_count: int
    fallback_to_caller: bool

    def __post_init__(self) -> None:
        if self.is_valid and self.phone_number is None:
            raise ValueError("is_valid=True requires phone_number is not None")


@dataclass
class ConsentResult:
    """개인정보 저장 동의 결과.

    Invariants:
    - consent_given=True  → is_rejected=False
    - is_rejected=True    → consent_given=False
    """
    consent_given: bool
    is_rejected: bool

    def __post_init__(self) -> None:
        if self.consent_given and self.is_rejected:
            raise ValueError("consent_given=True requires is_rejected=False")
        if self.is_rejected and self.consent_given:
            raise ValueError("is_rejected=True requires consent_given=False")


@dataclass
class TimeCollectionResult:
    """콜백 희망 시간 수집 결과.

    Invariants:
    - is_valid=True → parsed_time is not None
    """
    is_valid: bool
    parsed_time: Optional[datetime]
    collection_mode: str
    retry_count: int

    def __post_init__(self) -> None:
        if self.is_valid and self.parsed_time is None:
            raise ValueError("is_valid=True requires parsed_time is not None")


@dataclass
class ConfirmationResult:
    """예약 확인 결과."""
    is_confirmed: bool
    needs_retry: bool


@dataclass
class APIError:
    """API 오류 정보."""
    error_type: APIErrorType
    message: str
    is_retryable: bool


@dataclass
class APIResult:
    """외부 API 호출 결과.

    Invariants:
    - is_success=True  → data is not None and error is None
    - is_success=False → error is not None
    """
    is_success: bool
    data: Optional[dict]
    error: Optional[APIError]
    response_time_ms: int
    retry_count: int

    def __post_init__(self) -> None:
        if self.is_success:
            if self.data is None:
                raise ValueError("is_success=True requires data is not None")
            if self.error is not None:
                raise ValueError("is_success=True requires error is None")
        else:
            if self.error is None:
                raise ValueError("is_success=False requires error is not None")


@dataclass
class RollbackResult:
    """트랜잭션 롤백 결과.

    Invariants:
    - is_success=True    → requires_manual=False
    - requires_manual=True → is_success=False and retry_count == 3
    """
    is_success: bool
    requires_manual: bool
    retry_count: int
    error_message: Optional[str]

    def __post_init__(self) -> None:
        if self.is_success and self.requires_manual:
            raise ValueError("is_success=True requires requires_manual=False")
        if self.requires_manual:
            if self.is_success:
                raise ValueError("requires_manual=True requires is_success=False")
            if self.retry_count != 3:
                raise ValueError(
                    f"requires_manual=True requires retry_count == 3, got {self.retry_count}"
                )


@dataclass
class ConversationSummary:
    """대화 요약."""
    intent: object
    auth_status: bool
    processing_history: list[str]
    escalation_reason: str
    customer_complaint: str
