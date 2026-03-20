"""callbot.session.config — 세션 설정 클래스"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionConfig:
    """세션_관리자 설정.

    Attributes:
        max_business_turns: 최대 업무 턴 수 (기본 20)
        max_minutes: 최대 세션 시간 (분, 기본 15.0)
        warning_turns: 경고 임계값 턴 수 (기본 18)
        warning_minutes: 경고 임계값 시간 (분, 기본 13.0)
        retry_delays: DB 재시도 대기 시간 목록 (초, 기본 [0.1, 0.2, 0.4])
    """

    max_business_turns: int = 20
    max_minutes: float = 15.0
    warning_turns: int = 18
    warning_minutes: float = 13.0
    retry_delays: list[float] = field(default_factory=lambda: [0.1, 0.2, 0.4])
