"""callbot.orchestrator.config — 오케스트레이터 설정 클래스"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrchestratorConfig:
    """오케스트레이터 통합 설정.

    Attributes:
        no_response_timeout_sec: 무응답 타임아웃 (초, 기본 30초)
        max_turns: 최대 턴 수 (기본 20)
        max_minutes: 최대 통화 시간 (분, 기본 15)
        warn_turns: 경고 턴 수 (기본 18)
        warn_minutes: 경고 시간 (분, 기본 13)
        health_check_interval_sec: 외부 헬스체크 주기 (초, 기본 30)
        error_rate_window_sec: 내부 오류율 윈도우 (초, 기본 60)
        min_requests_for_failure: 오탐 방지 최소 요청 수 (기본 10)
    """
    no_response_timeout_sec: int = 30
    max_turns: int = 20
    max_minutes: int = 15
    warn_turns: int = 18
    warn_minutes: int = 13
    health_check_interval_sec: int = 30
    error_rate_window_sec: int = 60
    min_requests_for_failure: int = 10
