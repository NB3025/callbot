"""callbot.business.config — 비즈니스 계층 설정"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time


@dataclass
class BusinessConfig:
    """비즈니스 계층 통합 설정."""

    # 타임아웃 (초)
    billing_api_timeout_sec: float = 5.0
    customer_db_timeout_sec: float = 1.0

    # 재시도
    max_api_retries: int = 2
    max_rollback_retries: int = 3

    # 서킷브레이커
    circuit_failure_threshold: float = 0.5   # 50%
    circuit_min_calls: int = 10
    circuit_window_sec: int = 60
    circuit_half_open_timeout_sec: int = 30

    # 인증
    max_auth_attempts: int = 3

    # 영업시간
    business_open: time = field(default_factory=lambda: time(9, 0))
    business_close: time = field(default_factory=lambda: time(18, 0))

    # 콜백
    max_phone_retries: int = 1
    max_time_retries: int = 2
